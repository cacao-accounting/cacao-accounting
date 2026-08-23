# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Matriz parametrizada de cobertura fiscal por doctype del MVP fiscal (#250).

Para cada perfil documental del MVP ejecuta el mismo contrato server-side:

1. Preview fiscal positivo: el resumen se calcula con Decimal desde reglas del
   servidor o lineas manuales canonicas; los perfiles sin impuestos ni cargos
   ignoran las lineas fiscales del navegador.
2. Preview negativo: sin compania el preview se rechaza.
3. Snapshot + posting: los perfiles con impuestos persisten su snapshot fiscal
   y el contexto de posting de su familia documental lo recarga como reglas
   inmutables (``_document_tax_rules`` para facturas y notas de credito,
   ``_build_payment_context`` para pagos/cobros), incluyendo NC/ND de venta y
   compra y el cobro (payment_entry receive).
4. Negativos transversales: tipo documental no soportado y snapshot con cuenta
   fuera de la compania se rechazan.

El posting GL end-to-end por familia documental queda cubierto por las suites
funcionales existentes; esta matriz protege la entrada fiscal del posting.

Referencias: ``cacao_accounting/fiscal_preview_service.py``,
``cacao_accounting/fiscal_persistence_service.py``,
``cacao_accounting/accounting_engine/document_builders.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from flask import Flask

from cacao_accounting import create_app
from cacao_accounting.accounting_engine.document_builders import _build_payment_context, _document_tax_rules
from cacao_accounting.config import configuracion
from cacao_accounting.fiscal_persistence_service import (
    load_document_fiscal_lines,
    persist_document_fiscal_snapshot,
)
from cacao_accounting.fiscal_preview_service import fiscal_preview, get_fiscal_document_profile


@pytest.fixture()
def app_ctx() -> Iterator[Flask]:
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "fiscal-matrix-secret",
        }
    )
    with app.app_context():
        from cacao_accounting.database import CacaoConfig, Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="admin", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


MANUAL_TAX_LINE = {
    "manual": True,
    "concept": "IVA",
    "type": "tax",
    "base_amount": "20",
    "rate": "10",
    "amount": "2",
    "accounting_treatment": "separate_tax_account",
}


def _preview_payload(document_type: str, payment_type: str | None, *, with_manual_tax: bool = False) -> dict:
    payload = {
        "document_type": document_type,
        "payment_type": payment_type,
        "company": "cacao",
        "currency": "NIO",
        "posting_date": "2026-05-01",
        "party_id": "PARTY-MATRIX",
        "purpose": "material_receipt",
        "purchase_invoice_id": "PINV-MATRIX",
        "lines": [{"uid": "LINE-001", "item_code": "ITEM-001", "qty": "2", "rate": "10"}],
    }
    if with_manual_tax:
        payload["tax_lines"] = [dict(MANUAL_TAX_LINE)]
    return payload


@pytest.mark.parametrize(
    ("document_type", "payment_type", "expected_profile", "accepts_fiscal_lines"),
    [
        ("purchase_request", None, "purchase_request", False),
        ("purchase_order", None, "purchase_order", False),
        ("purchase_receipt", None, "purchase_receipt", True),
        ("purchase_invoice", None, "purchase_invoice", True),
        ("import_landed_cost", None, "import_landed_cost", True),
        ("sales_request", None, "sales_request", False),
        ("sales_order", None, "sales_order", False),
        ("delivery_note", None, "delivery_note", False),
        ("sales_invoice", None, "sales_invoice", True),
        ("stock_entry", None, "stock_entry", True),
        ("payment_entry", "pay", "payment_entry", True),
        ("payment_entry", "receive", "payment_entry", True),
        ("payment_entry", "debit_note", "bank_debit_note", False),
        ("payment_entry", "credit_note", "bank_credit_note", False),
        ("payment_entry", "internal_transfer", "bank_transfer", False),
    ],
)
def test_matriz_preview_positivo_por_doctype(
    app_ctx: Flask,
    document_type: str,
    payment_type: str | None,
    expected_profile: str,
    accepts_fiscal_lines: bool,
) -> None:
    """Cada perfil MVP calcula su preview fiscal server-side."""
    preview = fiscal_preview(_preview_payload(document_type, payment_type, with_manual_tax=accepts_fiscal_lines))

    assert preview["profile"]["document_type"] == expected_profile
    assert preview["summary"]["subtotal"] == "20"
    assert preview["errors"] == []
    if accepts_fiscal_lines:
        assert Decimal(preview["summary"]["document_tax_total"]) == Decimal("2")
        assert Decimal(preview["summary"]["grand_total"]) == Decimal("22")
        assert any(line["concept"] == "IVA" for line in preview["tax_lines"])
    else:
        assert Decimal(preview["summary"]["document_tax_total"]) == Decimal("0")
        assert Decimal(preview["summary"]["grand_total"]) == Decimal("20")
        assert preview["tax_lines"] == []


