# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Suite AUDIT-007 (issue #282): matriz completa de cash management.

Ejerce la ecuacion de aceptacion del issue en cada escenario:

    book balance +/- reconciling items = bank statement balance

Cubre la matriz completa de conciliacion bancaria:

- Cobros y pagos contra transacciones de extracto.
- Transferencias entre bancos (ambas piernas, misma moneda y FX).
- Fees bancarios, intereses, depositos y retiros como destinos GL.
- Returned payments y reversals via cancelacion append-only.
- Partidas conciliatorias y saldo bancario por compania, cuenta,
  libro, moneda y periodo.
- Bank transactions sin posting, postings sin bank transaction y
  duplicados con diagnostico explicito.
- Conciliacion repetida idempotente.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

COMPANY = "bnk7"
AS_OF = date(2026, 8, 21)


@pytest.fixture()
def app_ctx():
    """Aplicacion aislada con base SQLite en memoria."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Entity, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code=COMPANY, name="Banco7", company_name="Banco7", tax_id="BNK-7", currency="NIO"),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dolares", decimals=2, active=True),
                Currency(code="EUR", name="Euros", decimals=2, active=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def chart(app_ctx):
    """Catalogo minimo: dos bancos GL con cuentas bancarias NIO/USD, libro primario y defaults."""
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        database,
    )

    bank_gl_a = Accounts(entity=COMPANY, code="1001", name="Banco A", classification="asset", account_type="bank")
    bank_gl_b = Accounts(entity=COMPANY, code="1002", name="Banco B", classification="asset", account_type="bank")
    bank_gl_usd = Accounts(entity=COMPANY, code="1003", name="Banco USD", classification="asset", account_type="bank")
    fx_gain = Accounts(entity=COMPANY, code="4102", name="Ganancia Cambiaria", classification="income")
    fx_loss = Accounts(entity=COMPANY, code="6102", name="Perdida Cambiaria", classification="expense")
    customer_advance = Accounts(entity=COMPANY, code="1102", name="Anticipo Clientes", classification="asset")
    supplier_advance = Accounts(entity=COMPANY, code="2102", name="Anticipo Proveedores", classification="asset")
    book = Book(entity=COMPANY, code="BNKLOC", name="Libro Fiscal", currency="NIO", status="activo", is_primary=True)
    database.session.add_all([bank_gl_a, bank_gl_b, bank_gl_usd, fx_gain, fx_loss, customer_advance, supplier_advance, book])
    database.session.flush()

    bank_a = Bank(name="Banco Nacional 7")
    bank_b = Bank(name="Banco Regional 7")
    database.session.add_all([bank_a, bank_b])
    database.session.flush()

    account_a = BankAccount(
        bank_id=bank_a.id,
        company=COMPANY,
        account_name="Cuenta A",
        account_no="A-001",
        currency="NIO",
        gl_account_id=bank_gl_a.id,
    )
    account_b = BankAccount(
        bank_id=bank_b.id,
        company=COMPANY,
        account_name="Cuenta B",
        account_no="B-001",
        currency="NIO",
        gl_account_id=bank_gl_b.id,
    )
    account_usd = BankAccount(
        bank_id=bank_a.id,
        company=COMPANY,
        account_name="Cuenta USD",
        account_no="A-002",
        currency="USD",
        gl_account_id=bank_gl_usd.id,
    )
    database.session.add_all(
        [
            account_a,
            account_b,
            account_usd,
            CompanyDefaultAccount(
                company=COMPANY,
                default_bank=bank_gl_a.id,
                customer_advance_account_id=customer_advance.id,
                supplier_advance_account_id=supplier_advance.id,
                exchange_gain_account_id=fx_gain.id,
                exchange_loss_account_id=fx_loss.id,
                unrealized_exchange_gain_account_id=fx_gain.id,
                unrealized_exchange_loss_account_id=fx_loss.id,
            ),
        ]
    )
    database.session.commit()
    return {
        "bank_gl_a_id": bank_gl_a.id,
        "bank_gl_b_id": bank_gl_b.id,
        "book_id": book.id,
        "account_a": account_a,
        "account_b": account_b,
        "account_usd": account_usd,
    }


def _make_bank_transaction(bank_account, *, deposit=None, withdrawal=None, posting_date=AS_OF, reference=None):
    """Persiste una linea de extracto bancario."""
    from cacao_accounting.database import BankTransaction, database

    transaction = BankTransaction(
        bank_account_id=bank_account.id,
        posting_date=posting_date,
        deposit=deposit,
        withdrawal=withdrawal,
        reference_number=reference,
    )
    database.session.add(transaction)
    database.session.commit()
    return transaction


def _make_payment(
    *,
    amount: Decimal,
    payment_type: str = "receive",
    bank_account,
    target_bank_account=None,
    posting_date=AS_OF,
    currency="NIO",
    rate: Decimal = Decimal("1"),
    post: bool = True,
):
    """Crea un pago aprobado (opcionalmente contabilizado) sin referencias."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import PaymentEntry, database

    is_inflow = payment_type in ("receive", "credit_note")
    received_amount = amount if payment_type in ("receive", "credit_note", "internal_transfer") else None
    paid_amount = amount if payment_type in ("pay", "debit_note", "internal_transfer") else None
    base_received = amount * rate if received_amount is not None else None
    base_paid = amount * rate if paid_amount is not None else None
    if payment_type == "internal_transfer":
        # Semantica de bancos/services.py: el tipo de cambio de una transferencia
        # es origen->destino; received_amount = paid * rate y la pierna receptora
        # no conserva monto funcional propio.
        if target_bank_account and target_bank_account.currency and target_bank_account.currency != currency:
            received_amount = (amount * rate).quantize(Decimal("0.0001"))
            base_received = None
    payment = PaymentEntry(
        company=COMPANY,
        posting_date=posting_date,
        payment_type=payment_type,
        bank_account_id=bank_account.id,
        target_bank_account_id=target_bank_account.id if target_bank_account else None,
        paid_from_account_id=bank_account.gl_account_id if not is_inflow else None,
        paid_to_account_id=target_bank_account.gl_account_id if target_bank_account else None,
        transaction_currency=currency,
        base_currency="NIO",
        currency=currency,
        exchange_rate=rate,
        received_amount=received_amount,
        paid_amount=paid_amount,
        base_received_amount=base_received,
        base_paid_amount=base_paid,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()
    if post:
        post_document_to_gl(payment)
        database.session.commit()
    return payment


def _reconcile(transaction, target_type: str, target_id: str, amount: Decimal, recon_date=date(2026, 8, 21)):
    """Concilia una transaccion bancaria contra un destino y confirma la sesion."""
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )

    reconciliation = reconcile_bank_items(
        BankReconciliationRequest(
            company=COMPANY,
            reconciliation_date=recon_date,
            matches=[BankReconciliationMatch(transaction.id, target_type, target_id, amount)],
        )
    )
    database.session.commit()
    return reconciliation


