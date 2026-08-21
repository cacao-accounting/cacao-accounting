# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Suite AUDIT-003 (issue #278): matriz completa realized/unrealized FX de AR/AP.

Ejerce el ciclo cambiario completo en dos libros funcionales (NIO y EUR) con
documentos en USD, usando ``Decimal`` y valores esperados calculados a mano
(fuera de los servicios):

    Factura AR/AP 100 USD @36.50 -> pago parcial 40 @36.80 -> cierre con tasa
    de cierre -> reversa no realizada al periodo siguiente -> liquidacion
    final con realized FX exacto -> saldo AR/AP en cero.

Criterios de aceptacion cubiertos:
- La diferencia funcional queda exactamente en realized/unrealized FX.
- AR/AP final queda en cero cuando se liquida completamente.
- No se duplica FX al reabrir o repetir el job de revaluacion.
- Resultados independientes calculados fuera del servicio.

Convenciones de calculo manual usadas en las aserciones (libro NIO):

    factura   : Dr AR 100 * 36.50 = 3650.0000
    pago 1    : Cr AR 40 * 36.50 = 1460.0000 (valor historico liberado)
                Dr banco 40 * 36.80 = 1472.0000
                realizado  40 * (36.80 - 36.50) = 12.0000
                no realizado (100 - 40) * 36.80 - (3650 - 1460) = 18.0000
    cierre may: (3650 - 1460 + 18) -> 60 * 37.50 = 2250; ajuste +42.0000
    reversa jun: -42.0000 al primer dia del periodo siguiente
    reval jun : 60 * 37.00 - 2208 = +12.0000
    pago 2    : Cr AR valor en libros vigente; realizado contra ese valor.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

COMPANY = "fx"
CUSTOMER = "CUST-FX"
SUPPLIER = "SUPP-FX"

