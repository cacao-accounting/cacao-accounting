# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Suite AUDIT-005 (issue #280): matriz O2C de pagos, creditos y reversals.

Ejerce la ecuacion de aceptacion del issue en cada escenario:

    invoice - credit notes - applied payments - write-offs = outstanding receivable

en moneda de transaccion y funcional, con trazabilidad de journal
(``GLEntry.voucher_type``/``voucher_id``), idempotencia y aislamiento por
compania/libro/periodo. Los descuentos de pago (`PaymentReference.discount_amount`)
se usan como proxy de write-offs: liquidan saldo sin consumir efectivo y postean
a la cuenta de descuento configurada.

Escenarios cubiertos:
- Pagos parciales y multiples pagos contra una factura.
- Un pago contra multiples facturas.
- Overpayment que se convierte en anticipo y se aplica despues (con neteo GL).
- Credit note aplicada al outstanding.
- Refund de una credit note (liquidacion de la nota en el subledger).
- Descuento temprano como write-off proxy con posting a cuenta de descuento.
- Cancelacion/reversal de pago y de factura (append-only).
- Conciliacion AR subledger <-> cuenta control GL via matriz de conciliacion.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

COMPANY = "o2c"
AS_OF = date(2026, 8, 20)
# Corte abierto para calculos de saldo vigentes (date.today() puede ser anterior
# a las fechas de transaccion usadas en los escenarios).
OPEN_END = date(2026, 12, 31)


def _cancellation_metadata(posting_date: date) -> dict[str, str]:
    """Create the actor and open period required by the cancellation contract."""
    from cacao_accounting.database import AccountingPeriod, User, database

    if database.session.get(User, "admin") is None:
        database.session.add(
            User(
                id="admin",
                user="admin",
                name="Administrator",
                password=b"x",
                classification="admin",
                active=True,
            )
        )
    period = database.session.execute(
        database.select(AccountingPeriod)
        .where(
            AccountingPeriod.entity == COMPANY,
            AccountingPeriod.start <= posting_date,
            AccountingPeriod.end >= posting_date,
        )
        .order_by(AccountingPeriod.start.desc())
    ).scalar_one_or_none()
    if period is None:
        database.session.add(
            AccountingPeriod(
                entity=COMPANY,
                name=f"Cancellation {posting_date:%Y-%m-%d}",
                enabled=True,
                is_closed=False,
                start=posting_date.replace(day=1),
                end=posting_date,
            )
        )
    database.session.commit()
    return {"actor_user_id": "admin", "reason": "Prueba de anulacion"}


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
                Entity(code=COMPANY, name="O2C", company_name="O2C", tax_id="O2C-1", currency="NIO"),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dolares", decimals=2, active=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def chart(app_ctx):
    """Catalogo minimo: cuentas AR/ingreso/banco/anticipo/descuento/FX, libro y banco."""
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        PartyAccount,
        database,
    )

    ar = Accounts(entity=COMPANY, code="1101", name="Cuentas por Cobrar", classification="asset")
    income = Accounts(entity=COMPANY, code="4101", name="Ingreso", classification="income", account_type="income")
    bank_gl = Accounts(entity=COMPANY, code="1001", name="Banco", classification="asset", account_type="bank")
    advance = Accounts(entity=COMPANY, code="1102", name="Anticipo Clientes", classification="asset")
    discount = Accounts(entity=COMPANY, code="6101", name="Descuentos", classification="expense")
    fx_gain = Accounts(entity=COMPANY, code="4102", name="Ganancia Cambiaria", classification="income")
    fx_loss = Accounts(entity=COMPANY, code="6102", name="Perdida Cambiaria", classification="expense")
    fx_unreal_gain = Accounts(entity=COMPANY, code="4103", name="Ganancia Cambiaria No Realizada", classification="income")
    fx_unreal_loss = Accounts(entity=COMPANY, code="6103", name="Perdida Cambiaria No Realizada", classification="expense")
    book = Book(entity=COMPANY, code="O2CLOC", name="Libro Fiscal", currency="NIO", status="activo", is_primary=True)
    bank = Bank(name="Banco O2C")
    database.session.add_all(
        [ar, income, bank_gl, advance, discount, fx_gain, fx_loss, fx_unreal_gain, fx_unreal_loss, book, bank]
    )
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company=COMPANY,
        account_name="Cuenta O2C",
        currency="NIO",
        gl_account_id=bank_gl.id,
    )
    database.session.add_all(
        [
            bank_account,
            CompanyDefaultAccount(
                company=COMPANY,
                default_receivable=ar.id,
                default_income=income.id,
                default_bank=bank_gl.id,
                customer_advance_account_id=advance.id,
                sales_discount_account_id=discount.id,
                exchange_gain_account_id=fx_gain.id,
                exchange_loss_account_id=fx_loss.id,
                unrealized_exchange_gain_account_id=fx_unreal_gain.id,
                unrealized_exchange_loss_account_id=fx_unreal_loss.id,
            ),
            PartyAccount(party_id="CUST-O2C", company=COMPANY, receivable_account_id=ar.id),
        ]
    )
    database.session.commit()
    return {
        "ar_id": ar.id,
        "income_id": income.id,
        "bank_gl_id": bank_gl.id,
        "advance_id": advance.id,
        "discount_id": discount.id,
        "fx_gain_id": fx_gain.id,
        "fx_loss_id": fx_loss.id,
        "fx_unreal_gain_id": fx_unreal_gain.id,
        "fx_unreal_loss_id": fx_unreal_loss.id,
        "book_code": book.code,
        "book_id": book.id,
        "bank_account_id": bank_account.id,
    }