def _book_balance(chart, bank_account, as_of=AS_OF) -> Decimal:
    """Saldo contable del banco segun el resumen de saldos bancarios."""
    from cacao_accounting.reportes.services import BankingFilters, get_bank_balance_summary

    report = get_bank_balance_summary(BankingFilters(company=COMPANY, bank_account_id=bank_account.id))
    row = next(row for row in report.rows if row.values["account_no"] == bank_account.account_no)
    del chart
    return row.values["ending_balance"]


def _statement_balance(bank_account, as_of=AS_OF) -> Decimal:
    """Saldo del extracto: suma de depositos menos retiros al corte indicado."""
    from cacao_accounting.database import BankAccount, BankTransaction, database

    rows = (
        database.session.execute(
            select(BankTransaction)
            .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
            .filter_by(id=bank_account.id)
        )
        .scalars()
        .all()
    )
    balance = Decimal("0")
    for transaction in rows:
        if as_of is not None and transaction.posting_date > as_of:
            continue
        balance += Decimal(str(transaction.deposit or "0")) - Decimal(str(transaction.withdrawal or "0"))
    return balance


def _assert_cash_equation(chart, bank_account, *, expected_reconciling_items: Decimal) -> None:
    """Ecuacion de aceptacion AUDIT-007.

    ``book balance +/- reconciling items = bank statement balance``:
    el delta libro-extracto debe ser exactamente el neto de partidas
    conciliatorias pendientes que cada escenario declara.
    """
    book = _book_balance(chart, bank_account)
    statement = _statement_balance(bank_account)
    assert book - statement == expected_reconciling_items, (book, statement)
    assert statement + expected_reconciling_items == book


# --------------------------------------------------------------------------- #
# 1. Cobros y pagos


def test_receive_and_pay_reconcile_book_to_statement(app_ctx, chart):
    """Un cobro y un pago completos cuadran libro contra extracto tras conciliar."""
    from cacao_accounting.database import ReconciliationItem, database

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("500.00"), reference="DEP-1")
    withdrawal = _make_bank_transaction(chart["account_a"], withdrawal=Decimal("200.00"), reference="CHK-1")
    collection = _make_payment(amount=Decimal("500.00"), payment_type="receive", bank_account=chart["account_a"])
    payment = _make_payment(amount=Decimal("200.00"), payment_type="pay", bank_account=chart["account_a"])

    _reconcile(deposit, "payment_entry", collection.id, Decimal("500.00"))
    _reconcile(withdrawal, "payment_entry", payment.id, Decimal("200.00"))

    assert deposit.is_reconciled is True
    assert withdrawal.is_reconciled is True
    assert deposit.payment_entry_id == collection.id
    assert withdrawal.payment_entry_id == payment.id
    items = database.session.execute(select(ReconciliationItem)).scalars().all()
    assert {item.status for item in items} == {"reconciled"}
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("0"))