RATE_INVOICE_NIO = Decimal("36.50")
RATE_INVOICE_EUR = Decimal("0.90")
RATE_PAY1_NIO = Decimal("36.80")
RATE_PAY1_EUR = Decimal("0.905")
RATE_CLOSE_NIO = Decimal("37.50")
RATE_CLOSE_EUR = Decimal("0.92")
RATE_JUN_NIO = Decimal("37.00")
RATE_JUN_EUR = Decimal("0.91")
RATE_PAY2_NIO = Decimal("38.00")
RATE_PAY2_EUR = Decimal("0.94")


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
                Entity(code=COMPANY, name="FX", company_name="FX SA", tax_id="FX-1", currency="NIO"),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dolares", decimals=2, active=True),
                Currency(code="EUR", name="Euros", decimals=2, active=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def chart(app_ctx):
    """Catalogo multilibro: NIO funcional + EUR, cuentas FX realizadas y no realizadas."""
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        Book,
        CompanyDefaultAccount,
        ExchangeRate,
        PartyAccount,
        database,
    )

    def _account(code: str, name: str, classification: str, account_type: str | None = None):
        return Accounts(
            entity=COMPANY,
            code=code,
            name=name,
            active=True,
            enabled=True,
            classification=classification,
            account_type=account_type,
        )

    ar = _account("1105", "Clientes", "asset", "receivable")
    ap = _account("2105", "Proveedores", "liability", "payable")
    income = _account("4000", "Ingresos", "income", "income")
    expense = _account("6001", "Gastos de operacion", "expense")
    bank = _account("1005", "Banco", "asset", "bank")
    gain = _account("4205", "Ganancia cambiaria realizada", "income", "exchange_gain")
    loss = _account("5205", "Perdida cambiaria realizada", "expense", "exchange_loss")
    unreal_gain = _account("4210", "Ganancia cambiaria no realizada", "income", "unrealized_exchange_gain")
    unreal_loss = _account("5210", "Perdida cambiaria no realizada", "expense", "unrealized_exchange_loss")
    book_nio = Book(code="NIO", name="Libro NIO", entity=COMPANY, currency="NIO", status="activo", is_primary=True)
    book_eur = Book(code="EUR", name="Libro EUR", entity=COMPANY, currency="EUR", status="activo")
    database.session.add_all([ar, ap, income, expense, bank, gain, loss, unreal_gain, unreal_loss, book_nio, book_eur])
    database.session.flush()
    database.session.add_all(
        [
            CompanyDefaultAccount(
                company=COMPANY,
                default_receivable=ar.id,
                default_payable=ap.id,
                default_income=income.id,
                default_expense=expense.id,
                default_bank=bank.id,
                exchange_gain_account_id=gain.id,
                exchange_loss_account_id=loss.id,
                unrealized_exchange_gain_account_id=unreal_gain.id,
                unrealized_exchange_loss_account_id=unreal_loss.id,
            ),
            PartyAccount(party_id=CUSTOMER, company=COMPANY, receivable_account_id=ar.id),
            PartyAccount(party_id=SUPPLIER, company=COMPANY, payable_account_id=ap.id),
            AccountingPeriod(
                entity=COMPANY,
                name="2026-05",
                enabled=True,
                is_closed=False,
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
            ),
            AccountingPeriod(
                entity=COMPANY,
                name="2026-06",
                enabled=True,
                is_closed=False,
                start=date(2026, 6, 1),
                end=date(2026, 6, 30),
            ),
            ExchangeRate(origin="USD", destination="NIO", rate=RATE_INVOICE_NIO, date=date(2026, 5, 1)),
            ExchangeRate(origin="USD", destination="EUR", rate=RATE_INVOICE_EUR, date=date(2026, 5, 1)),
            ExchangeRate(origin="USD", destination="NIO", rate=RATE_PAY1_NIO, date=date(2026, 5, 15)),
            ExchangeRate(origin="USD", destination="EUR", rate=RATE_PAY1_EUR, date=date(2026, 5, 15)),
            ExchangeRate(origin="USD", destination="NIO", rate=RATE_CLOSE_NIO, date=date(2026, 5, 31)),
            ExchangeRate(origin="USD", destination="EUR", rate=RATE_CLOSE_EUR, date=date(2026, 5, 31)),
            ExchangeRate(origin="USD", destination="NIO", rate=RATE_JUN_NIO, date=date(2026, 6, 20)),
            ExchangeRate(origin="USD", destination="EUR", rate=RATE_JUN_EUR, date=date(2026, 6, 20)),
        ]
    )
    database.session.commit()
    return {
        "ar": ar.id,
        "ap": ap.id,
        "bank": bank.id,
        "expense": expense.id,
        "gain": gain.id,
        "loss": loss.id,
        "unreal_gain": unreal_gain.id,
        "unreal_loss": unreal_loss.id,
    }


def _book_id(code: str) -> str:
    from cacao_accounting.database import Book

    return str(database.session.execute(select(Book).filter_by(entity=COMPANY, code=code)).scalar_one().id)


def _net(account_id: str, ledger: str, *, voucher_type: str | None = None, until: date | None = None) -> Decimal:
    """Saldo deudor neto de una cuenta en un libro, excluyendo pares anulados."""
    from cacao_accounting.database import GLEntry
    from cacao_accounting.ledger_queries import exclude_cancelled_gl_entries

    query = exclude_cancelled_gl_entries(
        select(database.func.coalesce(database.func.sum(GLEntry.debit - GLEntry.credit), 0))
    ).where(GLEntry.company == COMPANY, GLEntry.account_id == account_id, GLEntry.ledger_id == _book_id(ledger))
    if voucher_type:
        query = query.where(GLEntry.voucher_type == voucher_type)
    if until is not None:
        query = query.where(GLEntry.posting_date <= until)
    return database.session.execute(query).scalar_one()


def _credit_balance(account_id: str, ledger: str, **kwargs) -> Decimal:
    """Saldo acreedor neto (para cuentas de resultado y pasivos)."""
    return -_net(account_id, ledger, **kwargs)