def _customer_id() -> str:
    return "CUST-O2C"


def _make_invoice(
    *,
    amount: Decimal,
    posting_date: date = AS_OF,
    currency: str = "NIO",
    rate: Decimal = Decimal("1"),
    document_type: str = "sales_invoice",
    customer: str | None = None,
):
    """Crea una factura/nota de venta aprobada (sin GL) y la retorna."""
    from cacao_accounting.database import CompanyDefaultAccount, SalesInvoice, SalesInvoiceItem, database

    defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company=COMPANY)).scalars().first()
    invoice = SalesInvoice(
        company=COMPANY,
        posting_date=posting_date,
        customer_id=customer or _customer_id(),
        document_type=document_type,
        transaction_currency=currency,
        base_currency="NIO",
        exchange_rate=rate,
        docstatus=1,
        total=amount,
        grand_total=amount,
        base_total=amount * rate,
        base_grand_total=amount * rate,
        outstanding_amount=amount,
        base_outstanding_amount=amount * rate,
        is_return=document_type == "sales_credit_note",
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ART-O2C",
            qty=Decimal("1"),
            rate=amount,
            amount=amount,
            base_amount=amount * rate,
            income_account_id=defaults.default_income if defaults else None,
        )
    )
    database.session.commit()
    return invoice