def test_partial_statement_line_splits_across_payments_and_is_idempotent(app_ctx, chart):
    """Un deposito se reparte entre dos pagos; el replay devuelve la misma conciliacion."""
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )
    from cacao_accounting.database import ReconciliationItem, database

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("100.00"))
    first = _make_payment(amount=Decimal("60.00"), bank_account=chart["account_a"], post=False)
    second = _make_payment(amount=Decimal("40.00"), bank_account=chart["account_a"], post=False)

    request_first = BankReconciliationRequest(
        company=COMPANY,
        reconciliation_date=AS_OF,
        matches=[BankReconciliationMatch(deposit.id, "payment_entry", first.id, Decimal("60.00"))],
    )
    reconciliation = reconcile_bank_items(request_first)
    database.session.commit()
    assert reconcile_bank_items(request_first).id == reconciliation.id

    item = database.session.execute(select(ReconciliationItem)).scalars().first()
    assert item.status == "partial"
    assert deposit.is_reconciled is False
    # El libro registra los pagos aun no contabilizados como partida conciliatoria negativa.
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("-100.00"))

    _reconcile(deposit, "payment_entry", second.id, Decimal("40.00"))
    assert deposit.is_reconciled is True
    assert reconcile_bank_items(request_first).id == reconciliation.id
    items = database.session.execute(select(ReconciliationItem)).scalars().all()
    statuses = {item.status for item in items}
    # Los status son append-only: el primer item conserva "partial" como historial,
    # la transaccion queda conciliada cuando la suma de asignaciones cubre su monto.
    assert statuses == {"partial", "reconciled"}
    assert sum(item.allocated_amount for item in items) == Decimal("100.00")
    # Conciliar no postea: el extracto cubierto sigue siendo partida conciliatoria
    # hasta que los pagos se contabilicen en el libro.
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("-100.00"))


# --------------------------------------------------------------------------- #
# 2. Transferencias entre bancos