def _make_sales_invoice(amount: Decimal = Decimal("100")):
    """Factura de venta 100 USD aprobada y contabilizada en ambos libros."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import SalesInvoice, SalesInvoiceItem, database

    invoice = SalesInvoice(
        company=COMPANY,
        posting_date=date(2026, 5, 1),
        customer_id=CUSTOMER,
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=RATE_INVOICE_NIO,
        docstatus=1,
        total=amount,
        grand_total=amount,
        base_total=amount * RATE_INVOICE_NIO,
        base_grand_total=amount * RATE_INVOICE_NIO,
        outstanding_amount=amount,
        base_outstanding_amount=amount * RATE_INVOICE_NIO,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="SVC-FX",
            qty=Decimal("1"),
            rate=amount,
            amount=amount,
            base_amount=amount * RATE_INVOICE_NIO,
        )
    )
    database.session.commit()
    post_document_to_gl(invoice)
    database.session.commit()
    return invoice


def _make_purchase_invoice(amount: Decimal = Decimal("100")):
    """Factura de compra 100 USD aprobada y contabilizada en ambos libros."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, PurchaseInvoice, PurchaseInvoiceItem, database

    invoice = PurchaseInvoice(
        company=COMPANY,
        supplier_id=SUPPLIER,
        posting_date=date(2026, 5, 1),
        document_type="purchase_invoice",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=RATE_INVOICE_NIO,
        docstatus=1,
        total=amount,
        grand_total=amount,
        base_total=amount * RATE_INVOICE_NIO,
        base_grand_total=amount * RATE_INVOICE_NIO,
        outstanding_amount=amount,
        base_outstanding_amount=amount * RATE_INVOICE_NIO,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="INS-FX",
            item_name="Insumo",
            qty=Decimal("1"),
            uom="UND",
            rate=amount,
            amount=amount,
            expense_account_id=database.session.execute(select(Accounts).filter_by(entity=COMPANY, code="6001"))
            .scalars()
            .one()
            .id,
        )
    )
    database.session.commit()
    post_document_to_gl(invoice)
    database.session.commit()
    return invoice