def _post_invoice(invoice) -> None:
    """Postea una factura al GL."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl

    post_document_to_gl(invoice)
    database.session.commit()


def _make_payment(
    *,
    amount: Decimal,
    payment_type: str = "receive",
    posting_date: date = AS_OF,
    currency: str = "NIO",
    rate: Decimal = Decimal("1"),
    chart: dict,
    party_id: str | None = None,
):
    """Crea un pago aprobado (sin GL ni referencias) y lo retorna."""
    from cacao_accounting.database import PaymentEntry, database

    payment = PaymentEntry(
        company=COMPANY,
        posting_date=posting_date,
        payment_type=payment_type,
        party_type="customer",
        party_id=party_id or _customer_id(),
        bank_account_id=chart["bank_account_id"],
        transaction_currency=currency,
        base_currency="NIO",
        currency=currency,
        exchange_rate=rate,
        received_amount=amount if payment_type == "receive" else None,
        paid_amount=amount if payment_type != "receive" else None,
        base_received_amount=amount * rate if payment_type == "receive" else None,
        base_paid_amount=amount * rate if payment_type != "receive" else None,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()
    return payment


def _apply(payment, lines: list[dict], allocation_date: date = AS_OF, party_id: str | None = None):
    """Aplica un pago contra documentos AR via el servicio de conciliacion."""
    from cacao_accounting.document_flow.payment import apply_payment_reconciliation

    payload_lines = []
    for line in lines:
        enriched = {"payment_id": payment.id, **line}
        payload_lines.append(enriched)
    reconciliation = apply_payment_reconciliation(
        company=COMPANY,
        party_type="customer",
        party_id=party_id or _customer_id(),
        allocation_date=allocation_date,
        lines=payload_lines,
    )
    database.session.commit()
    return reconciliation


def _post_payment(payment) -> None:
    from cacao_accounting.contabilidad.posting import post_document_to_gl

    post_document_to_gl(payment)
    database.session.commit()


def _outstanding(document, as_of_date: date | None = OPEN_END) -> Decimal:
    from cacao_accounting.document_flow.payment import compute_outstanding_amount

    return compute_outstanding_amount(document, as_of_date=as_of_date)


def _ar_gl_balance(chart: dict, as_of_date: date | None = AS_OF) -> Decimal:
    """Saldo deudor de la cuenta control AR excluyendo pares anulados."""
    from cacao_accounting.database import GLEntry, database
    from cacao_accounting.ledger_queries import exclude_cancelled_gl_entries

    query = exclude_cancelled_gl_entries(
        select(database.func.coalesce(database.func.sum(GLEntry.debit - GLEntry.credit), 0))
    ).where(GLEntry.company == COMPANY, GLEntry.account_id == chart["ar_id"])
    if as_of_date is not None:
        query = query.where(GLEntry.posting_date <= as_of_date)
    return database.session.execute(query).scalar_one()


def _matrix_row(chart: dict, area: str, as_of_date: date | None = AS_OF):
    from cacao_accounting.reportes.services import ReconciliationFilters, get_reconciliation_matrix

    matrix = get_reconciliation_matrix(
        ReconciliationFilters(company=COMPANY, ledger=chart["book_code"], as_of_date=as_of_date)
    )
    return next(row for row in matrix.rows if row.values["area"] == area)


def _assert_ar_reconciled(chart: dict, as_of_date: date | None = AS_OF) -> None:
    """La fila AR de la matriz debe cuadrar contra el GL de la cuenta control."""
    row = _matrix_row(chart, "AR", as_of_date)
    assert row.values["difference"] == Decimal("0"), row.values
    assert row.values["status"] == "reconciled"
    assert row.values["subledger_amount"] == row.values["gl_control_amount"]
    assert row.values["subledger_amount"] == _ar_gl_balance(chart, as_of_date)


def _subledger_totals(as_of_date: date | None = AS_OF) -> dict:
    from cacao_accounting.reportes.services import SubledgerFilters, get_ar_ap_subledger

    report = get_ar_ap_subledger(SubledgerFilters(company=COMPANY, party_type="customer", as_of_date=as_of_date))
    return report.totals


# --------------------------------------------------------------------------- #
# 1. Pagos parciales, multiples pagos y un pago contra varias facturas
# --------------------------------------------------------------------------- #


def test_280_partial_and_multiple_payments_equation(app_ctx, chart):
    """Pagos parciales y multiples: la ecuacion O2C se cumple en ambas monedas."""
    invoice = _make_invoice(amount=Decimal("1000"))
    _post_invoice(invoice)

    payment_a = _make_payment(amount=Decimal("400"), chart=chart)
    _apply(payment_a, [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 400}])
    _post_payment(payment_a)

    assert _outstanding(invoice) == Decimal("600")

    payment_b = _make_payment(amount=Decimal("350"), posting_date=date(2026, 8, 21), chart=chart)
    _apply(
        payment_b,
        [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 350}],
        allocation_date=date(2026, 8, 21),
    )
    _post_payment(payment_b)

    # Ecuacion en moneda de transaccion: 1000 - 0 notas - (400 + 350) aplicados = 250.
    assert _outstanding(invoice) == Decimal("250")
    # Moneda funcional (rate 1): el cache base coincide.
    assert invoice.base_outstanding_amount == Decimal("250")

    totals = _subledger_totals(date(2026, 8, 22))
    assert totals["original_amount"] == Decimal("1000")
    assert totals["paid_amount"] == Decimal("750")
    assert totals["outstanding_amount"] == Decimal("250")

    # Corte al 20 de agosto: solo el primer pago es visible.
    assert _outstanding(invoice, as_of_date=AS_OF) == Decimal("600")
    cutoff_totals = _subledger_totals(AS_OF)
    assert cutoff_totals["paid_amount"] == Decimal("400")
    assert cutoff_totals["outstanding_amount"] == Decimal("600")

    _assert_ar_reconciled(chart, date(2026, 8, 22))


def test_280_one_payment_against_many_invoices(app_ctx, chart):
    """Un pago aplica contra varias facturas sin exceder saldos individuales."""
    invoice_a = _make_invoice(amount=Decimal("500"))
    invoice_b = _make_invoice(amount=Decimal("400"))
    _post_invoice(invoice_a)
    _post_invoice(invoice_b)

    payment = _make_payment(amount=Decimal("900"), chart=chart)
    _apply(
        payment,
        [
            {"reference_type": "sales_invoice", "reference_id": invoice_a.id, "allocated_amount": 500},
            {"reference_type": "sales_invoice", "reference_id": invoice_b.id, "allocated_amount": 400},
        ],
    )
    _post_payment(payment)

    assert _outstanding(invoice_a) == Decimal("0")
    assert _outstanding(invoice_b) == Decimal("0")

    totals = _subledger_totals()
    assert totals["paid_amount"] == Decimal("900")
    assert totals["outstanding_amount"] == Decimal("0")
    _assert_ar_reconciled(chart)


# --------------------------------------------------------------------------- #
# 2. Overpayment -> anticipo -> aplicacion posterior con neteo GL
# --------------------------------------------------------------------------- #


def test_280_overpayment_becomes_advance_and_settles(app_ctx, chart):
    """El excedente de un cobro va a anticipo; su aplicacion netea AR en GL."""
    from cacao_accounting.database import CompanyDefaultAccount, database
    from cacao_accounting.document_flow.payment import (
        apply_advance_to_invoice,
        compute_payment_unallocated_amount,
    )

    defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company=COMPANY)).scalars().first()
    defaults.apply_advances_automatically = True
    database.session.commit()

    invoice = _make_invoice(amount=Decimal("600"))
    _post_invoice(invoice)

    # Cobro parcial de 250 y un segundo cobro de 350 sin aplicar (anticipo).
    partial = _make_payment(amount=Decimal("250"), chart=chart)
    _apply(partial, [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 250}])
    _post_payment(partial)

    overpayment = _make_payment(amount=Decimal("350"), posting_date=date(2026, 8, 21), chart=chart)
    _post_payment(overpayment)

    # Sin referencias el motor contabiliza el cobro como anticipo de cliente.
    assert compute_payment_unallocated_amount(overpayment) == Decimal("350")
    assert _outstanding(invoice) == Decimal("350")

    # Aplicacion posterior del anticipo contra la factura.
    apply_advance_to_invoice(overpayment.id, invoice.id, Decimal("350"), date(2026, 8, 22))
    database.session.commit()

    assert _outstanding(invoice) == Decimal("0")
    assert compute_payment_unallocated_amount(overpayment) == Decimal("0")

    totals = _subledger_totals(date(2026, 8, 23))
    assert totals["paid_amount"] == Decimal("600")
    assert totals["outstanding_amount"] == Decimal("0")

    # El neteo automatico debe dejar la cuenta control AR en cero.
    _assert_ar_reconciled(chart, date(2026, 8, 23))


# --------------------------------------------------------------------------- #
# 3. Credit note + descuento como write-off proxy
# --------------------------------------------------------------------------- #


def test_280_credit_note_and_discount_writeoff_equation(app_ctx, chart):
    """La nota reduce outstanding y el descuento actua como write-off postendo a GL."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import GLEntry, database
    from cacao_accounting.ventas.services import _persist_sales_reversal_relation

    invoice = _make_invoice(amount=Decimal("1000"))
    _post_invoice(invoice)

    credit_note = _make_invoice(
        amount=Decimal("200"),
        posting_date=date(2026, 8, 21),
        document_type="sales_credit_note",
    )
    credit_note.reversal_of = invoice.id
    database.session.commit()
    _persist_sales_reversal_relation(credit_note)
    post_document_to_gl(credit_note)
    database.session.commit()

    # Ecuacion parcial: 1000 - 200 (credit note) - 0 pagos = 800.
    assert _outstanding(invoice) == Decimal("800")

    # Write-off proxy: se liquidan 500 con 480 de efectivo + 20 de descuento.
    discounted = _make_invoice(amount=Decimal("500"), posting_date=date(2026, 8, 22))
    _post_invoice(discounted)
    settlement = _make_payment(amount=Decimal("480"), posting_date=date(2026, 8, 23), chart=chart)
    _apply(
        settlement,
        [
            {
                "reference_type": "sales_invoice",
                "reference_id": discounted.id,
                "allocated_amount": 500,
                "discount_amount": 20,
            }
        ],
        allocation_date=date(2026, 8, 23),
    )
    _post_payment(settlement)

    # Ecuacion sobre la factura descontada: 500 - 0 notas - 500 aplicados = 0,
    # donde 20 son write-off (descuento) y solo 480 consumieron efectivo.
    assert _outstanding(discounted) == Decimal("0")

    discount_rows = (
        database.session.execute(
            select(GLEntry).where(
                GLEntry.company == COMPANY,
                GLEntry.voucher_type == "payment_entry",
                GLEntry.voucher_id == settlement.id,
                GLEntry.account_id == chart["discount_id"],
            )
        )
        .scalars()
        .all()
    )
    assert sum(entry.debit for entry in discount_rows) == Decimal("20")

    totals = _subledger_totals(date(2026, 8, 24))
    # La nota vinculada por reversal_of se excluye de las filas del submayor.
    assert totals["original_amount"] == Decimal("1500")
    assert totals["paid_amount"] == Decimal("500")
    assert totals["outstanding_amount"] == Decimal("800")

    _assert_ar_reconciled(chart, date(2026, 8, 24))