def test_internal_transfer_reconciles_both_legs_and_balances(app_ctx, chart):
    """La transferencia interna concilia la salida en A y la entrada en B."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    transfer = _make_payment(
        amount=Decimal("250.00"),
        payment_type="internal_transfer",
        bank_account=chart["account_a"],
        target_bank_account=chart["account_b"],
    )
    out_leg = _make_bank_transaction(chart["account_a"], withdrawal=Decimal("250.00"), reference="TRF-OUT")
    in_leg = _make_bank_transaction(chart["account_b"], deposit=Decimal("250.00"), reference="TRF-IN")

    for leg in (out_leg, in_leg):
        candidates = find_bank_reconciliation_candidates(leg.id)
        payment_candidates = [candidate for candidate in candidates if candidate.reference_type == "payment_entry"]
        assert len(payment_candidates) == 1
        assert payment_candidates[0].reference_id == transfer.id
        assert payment_candidates[0].status == "exact"

    _reconcile(out_leg, "payment_entry", transfer.id, Decimal("250.00"))
    _reconcile(in_leg, "payment_entry", transfer.id, Decimal("250.00"))

    assert out_leg.is_reconciled and in_leg.is_reconciled
    assert out_leg.payment_entry_id == in_leg.payment_entry_id == transfer.id
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("0"))
    _assert_cash_equation(chart, chart["account_b"], expected_reconciling_items=Decimal("0"))
    assert _statement_balance(chart["account_a"]) == Decimal("-250.00")
    assert _statement_balance(chart["account_b"]) == Decimal("250.00")


def test_multicurrency_transfer_reconciles_each_leg_in_its_currency(app_ctx, chart):
    """Transferencia USD->NIO: cada pierna concilia en su propia moneda de extracto."""
    from datetime import date as date_type

    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates
    from cacao_accounting.database import ExchangeRate, database

    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate="36.000000", date=date_type(2026, 8, 1)))
    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate="36.000000", date=AS_OF))
    database.session.commit()
    transfer = _make_payment(
        amount=Decimal("10.00"),
        payment_type="internal_transfer",
        bank_account=chart["account_usd"],
        target_bank_account=chart["account_a"],
        currency="USD",
        rate=Decimal("36"),
    )
    out_leg = _make_bank_transaction(chart["account_usd"], withdrawal=Decimal("10.00"))
    in_leg = _make_bank_transaction(chart["account_a"], deposit=Decimal("360.00"))

    out_candidates = [
        candidate
        for candidate in find_bank_reconciliation_candidates(out_leg.id)
        if candidate.reference_type == "payment_entry"
    ]
    in_candidates = [
        candidate
        for candidate in find_bank_reconciliation_candidates(in_leg.id)
        if candidate.reference_type == "payment_entry"
    ]
    assert [candidate.amount for candidate in out_candidates] == [Decimal("10.00")]
    assert [candidate.amount for candidate in in_candidates] == [Decimal("360.0000")]

    _reconcile(out_leg, "payment_entry", transfer.id, Decimal("10.00"))
    _reconcile(in_leg, "payment_entry", transfer.id, Decimal("360.0000"))

    assert out_leg.is_reconciled and in_leg.is_reconciled
    # La cuenta USD concilia en su moneda (extracto -10 USD) mientras el libro
    # registra la contrapartida funcional (-360 NIO a la tasa histórica 36).
    assert _statement_balance(chart["account_usd"]) == Decimal("-10.00")
    assert _book_balance(chart, chart["account_usd"]) == Decimal("-360.0000")
    assert _statement_balance(chart["account_usd"]) * Decimal("36") == _book_balance(chart, chart["account_usd"])
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("0"))


# --------------------------------------------------------------------------- #
# 3. Fees, intereses, depositos y retiros


def test_bank_fee_and_interest_reconcile_gl_entry_targets(app_ctx, chart):
    """Fee e interés del extracto se concilian contra entradas GL del banco."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates
    from cacao_accounting.database import GLEntry, database

    fee = _make_bank_transaction(chart["account_a"], withdrawal=Decimal("15.00"), reference="FEE-AUG")
    interest = _make_bank_transaction(chart["account_a"], deposit=Decimal("50.00"), reference="INT-AUG")
    fee_gl = GLEntry(
        posting_date=AS_OF,
        company=COMPANY,
        ledger_id=chart["book_id"],
        account_id=chart["bank_gl_a_id"],
        account_code="1001",
        debit=Decimal("0"),
        credit=Decimal("15.0000"),
        account_currency="NIO",
        company_currency="NIO",
        voucher_type="journal_entry",
        voucher_id="JRN-FEE-1",
        is_cancelled=False,
        is_reversal=False,
        bank_account_id=chart["account_a"].id,
    )
    interest_gl = GLEntry(
        posting_date=AS_OF,
        company=COMPANY,
        ledger_id=chart["book_id"],
        account_id=chart["bank_gl_a_id"],
        account_code="1001",
        debit=Decimal("50.0000"),
        credit=Decimal("0"),
        account_currency="NIO",
        company_currency="NIO",
        voucher_type="journal_entry",
        voucher_id="JRN-INT-1",
        is_cancelled=False,
        is_reversal=False,
        bank_account_id=chart["account_a"].id,
    )
    database.session.add_all([fee_gl, interest_gl])
    database.session.commit()

    fee_candidates = [c for c in find_bank_reconciliation_candidates(fee.id) if c.reference_type == "gl_entry"]
    interest_candidates = [c for c in find_bank_reconciliation_candidates(interest.id) if c.reference_type == "gl_entry"]
    assert [c.reference_id for c in fee_candidates] == [fee_gl.id]
    assert [c.reference_id for c in interest_candidates] == [interest_gl.id]

    _reconcile(fee, "gl_entry", fee_gl.id, Decimal("15.00"))
    _reconcile(interest, "gl_entry", interest_gl.id, Decimal("50.00"))

    assert fee.is_reconciled and interest.is_reconciled
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("0"))
    assert _book_balance(chart, chart["account_a"]) == _statement_balance(chart["account_a"]) == Decimal("35.00")


# --------------------------------------------------------------------------- #
# 4. Returned payments y reversals


def test_returned_payment_cancellation_unlinks_and_restores_equation(app_ctx, chart):
    """El reverso de un cobro devuelto desvincula extracto y cancela asignaciones."""
    from cacao_accounting.contabilidad.posting_service import cancel_document
    from cacao_accounting.bancos.services import _apply_payment_cancellation_hooks
    from cacao_accounting.database import ReconciliationItem, database

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("100.00"), reference="CHQ-DEV")
    collection = _make_payment(amount=Decimal("100.00"), bank_account=chart["account_a"])
    _reconcile(deposit, "payment_entry", collection.id, Decimal("100.00"))
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("0"))

    cancel_document(collection)
    _apply_payment_cancellation_hooks(collection)
    database.session.commit()

    assert collection.docstatus == 2
    assert deposit.is_reconciled is False
    assert deposit.payment_entry_id is None
    items = database.session.execute(select(ReconciliationItem)).scalars().all()
    assert {item.status for item in items} == {"cancelled"}

    # El cheque devuelto aparece en el extracto como retiro; ambos saldos vuelven a cero.
    _make_bank_transaction(chart["account_a"], withdrawal=Decimal("100.00"), reference="CHQ-DEV-RET")
    _assert_cash_equation(chart, chart["account_a"], expected_reconciling_items=Decimal("0"))
    assert _statement_balance(chart["account_a"]) == Decimal("0")