def _settle(document, amount: Decimal, rate_nio: Decimal, rate_eur: Decimal, day: date, *, pay: bool) -> None:
    """Aplica un cobro/pago parcial contra el documento y lo contabiliza."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import PaymentEntry, database
    from cacao_accounting.document_flow.payment import apply_payment_reconciliation

    is_customer = not pay
    payment = PaymentEntry(
        company=COMPANY,
        posting_date=day,
        payment_type="receive" if is_customer else "pay",
        party_type="customer" if is_customer else "supplier",
        party_id=CUSTOMER if is_customer else SUPPLIER,
        transaction_currency="USD",
        base_currency="NIO",
        currency="USD",
        exchange_rate=rate_nio,
        received_amount=amount if is_customer else None,
        paid_amount=None if is_customer else amount,
        base_received_amount=amount * rate_nio if is_customer else None,
        base_paid_amount=None if is_customer else amount * rate_nio,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()
    reference_type = "sales_invoice" if isinstance(getattr(document, "customer_id", None), str) else "purchase_invoice"
    apply_payment_reconciliation(
        company=COMPANY,
        party_type="customer" if is_customer else "supplier",
        party_id=CUSTOMER if is_customer else SUPPLIER,
        allocation_date=day,
        lines=[
            {
                "payment_id": payment.id,
                "reference_type": reference_type,
                "reference_id": document.id,
                "allocated_amount": amount,
            }
        ],
    )
    post_document_to_gl(payment)
    database.session.commit()


# --------------------------------------------------------------------------- #
# 1. Regresion del fix: el saldo abierto usa el valor en libros previo
# --------------------------------------------------------------------------- #


def test_open_balance_uses_pre_allocation_carrying_including_offsets(app_ctx, chart):
    """El estimado de saldo abierto es el valor en libros, no el prorrateo historico."""
    from cacao_accounting.accounting_engine.document_builders import _estimated_company_open_balance
    from cacao_accounting.accounting_engine.gl_posting_builder import _reference_carrying_in_ledger

    invoice = _make_sales_invoice()
    _settle(invoice, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=False)

    from types import SimpleNamespace

    from cacao_accounting.database import PaymentReference

    stored = database.session.execute(select(PaymentReference)).scalars().first()
    # Sonda de una liquidacion hipotetica: distinto pago, mismo documento abierto.
    probe = SimpleNamespace(
        payment_id="probe-payment-2",
        company=COMPANY,
        reference_type=stored.reference_type,
        reference_id=stored.reference_id,
        party_id=stored.party_id,
        outstanding_amount=Decimal("60"),
    )

    # Calculo independiente: 3650 - 1460 + 18 = 2208.0000 (incluye el par no realizado).
    assert _estimated_company_open_balance([probe], Decimal("60"), Decimal("60")) == Decimal("2208.0000")

    # Camino por libro: el libro EUR lleva su propio valor en libros.
    eur_carrying = _reference_carrying_in_ledger(probe, "EUR", "NIO", _book_id("EUR"))
    # Calculo independiente EUR: 90 - 36 + 0.30 = 54.3000.
    assert eur_carrying == Decimal("54.3000")


def test_ar_sequential_partial_settlements_exact_fx_and_zero_balance(app_ctx, chart):
    """Pagos parciales AR a tasas distintas: FX exacto y AR final en cero."""
    invoice = _make_sales_invoice()

    # Salidos iniciales: Dr AR 3650.0000 (NIO) / 90.0000 (EUR).
    assert _net(chart["ar"], "NIO") == Decimal("3650.0000")
    assert _net(chart["ar"], "EUR") == Decimal("90.0000")

    _settle(invoice, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=False)

    # Pago 1 NIO: realizado 12.0000, no realizado 18.0000, AR 2208.0000.
    assert _credit_balance(chart["gain"], "NIO") == Decimal("12.0000")
    assert _credit_balance(chart["unreal_gain"], "NIO") == Decimal("18.0000")
    assert _net(chart["loss"], "NIO") == Decimal("0.0000")
    assert _net(chart["ar"], "NIO") == Decimal("2208.0000")
    # Pago 1 EUR: realizado 0.2000, no realizado 0.3000, AR 54.3000.
    assert _credit_balance(chart["gain"], "EUR") == Decimal("0.2000")
    assert _credit_balance(chart["unreal_gain"], "EUR") == Decimal("0.3000")
    assert _net(chart["ar"], "EUR") == Decimal("54.3000")

    _settle(invoice, Decimal("60"), RATE_PAY2_NIO, RATE_PAY2_EUR, date(2026, 6, 20), pay=False)

    # Pago 2 NIO: libera 2208.0000, efectivo 60*38.00 = 2280.0000 -> realizado +72.0000.
    assert _net(chart["ar"], "NIO") == Decimal("0.0000")
    assert _credit_balance(chart["gain"], "NIO") == Decimal("84.0000")
    # Pago 2 EUR: libera 54.3000; el libro no funcional valora el efectivo con la
    # tabla en la fecha del pago: 60*0.91 = 54.6000 -> realizado +0.3000.
    assert _net(chart["ar"], "EUR") == Decimal("0.0000")
    assert _credit_balance(chart["gain"], "EUR") == Decimal("0.5000")

    # Verificacion economica independiente por libro:
    # NIO: efectivo 1472 + 2280 = 3752 contra libro 3650 -> utilidad 102;
    # P&L: realizado 84 + no realizado 18 = 102.
    assert _credit_balance(chart["gain"], "NIO") + _credit_balance(chart["unreal_gain"], "NIO") == Decimal("102.0000")
    # EUR: efectivo 36.2 + 54.6 = 90.8 contra libro 90 -> utilidad 0.8.
    assert _credit_balance(chart["gain"], "EUR") + _credit_balance(chart["unreal_gain"], "EUR") == Decimal("0.8000")

    # Doble partida global en cada libro.
    from cacao_accounting.database import GLEntry

    for ledger in ("NIO", "EUR"):
        entries = (
            database.session.execute(select(GLEntry).where(GLEntry.company == COMPANY, GLEntry.ledger_id == _book_id(ledger)))
            .scalars()
            .all()
        )
        assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)


def test_ap_bill_mirrors_ar_cycle_exact_fx(app_ctx, chart):
    """Bill AP equivalente: perdidas/ganancias espejo y AP final en cero."""
    bill = _make_purchase_invoice()

    # Cr AP 3650.0000 (NIO) / 90.0000 (EUR).
    assert _credit_balance(chart["ap"], "NIO") == Decimal("3650.0000")
    assert _credit_balance(chart["ap"], "EUR") == Decimal("90.0000")

    _settle(bill, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=True)

    # Pago 1 NIO: pagar a tasa mayor es perdida realizada 12.0000 y
    # pasivo no realizado 18.0000; AP remedida a 2208.0000.
    assert _net(chart["loss"], "NIO") == Decimal("12.0000")
    assert _net(chart["unreal_loss"], "NIO") == Decimal("18.0000")
    assert _credit_balance(chart["ap"], "NIO") == Decimal("2208.0000")
    # Pago 1 EUR: perdida 0.2000, no realizada 0.3000, AP 54.3000.
    assert _net(chart["loss"], "EUR") == Decimal("0.2000")
    assert _net(chart["unreal_loss"], "EUR") == Decimal("0.3000")
    assert _credit_balance(chart["ap"], "EUR") == Decimal("54.3000")

    _settle(bill, Decimal("60"), RATE_PAY2_NIO, RATE_PAY2_EUR, date(2026, 6, 20), pay=True)

    assert _credit_balance(chart["ap"], "NIO") == Decimal("0.0000")
    assert _credit_balance(chart["ap"], "EUR") == Decimal("0.0000")
    # Realizado NIO acumulado: perdida 12 + perdida 72 = 84; economico:
    # efectivo 1472 + 2280 = 3752 contra libro 3650 -> costo extra 102
    # = perdidas 84 + no realizado 18.
    assert (
        _credit_balance(chart["gain"], "NIO")
        - _net(chart["loss"], "NIO")
        + _credit_balance(chart["unreal_gain"], "NIO")
        - _net(chart["unreal_loss"], "NIO")
    ) == Decimal("-102.0000")
    # EUR: perdidas 0.2 + 0.3 + no realizado 0.3 = costo extra 0.8.
    assert (
        _credit_balance(chart["gain"], "EUR")
        - _net(chart["loss"], "EUR")
        + _credit_balance(chart["unreal_gain"], "EUR")
        - _net(chart["unreal_loss"], "EUR")
    ) == Decimal("-0.8000")


# --------------------------------------------------------------------------- #
# 2. Cierre con tasa de cierre sobre partidas abiertas
# --------------------------------------------------------------------------- #


def test_closing_revaluation_measures_gl_carrying_not_historical_proportion(app_ctx, chart):
    """La revaluacion mide el valor en libros (incluye pares de pagos), sin duplicar."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService

    invoice = _make_sales_invoice()
    _settle(invoice, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=False)

    run = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=5, user_id="admin")

    assert run.status == "posted"
    # total_gain resume el libro funcional de la entidad (NIO): ajuste +42.0000.
    assert run.total_gain == Decimal("42.0000")
    assert run.total_loss == Decimal("0.0000")
    # Calculo independiente: AR 2208 -> 60 * 37.50 = 2250; ajuste +42.0000 (NIO)
    # y 54.30 -> 60 * 0.92 = 55.20; ajuste +0.9000 (EUR).
    assert _net(chart["ar"], "NIO", voucher_type="exchange_revaluation") == Decimal("42.0000")
    assert _net(chart["ar"], "EUR", voucher_type="exchange_revaluation") == Decimal("0.9000")
    assert _net(chart["ar"], "NIO") == Decimal("2250.0000")
    assert _net(chart["ar"], "EUR") == Decimal("55.2000")

    # Reejecutar el job del mismo periodo anula y recalcula sin duplicar FX.
    rerun = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=5, user_id="admin")
    assert rerun.status == "posted"
    assert rerun.id != run.id
    assert run.status == "voided"
    assert _net(chart["ar"], "NIO", voucher_type="exchange_revaluation") == Decimal("42.0000")
    assert _net(chart["ar"], "NIO") == Decimal("2250.0000")
    assert _credit_balance(chart["unreal_gain"], "NIO", voucher_type="exchange_revaluation") == Decimal("42.0000")


