# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de cierre para identificadores documentales y pagos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import importlib
from inspect import unwrap

import pytest
from werkzeug.exceptions import Conflict

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


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
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao",
                tax_id="J0001",
                currency="NIO",
            )
        )
        database.session.add(
            Entity(
                code="cafe",
                name="Cafe",
                company_name="Cafe",
                tax_id="J0002",
                currency="USD",
            )
        )
        database.session.commit()
        yield app


def _transaction_documents() -> list[tuple[object, str, str]]:
    """Devuelve documentos transaccionales mínimos por tipo documental."""

    from cacao_accounting.database import (
        DeliveryNote,
        PaymentEntry,
        PurchaseInvoice,
        PurchaseOrder,
        PurchaseQuotation,
        PurchaseReceipt,
        PurchaseRequest,
        SalesInvoice,
        SalesOrder,
        SalesQuotation,
        SalesRequest,
        StockEntry,
        SupplierQuotation,
    )

    return [
        (PurchaseRequest(company="cacao", posting_date=date(2026, 5, 4)), "purchase_request", "PREQ"),
        (PurchaseQuotation(company="cacao", posting_date=date(2026, 5, 4)), "purchase_quotation", "RFQ"),
        (SupplierQuotation(company="cacao", posting_date=date(2026, 5, 4)), "supplier_quotation", "SPQ"),
        (PurchaseOrder(company="cacao", posting_date=date(2026, 5, 4)), "purchase_order", "PO"),
        (PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 4)), "purchase_receipt", "PR"),
        (PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 4)), "purchase_invoice", "PI"),
        (SalesRequest(company="cacao", posting_date=date(2026, 5, 4)), "sales_request", "SR"),
        (SalesQuotation(company="cacao", posting_date=date(2026, 5, 4)), "sales_quotation", "SQ"),
        (SalesOrder(company="cacao", posting_date=date(2026, 5, 4)), "sales_order", "SO"),
        (DeliveryNote(company="cacao", posting_date=date(2026, 5, 4)), "delivery_note", "DN"),
        (SalesInvoice(company="cacao", posting_date=date(2026, 5, 4)), "sales_invoice", "SI"),
        (PaymentEntry(company="cacao", posting_date=date(2026, 5, 4), payment_type="pay"), "payment_entry", "PAY"),
        (
            StockEntry(company="cacao", posting_date=date(2026, 5, 4), purpose="material_receipt"),
            "stock_entry",
            "STE",
        ),
    ]


def test_transaction_documents_receive_bootstrapped_identifiers(app_ctx):
    """Todos los documentos operativos cubiertos generan serie e identificador."""

    from cacao_accounting.database import GeneratedIdentifierLog, NamingSeries, database
    from cacao_accounting.document_identifiers import assign_document_identifier

    for document, entity_type, code in _transaction_documents():
        database.session.add(document)
        database.session.flush()

        assign_document_identifier(
            document=document,
            entity_type=entity_type,
            posting_date_raw=document.posting_date,
            naming_series_id=None,
        )

        assert document.naming_series_id
        assert document.document_no
        assert document.document_no.startswith(f"cacao-{code}-2026-05-")

        series = database.session.get(NamingSeries, document.naming_series_id)
        assert series is not None
        assert series.company == "cacao"
        assert series.entity_type == entity_type

        log = database.session.execute(
            database.select(GeneratedIdentifierLog).filter_by(full_identifier=document.document_no)
        ).scalar_one_or_none()
        assert log is not None
        assert log.company == "cacao"
        assert log.posting_date == date(2026, 5, 4)


def test_identifier_rejects_closed_accounting_period(app_ctx):
    """La fecha de contabilización no puede caer en un periodo cerrado."""

    from cacao_accounting.database import AccountingPeriod, PurchaseInvoice, database
    from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier

    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 4))
    database.session.add_all(
        [
            AccountingPeriod(
                entity="cacao",
                name="Mayo 2026",
                is_closed=True,
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
            ),
            invoice,
        ]
    )
    database.session.flush()

    with pytest.raises(IdentifierConfigurationError, match="periodo contable cerrado"):
        assign_document_identifier(
            document=invoice,
            entity_type="purchase_invoice",
            posting_date_raw=invoice.posting_date,
            naming_series_id=None,
        )