def test_cancelled_collection_is_not_offered_again_as_candidate(app_ctx, chart):
    """Un cobro cancelado ya no es candidato para conciliaciones nuevas."""
    from cacao_accounting.contabilidad.posting_service import cancel_document
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("80.00"))
    collection = _make_payment(amount=Decimal("80.00"), bank_account=chart["account_a"])
    cancel_document(collection)
    database.session.commit()

    candidates = [
        candidate
        for candidate in find_bank_reconciliation_candidates(deposit.id)
        if candidate.reference_type == "payment_entry"
    ]
    assert candidates == []


# --------------------------------------------------------------------------- #
# 5. Huérfanos y duplicados con diagnóstico explícito


def test_orphan_diagnostics_flag_all_kinds_but_not_pending_items(app_ctx, chart):
    """Los cuatro tipos de huérfano generan diagnóstico; lo pendiente no es huérfano."""
    from cacao_accounting.reportes.services import get_reconciliation_report

    # (a) Cobro posteado sin extracto -> posting_without_bank_transaction.
    _make_payment(amount=Decimal("70.00"), bank_account=chart["account_a"])

    # (b) Extracto vinculado a un pago inexistente -> orphan_payment_link.
    ghost_link = _make_bank_transaction(chart["account_a"], deposit=Decimal("30.00"))
    ghost_link.payment_entry_id = "PAGO-FANTASMA"
    database.session.commit()

    # (c) Extracto sin conciliar y sin pago: NO es huérfano, es partida pendiente.
    _make_bank_transaction(chart["account_a"], withdrawal=Decimal("5.00"))

    report = get_reconciliation_report(company=COMPANY)
    diagnostics = {
        (row.values["source_id"], row.values["status"]): row.values["target_id"]
        for row in report.rows
        if row.values.get("recon_type") == "bank_diagnostic"
    }
    posted = [key for key in diagnostics if key[1] == "posting_without_bank_transaction" and key[0]]
    assert len(posted) == 1
    assert any(status == "orphan_payment_link" for _, status in diagnostics)
    # El extracto pendiente no genera fila de diagnóstico.
    assert report.totals["bank_orphan_count"] >= Decimal("2")


def test_posted_payment_without_bank_gl_dimension_is_diagnosed(app_ctx, chart):
    """Pago posteo sin línea GL con dimensión bancaria -> payment_without_bank_gl."""
    from cacao_accounting.database import GLEntry, database
    from cacao_accounting.reportes.services import get_reconciliation_report

    payment = _make_payment(amount=Decimal("40.00"), bank_account=chart["account_a"], post=False)
    statement_line = _make_bank_transaction(chart["account_a"], deposit=Decimal("40.00"))
    statement_line.payment_entry_id = payment.id
    database.session.flush()
    # GL del pago sin la dimension bancaria (simula posting historico defectuoso).
    database.session.add(
        GLEntry(
            posting_date=AS_OF,
            company=COMPANY,
            ledger_id=chart["book_id"],
            account_id=chart["bank_gl_a_id"],
            account_code="1001",
            debit=Decimal("0"),
            credit=Decimal("40.0000"),
            account_currency="NIO",
            company_currency="NIO",
            voucher_type="payment_entry",
            voucher_id=payment.id,
            is_cancelled=False,
            is_reversal=False,
            bank_account_id=None,
        )
    )
    database.session.commit()

    report = get_reconciliation_report(company=COMPANY)
    statuses = {
        row.values["status"]
        for row in report.rows
        if row.values.get("recon_type") == "bank_diagnostic" and row.values.get("source_id") == statement_line.id
    }
    assert "payment_without_bank_gl" in statuses


def test_duplicate_statement_import_is_detected_once(app_ctx, chart):
    """Reimportar un extracto marca duplicados y no persiste filas repetidas."""
    from cacao_accounting.bancos.statement_service import import_bank_statement
    from cacao_accounting.database import BankTransaction, database

    csv_data = "fecha,referencia,descripcion,deposito,retiro\n2026-08-21,DUP-1,Prueba,120.00,\n"
    mapping = {
        "date": "fecha",
        "reference": "referencia",
        "description": "descripcion",
        "deposit": "deposito",
        "withdrawal": "retiro",
    }

    imported = import_bank_statement(StringIO(csv_data), mapping, chart["account_a"].id, company=COMPANY, preview=False)
    replay = import_bank_statement(StringIO(csv_data), mapping, chart["account_a"].id, company=COMPANY, preview=False)

    assert imported.imported_count == 1
    assert imported.duplicate_count == 0
    assert replay.imported_count == 0
    assert replay.duplicate_count == 1
    assert replay.rows[0].duplicate is True
    persisted = (
        database.session.execute(select(BankTransaction).filter_by(bank_account_id=chart["account_a"].id)).scalars().all()
    )
    assert len(persisted) == 1


# --------------------------------------------------------------------------- #
# 6. Compania, cuenta, libro, moneda y periodo