# --------------------------------------------------------------------------- #
# 3. Reversa del periodo siguiente y liquidacion posterior exacta
# --------------------------------------------------------------------------- #


def test_next_period_reverses_unrealized_and_final_settlement_is_exact(app_ctx, chart):
    """Junio revierte el ajuste de mayo el dia 1 y el cierre final es exacto."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import GLEntry

    invoice = _make_sales_invoice()
    _settle(invoice, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=False)
    may_run = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=5, user_id="admin")
    assert _net(chart["ar"], "NIO") == Decimal("2250.0000")

    june_run = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=6, user_id="admin")

    # La corrida de mayo quedo anulada por la reversa automatica.
    assert may_run.status == "voided"
    assert june_run.status == "posted"
    reversals = (
        database.session.execute(
            select(GLEntry).where(
                GLEntry.voucher_type == "exchange_revaluation",
                GLEntry.voucher_id == may_run.id,
                GLEntry.is_reversal.is_(True),
                GLEntry.is_cancelled.is_(False),
            )
        )
        .scalars()
        .all()
    )
    assert {entry.posting_date for entry in reversals} == {date(2026, 6, 1)}

    # Estado tras reversa + nueva medicion de junio (tasas de tabla al 20/jun):
    # AR NIO: 2250 - 42 (reversa) + 12 (60 * 37.00 - 2208) = 2220.0000.
    assert _net(chart["ar"], "NIO") == Decimal("2220.0000")
    # AR EUR: 55.20 - 0.90 + 0.30 (60 * 0.91 - 54.30) = 54.6000.
    assert _net(chart["ar"], "EUR") == Decimal("54.6000")
    assert _net(chart["ar"], "NIO", voucher_type="exchange_revaluation") == Decimal("12.0000")

    # El pago final usa su propia tasa documentaria (38.00) en la fecha de
    # tabla de junio; el libro funcional la aplica al efectivo y el libro EUR
    # valora el efectivo con la tabla (0.91).
    _settle(invoice, Decimal("60"), RATE_PAY2_NIO, RATE_PAY2_EUR, date(2026, 6, 20), pay=False)

    # Liquidacion posterior: libera el valor en libros vigente 2220.0000,
    # efectivo 60 * 38.00 = 2280.0000 -> realizado exacto +60.0000 (NIO).
    assert _net(chart["ar"], "NIO") == Decimal("0.0000")
    assert _credit_balance(chart["gain"], "NIO") == Decimal("72.0000")
    # EUR: libera 54.6000; efectivo con tabla del 20/jun: 60 * 0.91 = 54.6000
    # -> realizado 0.0000 (la revaluacion ya reconocio la diferencia).
    assert _net(chart["ar"], "EUR") == Decimal("0.0000")
    assert _credit_balance(chart["gain"], "EUR") == Decimal("0.2000")

    # Conciliacion economica final por libro (calculada fuera del servicio):
    # NIO: efectivo 3752 - libro 3650 = 102 = realizado 72 + no realizado neto 30.
    assert _credit_balance(chart["unreal_gain"], "NIO") == Decimal("30.0000")
    assert _credit_balance(chart["gain"], "NIO") + _credit_balance(chart["unreal_gain"], "NIO") == Decimal("102.0000")
    # EUR: efectivo 90.8 - libro 90 = 0.8 = realizado 0.2 + no realizado neto 0.6.
    assert _credit_balance(chart["unreal_gain"], "EUR") == Decimal("0.6000")
    assert _credit_balance(chart["gain"], "EUR") + _credit_balance(chart["unreal_gain"], "EUR") == Decimal("0.8000")


def test_revaluation_job_rerun_after_reversal_does_not_duplicate_fx(app_ctx, chart):
    """Repetir el job de junio conserva una sola corrida activa y el mismo ajuste."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import (
        EXCHANGE_REVALUATION_STATUS_POSTED,
        ExchangeRevaluationService,
    )
    from cacao_accounting.database import ExchangeRevaluation

    invoice = _make_sales_invoice()
    _settle(invoice, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=False)
    ExchangeRevaluationService().run(company=COMPANY, year=2026, month=5, user_id="admin")

    first = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=6, user_id="admin")
    second = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=6, user_id="admin")

    assert first.status == "voided"
    assert second.status == "posted"
    posted_june = (
        database.session.execute(
            select(ExchangeRevaluation).where(
                ExchangeRevaluation.company == COMPANY,
                ExchangeRevaluation.year == 2026,
                ExchangeRevaluation.month == 6,
                ExchangeRevaluation.status == EXCHANGE_REVALUATION_STATUS_POSTED,
            )
        )
        .scalars()
        .all()
    )
    assert len(posted_june) == 1
    # Ajuste neto estable: reversa de mayo (-42) + medicion junio (+12) = -30
    # sobre las corridas; el AR permanece en 2220.0000.
    assert _net(chart["ar"], "NIO", voucher_type="exchange_revaluation") == Decimal("12.0000")
    assert _net(chart["ar"], "NIO") == Decimal("2220.0000")
    # total_gain resume el libro funcional (NIO): +12.0000 de junio.
    assert second.total_gain == Decimal("12.0000")

    # La liquidacion final tras repetir el job tambien cierra en cero.
    _settle(invoice, Decimal("60"), RATE_PAY2_NIO, RATE_PAY2_EUR, date(2026, 6, 20), pay=False)
    assert _net(chart["ar"], "NIO") == Decimal("0.0000")
    assert _net(chart["ar"], "EUR") == Decimal("0.0000")