def test_identifier_rejects_incompatible_or_cross_company_series(app_ctx):
    """La serie elegida debe pertenecer al tipo documental y a la compañia."""

    from cacao_accounting.database import NamingSeries, PurchaseInvoice, database
    from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier

    wrong_type = NamingSeries(
        name="Serie Venta",
        entity_type="sales_invoice",
        company="cacao",
        prefix_template="*COMP*-SI-",
        is_active=True,
    )
    other_company = NamingSeries(
        name="Serie Cafe",
        entity_type="purchase_invoice",
        company="cafe",
        prefix_template="*COMP*-PI-",
        is_active=True,
    )
    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 4))
    database.session.add_all([wrong_type, other_company, invoice])
    database.session.flush()

    with pytest.raises(IdentifierConfigurationError, match="tipo de documento"):
        assign_document_identifier(
            document=invoice,
            entity_type="purchase_invoice",
            posting_date_raw=invoice.posting_date,
            naming_series_id=wrong_type.id,
        )

    with pytest.raises(IdentifierConfigurationError, match="compania indicada"):
        assign_document_identifier(
            document=invoice,
            entity_type="purchase_invoice",
            posting_date_raw=invoice.posting_date,
            naming_series_id=other_company.id,
        )


def test_payment_references_update_purchase_and_sales_invoice_balances(app_ctx):
    """Un pago puede asignarse parcialmente a facturas AP y AR."""

    from cacao_accounting.bancos import _save_payment_references
    from cacao_accounting.database import PaymentEntry, PaymentReference, PurchaseInvoice, SalesInvoice, database

    purchase_invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        grand_total=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
    )
    sales_invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        grand_total=Decimal("80.00"),
        outstanding_amount=Decimal("80.00"),
    )
    payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="pay")
    database.session.add_all([purchase_invoice, sales_invoice, payment])
    database.session.flush()

    data = {
        "reference_type_0": "purchase_invoice",
        "reference_id_0": purchase_invoice.id,
        "allocated_amount_0": "25.00",
        "reference_type_1": "sales_invoice",
        "reference_id_1": sales_invoice.id,
        "allocated_amount_1": "15.00",
    }
    with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=data):
        allocated = _save_payment_references(payment)

    references = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment.id)).scalars().all()

    assert allocated == Decimal("40.00")
    assert len(references) == 2
    assert purchase_invoice.outstanding_amount == Decimal("75.00")
    assert sales_invoice.outstanding_amount == Decimal("65.00")
    assert {reference.allocation_date for reference in references} == {date(2026, 5, 5)}


def test_payment_references_reject_cross_company_invoice(app_ctx):
    """Una referencia de pago no puede cruzar compañias."""

    from cacao_accounting.bancos import _save_payment_references
    from cacao_accounting.database import PaymentEntry, PurchaseInvoice, database

    invoice = PurchaseInvoice(
        company="cafe",
        posting_date=date(2026, 5, 4),
        grand_total=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
    )
    payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="pay")
    database.session.add_all([invoice, payment])
    database.session.flush()

    data = {
        "reference_type_0": "purchase_invoice",
        "reference_id_0": invoice.id,
        "allocated_amount_0": "25.00",
    }
    with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=data):
        with pytest.raises(Conflict):
            _save_payment_references(payment)


def test_payment_references_reject_duplicate_and_negative_allocations(app_ctx):
    """Las referencias de pago rechazan duplicados y montos negativos."""

    from cacao_accounting.bancos import _save_payment_references
    from cacao_accounting.database import PaymentEntry, PurchaseInvoice, database

    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        grand_total=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
    )
    payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="pay")
    database.session.add_all([invoice, payment])
    database.session.flush()
    database.session.commit()

    duplicate_data = {
        "reference_type_0": "purchase_invoice",
        "reference_id_0": invoice.id,
        "allocated_amount_0": "25.00",
        "reference_type_1": "purchase_invoice",
        "reference_id_1": invoice.id,
        "allocated_amount_1": "10.00",
    }
    with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=duplicate_data):
        with pytest.raises(Conflict):
            _save_payment_references(payment)
    database.session.rollback()

    negative_data = {
        "reference_type_0": "purchase_invoice",
        "reference_id_0": invoice.id,
        "allocated_amount_0": "-1.00",
    }
    with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=negative_data):
        with pytest.raises(Conflict):
            _save_payment_references(payment)
    database.session.rollback()