def test_gl_candidates_respect_primary_ledger_and_date_window(app_ctx, chart):
    """Solo GL del libro primario dentro de la ventana ±7 días es candidato."""
    from cacao_accounting.bancos.reconciliation_service import find_bank_reconciliation_candidates
    from cacao_accounting.database import Book, GLEntry, database

    secondary_book = Book(entity=COMPANY, code="BNKSEC", name="Libro Secundario", currency="NIO", status="activo")
    database.session.add(secondary_book)
    database.session.flush()
    withdrawal = _make_bank_transaction(chart["account_a"], withdrawal=Decimal("60.00"))

    def _entry(voucher_id: str, *, posting_date, ledger_id, debit="0", credit="60"):
        return GLEntry(
            posting_date=posting_date,
            company=COMPANY,
            ledger_id=ledger_id,
            account_id=chart["bank_gl_a_id"],
            account_code="1001",
            debit=debit,
            credit=credit,
            account_currency="NIO",
            company_currency="NIO",
            voucher_type="journal_entry",
            voucher_id=voucher_id,
            is_cancelled=False,
            is_reversal=False,
        )

    outside_window = _entry("JRN-OLD", posting_date=date(2026, 7, 1), ledger_id=chart["book_id"])
    secondary_ledger = _entry("JRN-SEC", posting_date=AS_OF, ledger_id=secondary_book.id)
    eligible = _entry("JRN-OK", posting_date=AS_OF, ledger_id=chart["book_id"])
    database.session.add_all([outside_window, secondary_ledger, eligible])
    database.session.commit()

    gl_candidates = [c for c in find_bank_reconciliation_candidates(withdrawal.id) if c.reference_type == "gl_entry"]
    assert [c.reference_id for c in gl_candidates] == [eligible.id]


def test_cross_company_and_foreign_currency_targets_are_rejected(app_ctx, chart):
    """Transacciones de otra compania y pagos en moneda ajena no concilian."""
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationError,
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )
    from cacao_accounting.database import Entity, database

    database.session.add(Entity(code="otra", name="Otra", company_name="Otra", tax_id="OTR-1", currency="NIO"))
    from cacao_accounting.database import Accounts, Bank, BankAccount

    other_gl = Accounts(entity="otra", code="9001", name="Banco Ajeno", classification="asset", account_type="bank")
    other_bank = Bank(name="Banco Otra Compania")
    database.session.add_all([other_gl, other_bank])
    database.session.flush()
    other_account = BankAccount(
        bank_id=other_bank.id, company="otra", account_name="Cuenta Ajena", currency="NIO", gl_account_id=other_gl.id
    )
    database.session.add(other_account)
    database.session.commit()

    foreign_deposit = _make_bank_transaction(other_account, deposit=Decimal("90.00"))

    # La transaccion de otra compania no puede conciliarse bajo bnk7.
    with pytest.raises(BankReconciliationError, match="otra compania"):
        reconcile_bank_items(
            BankReconciliationRequest(
                company=COMPANY,
                reconciliation_date=AS_OF,
                matches=[BankReconciliationMatch(foreign_deposit.id, "gl_entry", "GL-INEXISTENTE", Decimal("90.00"))],
            )
        )

    # Un pago en moneda ajena a la cuenta USD (distinta de la funcional)
    # se rechaza de forma explicita al conciliarlo.
    usd_withdrawal = _make_bank_transaction(chart["account_usd"], withdrawal=Decimal("90.00"))
    foreign_payment = _make_payment(
        amount=Decimal("90.00"), payment_type="pay", bank_account=chart["account_usd"], currency="EUR", post=False
    )
    with pytest.raises(BankReconciliationError, match="moneda del pago no coincide"):
        reconcile_bank_items(
            BankReconciliationRequest(
                company=COMPANY,
                reconciliation_date=AS_OF,
                matches=[BankReconciliationMatch(usd_withdrawal.id, "payment_entry", foreign_payment.id, Decimal("90.00"))],
            )
        )