def test_280_refund_settles_credit_note_in_subledger(app_ctx, chart):
    """El refund liquida el saldo abierto de la nota de credito en el subledger."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import GLEntry, database

    credit_note = _make_invoice(
        amount=Decimal("200"),
        document_type="sales_credit_note",
    )
    post_document_to_gl(credit_note)
    database.session.commit()

    refund = _make_payment(amount=Decimal("200"), payment_type="pay", posting_date=date(2026, 8, 21), chart=chart)
    _apply(
        refund,
        [
            {
                "flow_source_type": "sales_credit_note",
                "reference_type": "sales_invoice",
                "reference_id": credit_note.id,
                "allocated_amount": 200,
            }
        ],
        allocation_date=date(2026, 8, 21),
    )
    _post_payment(refund)

    assert _outstanding(credit_note) == Decimal("0")

    # El ciclo completo mantiene el GL balanceado (doble partida).
    entries = database.session.execute(select(GLEntry).where(GLEntry.company == COMPANY)).scalars().all()
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)

    # Trazabilidad: cada documento aporta su voucher al journal.
    for voucher_type, voucher_id in (("sales_invoice", credit_note.id), ("payment_entry", refund.id)):
        rows = (
            database.session.execute(
                select(GLEntry).filter_by(company=COMPANY, voucher_type=voucher_type, voucher_id=voucher_id)
            )
            .scalars()
            .all()
        )
        assert rows, f"Sin GL para {voucher_type} {voucher_id}"


# --------------------------------------------------------------------------- #
# 4. Cancelacion de pago: restauracion de saldos y reversal append-only
# --------------------------------------------------------------------------- #


def test_280_payment_cancellation_restores_active_effect(app_ctx, chart):
    """Cancelar un pago aplicado restaura el saldo y agrega reversos al GL."""
    from cacao_accounting.contabilidad.posting_service import cancel_document
    from cacao_accounting.database import GLEntry, PaymentReference, database

    invoice = _make_invoice(amount=Decimal("1000"))
    _post_invoice(invoice)

    payment = _make_payment(amount=Decimal("400"), chart=chart)
    _apply(payment, [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 400}])
    _post_payment(payment)
    assert _outstanding(invoice) == Decimal("600")
    _assert_ar_reconciled(chart)

    original_entries = (
        database.session.execute(select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )
    original_ids = {entry.id for entry in original_entries}

    cancel_document(payment, **_cancellation_metadata(payment.posting_date))

    database.session.refresh(payment)
    assert payment.docstatus == 2
    # La referencia se conserva como evidencia tras la compensación append-only.
    references = database.session.execute(select(PaymentReference).filter_by(payment_id=payment.id)).scalars().all()
    assert len(references) == 1
    assert _outstanding(invoice) == Decimal("1000")
    reversal_entries = (
        database.session.execute(
            select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id, is_reversal=True)
        )
        .scalars()
        .all()
    )
    assert reversal_entries
    assert original_ids.isdisjoint({entry.id for entry in reversal_entries})


def test_280_posting_and_application_are_idempotent(app_ctx, chart):
    """Re-postear un documento o re-aplicar el mismo pago falla sin duplicar GL."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.contabilidad.posting_service import PostingError
    from cacao_accounting.database import GLEntry, database
    from cacao_accounting.document_flow.service import DocumentFlowError

    invoice = _make_invoice(amount=Decimal("300"))
    _post_invoice(invoice)
    with pytest.raises(PostingError):
        post_document_to_gl(invoice)
    invoice_gl = (
        database.session.execute(select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )
    assert len(invoice_gl) == 2

    payment = _make_payment(amount=Decimal("300"), chart=chart)
    _apply(payment, [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 300}])
    _post_payment(payment)
    with pytest.raises(DocumentFlowError):
        _apply(payment, [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 100}])

    assert _outstanding(invoice) == Decimal("0")
    _assert_ar_reconciled(chart)