def test_partial_settlement_after_closing_keeps_matrix_balanced(app_ctx, chart):
    """La matriz cuadra antes del pago FX y el GL compone con los ajustes."""
    from cacao_accounting.reportes.services import ReconciliationFilters, get_reconciliation_matrix

    invoice = _make_sales_invoice()

    # Corte solo-factura: la igualdad submayor/control GL es estricta.
    matrix = get_reconciliation_matrix(ReconciliationFilters(company=COMPANY, ledger="NIO", as_of_date=date(2026, 5, 10)))
    ar_row = next(row for row in matrix.rows if row.values.get("area") == "AR")
    assert ar_row.values["difference"] == Decimal("0")

    _settle(invoice, Decimal("40"), RATE_PAY1_NIO, RATE_PAY1_EUR, date(2026, 5, 15), pay=False)

    # Tras un pago FX el control GL queda remedido por el par no realizado:
    # submayor 60 * 36.50 = 2190 + offset 18 = GL 2208. La igualdad estricta
    # de la matriz se verifica al corte anterior al pago FX (invariante
    # documentada de la suite O2C).
    assert _net(chart["ar"], "NIO") == Decimal("2208.0000")

    database.session.refresh(invoice)
    assert invoice.base_outstanding_amount == Decimal("2190.00")
    assert _net(chart["ar"], "NIO") == invoice.base_outstanding_amount + Decimal("18.0000")