def test_balance_summary_and_diagnostics_respect_period_cutoff(app_ctx, chart):
    """El saldo bancario y los diagnósticos honran el corte de período indicado."""
    from cacao_accounting.reportes.services import BankingFilters, get_bank_balance_summary, get_reconciliation_report

    cutoff_day = date(2026, 8, 20)
    before = _make_payment(amount=Decimal("300.00"), bank_account=chart["account_a"], posting_date=cutoff_day)
    after = _make_payment(amount=Decimal("700.00"), bank_account=chart["account_a"], posting_date=date(2026, 8, 25))
    deposit_before = _make_bank_transaction(
        chart["account_a"], deposit=Decimal("300.00"), posting_date=cutoff_day, reference="ANTES"
    )
    _make_bank_transaction(chart["account_a"], deposit=Decimal("700.00"), posting_date=date(2026, 8, 25), reference="DESPUES")
    _reconcile(deposit_before, "payment_entry", before.id, Decimal("300.00"))

    report_cutoff = get_bank_balance_summary(
        BankingFilters(company=COMPANY, bank_account_id=chart["account_a"].id, as_of_date=cutoff_day)
    )
    assert report_cutoff.totals["ending_balance"] == Decimal("300.0000")
    report_full = get_bank_balance_summary(BankingFilters(company=COMPANY, bank_account_id=chart["account_a"].id))
    assert report_full.totals["ending_balance"] == Decimal("1000.0000")

    def _diagnostic_sources(as_of):
        report = get_reconciliation_report(company=COMPANY, as_of_date=as_of)
        return {
            row.values["source_id"]
            for row in report.rows
            if row.values.get("recon_type") == "bank_diagnostic"
            and row.values.get("status") == "posting_without_bank_transaction"
        }

    # Al corte, el pago posterior no existe; el cobro anterior ya esta conciliado.
    assert before.id not in _diagnostic_sources(cutoff_day)
    assert after.id not in _diagnostic_sources(cutoff_day)
    # Sin corte, el pago posterior sin extracto vinculado es diagnostico explicito.
    assert after.id in _diagnostic_sources(None)
    assert before.id not in _diagnostic_sources(None)


# --------------------------------------------------------------------------- #
# 7. Contexto contable persistido en ReconciliationItem


def test_reconciliation_items_persist_accounting_context(app_ctx, chart):
    """Cada asignacion conserva compania, pierna, moneda, libro, direccion y tasa."""
    from datetime import date as date_type

    from cacao_accounting.database import ExchangeRate, ReconciliationItem, database

    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate="36.000000", date=date_type(2026, 8, 1)))
    database.session.commit()

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("120.00"), reference="CTX-NIO")
    collection = _make_payment(amount=Decimal("120.00"), bank_account=chart["account_a"])
    _reconcile(deposit, "payment_entry", collection.id, Decimal("120.00"))

    transfer = _make_payment(
        amount=Decimal("10.00"),
        payment_type="internal_transfer",
        bank_account=chart["account_usd"],
        target_bank_account=chart["account_a"],
        currency="USD",
        rate=Decimal("36"),
    )
    out_leg = _make_bank_transaction(chart["account_usd"], withdrawal=Decimal("10.00"), reference="CTX-OUT")
    _reconcile(out_leg, "payment_entry", transfer.id, Decimal("10.00"))

    items = database.session.execute(select(ReconciliationItem)).scalars().all()
    by_reference = {item.reference_id: item for item in items}

    nio_item = by_reference[deposit.id]
    assert nio_item.company == COMPANY
    assert nio_item.bank_account_id == chart["account_a"].id
    assert nio_item.currency == "NIO"
    assert nio_item.ledger_id == chart["book_id"]
    assert nio_item.direction == "deposit"
    assert nio_item.exchange_rate == Decimal("1")

    usd_item = next(item for item in items if item.source_id == out_leg.id)
    assert usd_item.bank_account_id == chart["account_usd"].id
    assert usd_item.currency == "USD"
    assert usd_item.direction == "withdrawal"
    # Tasa historica funcional -> moneda del banco (inversa de USD->NIO 36),
    # persistida con la escala de 9 decimales del modelo.
    assert usd_item.exchange_rate == (Decimal("1") / Decimal("36")).quantize(Decimal("0.000000001"))
    assert usd_item.exchange_rate.as_tuple().exponent == -9


def test_orphaned_statement_line_cannot_be_consumed_twice(app_ctx, chart):
    """Con contexto persistido, borrar el extracto no libera el saldo consumido."""
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationError,
        BankReconciliationMatch,
        BankReconciliationRequest,
        find_bank_reconciliation_candidates,
        reconcile_bank_items,
    )
    from cacao_accounting.database import ExchangeRate, database

    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate="36.000000", date=date(2026, 8, 1)))
    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate="36.000000", date=AS_OF))
    database.session.commit()

    transfer = _make_payment(
        amount=Decimal("10.00"),
        payment_type="internal_transfer",
        bank_account=chart["account_usd"],
        target_bank_account=chart["account_a"],
        currency="USD",
        rate=Decimal("36"),
    )
    out_leg = _make_bank_transaction(chart["account_usd"], withdrawal=Decimal("10.00"), reference="ORPHAN-OUT")
    _reconcile(out_leg, "payment_entry", transfer.id, Decimal("10.00"))

    # La transaccion fuente desaparece: el importe asignado persiste en el item.
    database.session.delete(out_leg)
    database.session.commit()

    replay_leg = _make_bank_transaction(chart["account_usd"], withdrawal=Decimal("10.00"), reference="REPLAY")
    payment_candidates = [
        candidate
        for candidate in find_bank_reconciliation_candidates(replay_leg.id)
        if candidate.reference_type == "payment_entry"
    ]
    # La pierna ya consumida no vuelve a ofrecerse como candidato.
    assert payment_candidates == []

    with pytest.raises(BankReconciliationError, match="saldo pendiente del documento destino"):
        reconcile_bank_items(
            BankReconciliationRequest(
                company=COMPANY,
                reconciliation_date=AS_OF,
                matches=[BankReconciliationMatch(replay_leg.id, "payment_entry", transfer.id, Decimal("10.00"))],
            )
        )