# --------------------------------------------------------------------------- #
# 5. Cancelacion de factura: exclusion del subledger y GL oculto
# --------------------------------------------------------------------------- #


def test_280_invoice_cancellation_excluded_from_subledger(app_ctx, chart):
    """Una factura anulada sale del subledger, su par GL se oculta y la matriz cuadra."""
    from cacao_accounting.contabilidad.posting_service import cancel_document
    from cacao_accounting.database import GLEntry, database

    kept = _make_invoice(amount=Decimal("700"))
    _post_invoice(kept)
    removed = _make_invoice(amount=Decimal("300"))
    _post_invoice(removed)

    cancel_document(removed, **_cancellation_metadata(removed.posting_date))
    database.session.commit()

    assert removed.docstatus == 2
    totals = _subledger_totals()
    assert totals["original_amount"] == Decimal("700")
    assert totals["outstanding_amount"] == Decimal("700")

    removed_entries = (
        database.session.execute(select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=removed.id))
        .scalars()
        .all()
    )
    assert len(removed_entries) == 4
    assert any(entry.is_cancelled for entry in removed_entries)
    assert any(entry.is_reversal for entry in removed_entries)

    _assert_ar_reconciled(chart)


# --------------------------------------------------------------------------- #
# 6. Multimoneda, corte temporal y aislamiento por compania
# --------------------------------------------------------------------------- #


