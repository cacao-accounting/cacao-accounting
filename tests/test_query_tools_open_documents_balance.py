# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1127: las herramientas de documentos abiertos filtran por saldo vigente.

El estado ``open`` puede quedar desactualizado; una factura liquidada no
debe aparecer como abierta ni inflar el total paginado.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.database import (
    ARAPLedgerEntry,
    Modules,
    Party,
    PurchaseInvoice,
    SalesInvoice,
    database,
)
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.handlers import payables as payables_handlers
from cacao_accounting.query_tools.handlers import receivables as receivables_handlers

CORTE = date(2026, 5, 15)


def _context(permission: str) -> QueryContext:
    """Contexto de servicio con acceso a la compañía del escenario."""
    return QueryContext(
        user_id="tester",
        company_ids=["cacao"],
        permissions={permission},
        is_service_principal=True,
    )


def _ensure_modules() -> None:
    """Habilita los módulos que validan las herramientas."""
    for name in ("sales", "purchases", "accounting"):
        exists = database.session.execute(select(Modules.id).filter_by(module=name)).scalar_one_or_none()
        if exists is None:
            database.session.add(Modules(module=name, default=False, enabled=True))
    database.session.flush()


def _ledger(document, party_type: str, amount: Decimal, event_type: str) -> None:
    """Registra una fila de apertura o aplicación en AR/AP."""
    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="ar" if party_type == "customer" else "ap",
            party_type=party_type,
            party_id=str(document.customer_id if party_type == "customer" else document.supplier_id),
            document_type=str(document.document_type),
            document_id=str(document.id),
            document_no=document.document_no or str(document.id),
            posting_date=CORTE,
            event_type=event_type,
            currency="NIO",
            document_amount=amount,
        )
    )
    database.session.flush()


def _sales_invoice(customer_id: str, number: str, status: str | None = "open") -> SalesInvoice:
    """Crea una factura de venta publicada con el estado indicado."""
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        customer_name="Cliente Principal SA",
        document_no=number,
        document_type="sales_invoice",
        posting_date=CORTE,
        docstatus=1,
        status=status,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _purchase_invoice(supplier_id: str, number: str, status: str | None = "open") -> PurchaseInvoice:
    """Crea una factura de compra publicada con el estado indicado."""
    invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier_id,
        supplier_name="Proveedor Principal SA",
        document_no=number,
        document_type="purchase_invoice",
        posting_date=CORTE,
        docstatus=1,
        status=status,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def test_receivables_omite_facturas_liquidadas_y_pagina_por_saldo(entorno_contable_aislado):
    """Una factura pagada al 100% no aparece; la parcial conserva su saldo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _ensure_modules()
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
        pagada = _sales_invoice(customer_id, "AR-PAGADA")
        _ledger(pagada, "customer", Decimal("100"), "opening")
        _ledger(pagada, "customer", Decimal("-100"), "allocation")
        parcial = _sales_invoice(customer_id, "AR-PARCIAL")
        _ledger(parcial, "customer", Decimal("100"), "opening")
        _ledger(parcial, "customer", Decimal("-40"), "allocation")
        pendiente = _sales_invoice(customer_id, "AR-PENDIENTE")
        _ledger(pendiente, "customer", Decimal("100"), "opening")
        database.session.commit()

        result = receivables_handlers.get_receivables_open_documents.handler(
            context=_context("receivables.reports.read"),
            company_id="cacao",
            page=1,
            page_size=2,
        )

        assert result["total_items"] == 2
        assert result["total_pages"] == 1
        assert [item["document_no"] for item in result["items"]] == ["AR-PARCIAL", "AR-PENDIENTE"]
        outstanding = {item["document_no"]: Decimal(item["outstanding"]) for item in result["items"]}
        assert outstanding == {"AR-PARCIAL": Decimal("60.0000"), "AR-PENDIENTE": Decimal("100.0000")}


def test_receivables_pagina_solo_saldos_positivos(entorno_contable_aislado):
    """La segunda página continúa después de los documentos liquidados."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _ensure_modules()
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
        for number in ("AR-1", "AR-2", "AR-3"):
            invoice = _sales_invoice(customer_id, number)
            _ledger(invoice, "customer", Decimal("100"), "opening")
        cerrada = _sales_invoice(customer_id, "AR-4")
        _ledger(cerrada, "customer", Decimal("100"), "opening")
        _ledger(cerrada, "customer", Decimal("-100"), "allocation")
        database.session.commit()

        result = receivables_handlers.get_receivables_open_documents.handler(
            context=_context("receivables.reports.read"),
            company_id="cacao",
            page=2,
            page_size=2,
        )

        assert result["total_items"] == 3
        assert result["has_next_page"] is False
        assert len(result["items"]) == 1
        assert result["items"][0]["document_no"] == "AR-3"


def test_payables_omite_facturas_liquidadas(entorno_contable_aislado):
    """AP aplica el mismo criterio de saldo vigente que AR."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _ensure_modules()
        supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
        pagada = _purchase_invoice(supplier_id, "AP-PAGADA")
        _ledger(pagada, "supplier", Decimal("100"), "opening")
        _ledger(pagada, "supplier", Decimal("-100"), "allocation")
        abierta = _purchase_invoice(supplier_id, "AP-ABIERTA")
        _ledger(abierta, "supplier", Decimal("100"), "opening")
        database.session.commit()

        result = payables_handlers.get_payables_open_documents.handler(
            context=_context("payables.reports.read"),
            company_id="cacao",
            page=1,
            page_size=100,
        )

        assert result["total_items"] == 1
        assert [item["document_no"] for item in result["items"]] == ["AP-ABIERTA"]
        assert Decimal(result["items"][0]["outstanding"]) == Decimal("100.0000")


def test_receivables_incluye_facturas_sin_estado_heredado(entorno_contable_aislado):
    """Una factura contabilizada con status NULL aparece por su saldo real."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _ensure_modules()
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
        invoice = _sales_invoice(customer_id, "AR-SIN-ESTADO", status=None)
        _ledger(invoice, "customer", Decimal("100"), "opening")
        database.session.commit()

        result = receivables_handlers.get_receivables_open_documents.handler(
            context=_context("receivables.reports.read"),
            company_id="cacao",
            page=1,
            page_size=100,
        )

        assert [item["document_no"] for item in result["items"]] == ["AR-SIN-ESTADO"]
        assert Decimal(result["items"][0]["outstanding"]) == Decimal("100.0000")
        assert result["total_items"] == 1


def test_payables_incluye_facturas_sin_estado_heredado(entorno_contable_aislado):
    """AP aplica el mismo criterio de saldo real sin depender del estado."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _ensure_modules()
        supplier_id = str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())
        invoice = _purchase_invoice(supplier_id, "AP-SIN-ESTADO", status=None)
        _ledger(invoice, "supplier", Decimal("100"), "opening")
        database.session.commit()

        result = payables_handlers.get_payables_open_documents.handler(
            context=_context("payables.reports.read"),
            company_id="cacao",
            page=1,
            page_size=100,
        )

        assert [item["document_no"] for item in result["items"]] == ["AP-SIN-ESTADO"]
        assert result["total_items"] == 1