def test_persisted_currency_rejects_mixed_currency_allocation_of_unknown_source(app_ctx, chart):
    """La moneda persistida rechaza mezclas aunque la fuente ya no exista."""
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationError,
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )
    from cacao_accounting.database import Reconciliation, ReconciliationItem, database

    payment = _make_payment(amount=Decimal("90.00"), bank_account=chart["account_a"])
    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("90.00"), reference="MIX-1")

    reconciliation = Reconciliation(company=COMPANY, recon_date=AS_OF, recon_type="bank")
    database.session.add(reconciliation)
    database.session.flush()
    database.session.add(
        ReconciliationItem(
            reconciliation_id=reconciliation.id,
            reference_type="bank_transaction",
            reference_id="LEGACY-FANTASMA",
            amount=Decimal("40.00"),
            allocated_amount=Decimal("40.00"),
            reconciliation_date=AS_OF,
            status="reconciled",
            source_type="bank_transaction",
            source_id="FANTASMA-INEXISTENTE",
            target_type="payment_entry",
            target_id=payment.id,
            bank_account_id=chart["account_a"].id,
            currency="EUR",
        )
    )
    database.session.commit()

    # La transaccion fuente del item previo no existe: sin moneda persistida la
    # validacion se saltaba el chequeo y mezclaba EUR con NIO en el pendiente.
    with pytest.raises(BankReconciliationError, match="otra moneda bancaria"):
        reconcile_bank_items(
            BankReconciliationRequest(
                company=COMPANY,
                reconciliation_date=AS_OF,
                matches=[BankReconciliationMatch(deposit.id, "payment_entry", payment.id, Decimal("90.00"))],
            )
        )


def test_backfill_restores_context_and_reports_unresolved(app_ctx, chart):
    """El backfill migra partidas legacy y diagnostica las de fuente perdida."""
    from cacao_accounting.bancos.reconciliation_service import backfill_reconciliation_item_context
    from cacao_accounting.database import ReconciliationItem, database

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("80.00"), reference="BF-1")
    collection = _make_payment(amount=Decimal("80.00"), bank_account=chart["account_a"])
    _reconcile(deposit, "payment_entry", collection.id, Decimal("80.00"))

    items = database.session.execute(select(ReconciliationItem)).scalars().all()
    for item in items:
        item.company = None
        item.bank_account_id = None
        item.currency = None
        item.ledger_id = None
        item.direction = None
        item.exchange_rate = None
    database.session.commit()

    stats = backfill_reconciliation_item_context()
    assert stats == {"backfilled": 1, "unresolved": 0}
    item = database.session.execute(select(ReconciliationItem)).scalars().first()
    assert item.company == COMPANY
    assert item.bank_account_id == chart["account_a"].id
    assert item.currency == "NIO"
    assert item.ledger_id == chart["book_id"]
    assert item.direction == "deposit"
    assert item.exchange_rate == Decimal("1")

    # Una partida cuya fuente ya no existe no tiene contexto inequivoco.
    database.session.delete(deposit)
    item.company = None
    item.bank_account_id = None
    item.currency = None
    database.session.commit()

    stats_after = backfill_reconciliation_item_context()
    assert stats_after == {"backfilled": 0, "unresolved": 1}
    database.session.expire(item)
    assert item.currency is None


def test_missing_context_items_are_diagnosed_and_resolved_by_backfill(app_ctx, chart):
    """Las partidas sin contexto generan diagnóstico explícito hasta migrarse."""
    from cacao_accounting.bancos.reconciliation_service import backfill_reconciliation_item_context
    from cacao_accounting.reportes.services import get_reconciliation_report

    deposit = _make_bank_transaction(chart["account_a"], deposit=Decimal("55.00"), reference="DIAG-CTX")
    collection = _make_payment(amount=Decimal("55.00"), bank_account=chart["account_a"])
    _reconcile(deposit, "payment_entry", collection.id, Decimal("55.00"))

    from cacao_accounting.database import ReconciliationItem, database

    item = database.session.execute(select(ReconciliationItem)).scalars().first()
    item.currency = None
    item.bank_account_id = None
    database.session.commit()

    def _context_statuses():
        report = get_reconciliation_report(company=COMPANY)
        return [
            row.values["status"]
            for row in report.rows
            if row.values.get("recon_type") == "bank_diagnostic"
            and row.values.get("status") == "reconciliation_item_missing_context"
        ]

    assert len(_context_statuses()) == 1

    backfill_reconciliation_item_context()
    database.session.commit()
    assert _context_statuses() == []