def test_280_multicurrency_functional_equation_and_isolation(app_ctx, chart):
    """FX: ecuacion en moneda de transaccion y funcional; aislamiento por compania."""
    from cacao_accounting.database import ExchangeRate, Party, PartyAccount, database

    database.session.add(ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=AS_OF))
    foreign_customer = Party(id="CUST-FX", code="CUST-FX", name="Cliente FX", is_customer=True, is_active=True)
    database.session.add(foreign_customer)
    database.session.flush()
    database.session.add(PartyAccount(party_id="CUST-FX", company=COMPANY, receivable_account_id=chart["ar_id"]))
    database.session.commit()

    usd_invoice = _make_invoice(
        amount=Decimal("100"),
        currency="USD",
        rate=Decimal("36"),
        customer="CUST-FX",
    )
    _post_invoice(usd_invoice)

    # La matriz cuadra en el corte solo-factura (el pago FX se fecha despues:
    # su liquidacion involucra revaluacion no realizada que se reversa en el
    # periodo siguiente y no es parte de la ecuacion de outstanding).
    _assert_ar_reconciled(chart, AS_OF)
    assert _subledger_totals(AS_OF)["outstanding_amount"] == Decimal("3600")

    usd_payment = _make_payment(
        amount=Decimal("40"),
        currency="USD",
        rate=Decimal("36"),
        posting_date=date(2026, 8, 25),
        chart=chart,
        party_id="CUST-FX",
    )
    _apply(
        usd_payment,
        [{"reference_type": "sales_invoice", "reference_id": usd_invoice.id, "allocated_amount": 40}],
        allocation_date=date(2026, 8, 25),
        party_id="CUST-FX",
    )
    _post_payment(usd_payment)

    # Moneda de transaccion: 100 - 40 = 60 USD.
    assert _outstanding(usd_invoice) == Decimal("60")
    # Moneda funcional: 60 * 36 = 2160 NIO.
    assert usd_invoice.base_outstanding_amount == Decimal("2160")

    totals = _subledger_totals(OPEN_END)
    assert totals["outstanding_amount"] == Decimal("2160")

    # Aislamiento de compania: otra empresa no contamina el submayor ni la matriz.
    from cacao_accounting.database import Accounts, Book, CompanyDefaultAccount, Entity, SalesInvoice, database
    from cacao_accounting.reportes.services import ReconciliationFilters, get_reconciliation_matrix

    database.session.add_all(
        [
            Entity(code="otra", name="Otra", company_name="Otra", tax_id="OTRA-1", currency="NIO"),
            Accounts(entity="otra", code="1101", name="CxC", classification="asset"),
        ]
    )
    database.session.flush()
    other_book = Book(entity="otra", code="OTRALOC", name="Libro Otra", currency="NIO", status="activo", is_primary=True)
    database.session.add(other_book)
    database.session.flush()
    other_ar = database.session.execute(select(Accounts).filter_by(entity="otra", code="1101")).scalars().first()
    database.session.add(CompanyDefaultAccount(company="otra", default_receivable=other_ar.id))
    database.session.add(
        SalesInvoice(
            company="otra",
            posting_date=AS_OF,
            customer_id="CUST-O2C",
            document_type="sales_invoice",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=1,
            total=Decimal("9999"),
            grand_total=Decimal("9999"),
            base_total=Decimal("9999"),
            base_grand_total=Decimal("9999"),
            outstanding_amount=Decimal("9999"),
            base_outstanding_amount=Decimal("9999"),
        )
    )
    database.session.commit()

    totals_after = _subledger_totals(OPEN_END)
    assert totals_after["outstanding_amount"] == Decimal("2160")

    other_matrix = get_reconciliation_matrix(ReconciliationFilters(company="otra", ledger="OTRALOC", as_of_date=AS_OF))
    other_row = next(row for row in other_matrix.rows if row.values["area"] == "AR")
    assert other_row.values["subledger_amount"] == Decimal("9999")
    assert other_row.values["gl_control_amount"] == Decimal("0")

    # La matriz de la empresa principal sigue cuadrando en su corte
    # (estado solo-factura; la liquidacion FX se reversa en el periodo siguiente).
    o2c_row = _matrix_row(chart, "AR", AS_OF)
    assert o2c_row.values["subledger_amount"] == Decimal("3600")


def test_280_subledger_columns_share_cutoff_when_no_as_of(app_ctx, chart):
    """Sin corte explicito, paid y outstanding comparten el mismo cutoff."""
    from datetime import timedelta

    invoice = _make_invoice(amount=Decimal("400"), posting_date=date.today())
    _post_invoice(invoice)

    future = date.today() + timedelta(days=10)
    payment = _make_payment(amount=Decimal("150"), chart=chart, posting_date=future)
    _apply(
        payment,
        [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 150}],
        allocation_date=future,
    )
    _post_payment(payment)

    # Sin corte: la aplicacion futura no aparece en paid ni reduce outstanding.
    totals = _subledger_totals(None)
    assert totals["paid_amount"] == Decimal("0")
    assert totals["outstanding_amount"] == Decimal("400")

    # Con corte que incluye la aplicacion ambas columnas son consistentes.
    totals_cut = _subledger_totals(future)
    assert totals_cut["paid_amount"] == Decimal("150")
    assert totals_cut["outstanding_amount"] == Decimal("250")