@pytest.mark.parametrize(
    ("document_type", "payment_type"),
    [
        ("purchase_request", None),
        ("purchase_order", None),
        ("purchase_receipt", None),
        ("purchase_invoice", None),
        ("import_landed_cost", None),
        ("sales_request", None),
        ("sales_order", None),
        ("delivery_note", None),
        ("sales_invoice", None),
        ("stock_entry", None),
        ("payment_entry", "pay"),
        ("payment_entry", "receive"),
        ("payment_entry", "debit_note"),
        ("payment_entry", "credit_note"),
        ("payment_entry", "internal_transfer"),
    ],
)
def test_matriz_preview_negativo_sin_compania(app_ctx: Flask, document_type: str, payment_type: str | None) -> None:
    """El preview exige compania para calcular impuestos y cargos."""
    payload = _preview_payload(document_type, payment_type)
    payload.pop("company")
    with pytest.raises(ValueError, match="obligatoria"):
        fiscal_preview(payload)


def test_matriz_rechaza_tipo_documental_desconocido(app_ctx: Flask) -> None:
    """Un doctype fuera de la matriz no recibe perfil fiscal silenciosamente."""
    with pytest.raises(ValueError, match="no soportado"):
        get_fiscal_document_profile("documento_inexistente")


@pytest.mark.parametrize(
    (
        "document_type",
        "applies_to",
        "recognition_event",
        "expected_concept",
        "expected_amount",
        "expected_type",
    ),
    [
        ("sales_invoice", "sales", "sales_invoice_confirmed", "IVA", Decimal("15.00"), "tax"),
        ("sales_credit_note", "sales", "sales_credit_note_confirmed", "IVA", Decimal("15.00"), "tax"),
        ("purchase_invoice", "purchase", "purchase_invoice_confirmed", "IVA", Decimal("15.00"), "tax"),
        ("purchase_credit_note", "purchase", "purchase_credit_note_confirmed", "IVA", Decimal("15.00"), "tax"),
    ],
)
def test_matriz_snapshot_posting_facturas_y_notas(
    app_ctx: Flask,
    document_type: str,
    applies_to: str,
    recognition_event: str,
    expected_concept: str,
    expected_amount: Decimal,
    expected_type: str,
) -> None:
    """Facturas y NC/ND de venta/compra conservan su snapshot para el posting."""
    from cacao_accounting.database import PurchaseInvoice, SalesInvoice, database

    is_return = document_type.endswith("_credit_note")
    if applies_to == "sales":
        document = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 1),
            document_type=document_type,
            docstatus=0,
            is_return=is_return,
        )
    else:
        document = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 1),
            document_type=document_type,
            docstatus=0,
            is_return=is_return,
        )
    database.session.add(document)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type=document_type,
        document_id=document.id,
        currency="NIO",
        tax_lines=[
            {
                "source_rule_id": f"MANUAL-{document_type.upper()}-001",
                "manual": True,
                "concept": "IVA",
                "type": "tax",
                "base_amount": "100.00",
                "rate": "15",
                "amount": "15.00",
                "accounting_treatment": "separate_tax_account",
                "account_id": "",
                "affects_inventory": False,
                "included_in_price": False,
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "15.00", "grand_total": "115.00"},
    )

    rules = _document_tax_rules(document, [], company="cacao", applies_to=applies_to, event_type=recognition_event)

    assert len(rules) == 1
    assert rules[0].concept == expected_concept
    assert rules[0].amount == expected_amount
    assert rules[0].tax_type == expected_type
    assert rules[0].recognition_event == recognition_event
    persisted = load_document_fiscal_lines(document_type, document.id)
    assert persisted[0].concept == "IVA"