def test_payment_cancellation_reverts_relations(app_ctx, monkeypatch):
    """Cancelar un pago libera las referencias y restaura el saldo pendiente."""

    from cacao_accounting.bancos import bancos_pago_cancel, _save_payment_references
    from cacao_accounting.database import DocumentRelation, PaymentEntry, PaymentReference, PurchaseInvoice, database

    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        grand_total=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
        base_outstanding_amount=Decimal("100.00"),
    )
    payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="pay", docstatus=1)
    database.session.add_all([invoice, payment])
    database.session.flush()

    with app_ctx.test_request_context(
        "/cash_management/payment/new",
        method="POST",
        data={
            "reference_type_0": "purchase_invoice",
            "reference_id_0": invoice.id,
            "allocated_amount_0": "25.00",
        },
    ):
        _save_payment_references(payment)
    database.session.commit()

    bancos_module = importlib.import_module("cacao_accounting.bancos")
    monkeypatch.setattr(bancos_module, "cancel_document", lambda document: setattr(document, "docstatus", 2))

    with app_ctx.test_request_context(f"/cash_management/payment/{payment.id}/cancel", method="POST"):
        response = unwrap(bancos_pago_cancel)(payment.id)

    relation = database.session.execute(database.select(DocumentRelation)).scalar_one()
    references = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment.id)).scalars().all()
    refreshed_invoice = database.session.get(PurchaseInvoice, invoice.id)

    assert response.status_code == 302
    assert relation.status == "reverted"
    assert references == []
    assert refreshed_invoice is not None
    assert refreshed_invoice.outstanding_amount == Decimal("100.00")


def test_create_company_with_custom_fiscal_year_generates_12_periods(app_ctx):
    from cacao_accounting.setup.service import create_company
    from cacao_accounting.database import AccountingPeriod, FiscalYear, database

    company_data = {
        "id": "mapco",
        "razon_social": "Mapco",
        "nombre_comercial": "Mapco",
        "id_fiscal": "M0001",
        "moneda": "USD",
        "pais": "US",
        "tipo_entidad": "company",
        "inicio_anio_fiscal": date(2025, 4, 1),
        "fin_anio_fiscal": date(2026, 3, 31),
    }

    entity = create_company(
        company_data,
        catalogo_tipo="en_cero",
        country="US",
        idioma="en",
        catalogo_archivo=None,
        status="activo",
        default=False,
    )
    database.session.commit()

    fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(entity=entity.code)).scalar_one()
    periods = (
        database.session.execute(
            database.select(AccountingPeriod)
            .filter_by(entity=entity.code, fiscal_year_id=fiscal_year.id)
            .order_by(AccountingPeriod.start)
        )
        .scalars()
        .all()
    )

    assert len(periods) == 12
    assert periods[0].start == date(2025, 4, 1)
    assert periods[-1].end == date(2026, 3, 31)


def test_closed_fiscal_year_blocks_all_postings(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal, JournalValidationError
    from cacao_accounting.database import Accounts, ExchangeRate, FiscalYear, Book, database

    debit_account = Accounts(entity="cacao", code="EXP-009", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-009", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all(
        [
            debit_account,
            credit_account,
            fiscal_book,
            FiscalYear(
                entity="cacao", name="2026", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31), is_closed=True
            ),
            ExchangeRate(origin="USD", destination="NIO", rate="35.00", date=date(2026, 5, 6)),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["FISC"],
            "transaction_currency": "USD",
            "lines": [
                {"account": debit_account.id, "debit": "10.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    with pytest.raises(JournalValidationError, match="año fiscal cerrado"):
        submit_journal(journal.id)