@pytest.mark.parametrize(
    ("payment_type", "recognition_event"),
    [("pay", "payment_confirmed"), ("receive", "collection_confirmed")],
)
def test_matriz_snapshot_posting_pagos_y_cobros(app_ctx: Flask, payment_type: str, recognition_event: str) -> None:
    """Pagos y cobros conservan su snapshot fiscal para el evento contable."""
    from cacao_accounting.database import PaymentEntry, database

    outgoing = payment_type == "pay"
    document = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        payment_type=payment_type,
        paid_amount=Decimal("98.00") if outgoing else None,
        base_paid_amount=Decimal("98.00") if outgoing else None,
        received_amount=None if outgoing else Decimal("98.00"),
        base_received_amount=None if outgoing else Decimal("98.00"),
        party_type="supplier" if outgoing else "customer",
        party_id="",
        docstatus=0,
    )
    database.session.add(document)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="payment_entry",
        document_id=document.id,
        currency="NIO",
        tax_lines=[
            {
                "source_rule_id": f"MANUAL-PAYMENT-{payment_type.upper()}-001",
                "manual": True,
                "concept": "Retención",
                "type": "withholding",
                "base_amount": "100.00",
                "rate": "2",
                "amount": "2.00",
                "accounting_treatment": "separate_tax_account",
                "account_id": "",
                "affects_inventory": False,
                "included_in_price": False,
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "-2.00", "grand_total": "98.00"},
    )

    context = _build_payment_context(document)

    assert context is not None
    assert context.event_type == recognition_event
    assert len(context.tax_rules) == 1
    assert context.tax_rules[0].tax_type == "withholding"
    assert context.tax_rules[0].amount == Decimal("2.00")
    persisted = load_document_fiscal_lines("payment_entry", document.id)
    assert persisted[0].notes == "" or persisted[0].concept == "Retención"


def test_matriz_notas_bancarias_resuelven_perfil_sin_impuestos(app_ctx: Flask) -> None:
    """Las notas bancarias resuelven perfil propio y no aplican impuestos."""
    for payment_type, expected in (("debit_note", "bank_debit_note"), ("credit_note", "bank_credit_note")):
        profile = get_fiscal_document_profile("payment_entry", payment_type)
        assert profile.document_type == expected
        assert profile.supports_taxes is False
        preview = fiscal_preview(_preview_payload("payment_entry", payment_type, with_manual_tax=False))
        assert preview["summary"]["grand_total"] == "20"
        assert preview["tax_lines"] == []


def test_matriz_snapshot_rechaza_cuenta_de_otra_compania(app_ctx: Flask) -> None:
    """Lineas fiscales manuales no pueden publicar en cuentas ajenas."""
    from cacao_accounting.database import Accounts, Entity, PurchaseInvoice, database

    other_entity = Entity(
        code="cafe",
        name="Cafe",
        company_name="Cafe",
        tax_id="J0002",
        currency="NIO",
        enabled=True,
    )
    other_account = Accounts(
        id="ACC-TAX-MATRIX",
        entity="cafe",
        code="ACC-TAX-MATRIX",
        name="Impuesto Cafe",
        active=True,
        enabled=True,
        group=False,
    )
    database.session.add_all([other_entity, other_account])
    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 4), document_type="purchase_invoice")
    database.session.add(invoice)
    database.session.flush()

    with pytest.raises(ValueError, match="pertenecer a la compañía"):
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="purchase_invoice",
            document_id=invoice.id,
            currency="NIO",
            tax_lines=[
                {
                    "source_rule_id": "MANUAL-FLETE-MATRIX",
                    "manual": True,
                    "concept": "Flete",
                    "amount": "10",
                    "account_id": other_account.id,
                }
            ],
            tax_summary={"subtotal": "100", "grand_total": "110"},
        )
