"""Regresión de aislamiento para borradores de factura de compra."""

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask_babel import Babel, force_locale

from cacao_accounting.compras.purchase_invoice_draft_service import (
    PurchaseInvoiceDraftCommand,
    PurchaseInvoiceDraftError,
    PurchaseInvoiceDraftLine,
    _validate_idempotency_replay,
    _validate_line,
    _validate_sources,
)
from cacao_accounting.database import CompanyParty, PurchaseInvoice

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "cacao_accounting" / "translations"


@pytest.mark.parametrize(
    ("existing_company", "existing_supplier", "command_company", "command_supplier"),
    [
        ("company-a", "supplier-a", "company-b", "supplier-a"),
        ("company-a", "supplier-a", "company-a", "supplier-b"),
    ],
)
def test_idempotency_replay_rejects_cross_tenant_or_supplier_invoice(
    existing_company: str,
    existing_supplier: str,
    command_company: str,
    command_supplier: str,
) -> None:
    """Una clave global no puede convertirse en acceso a otra factura."""
    existing = cast(PurchaseInvoice, SimpleNamespace(company=existing_company, supplier_id=existing_supplier))
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(company_id=command_company, supplier_id=command_supplier))

    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _validate_idempotency_replay(existing, command)

    assert exc_info.value.code == "IDEMPOTENCY_KEY_CONFLICT"


def test_idempotency_replay_returns_same_tenant_and_supplier_invoice() -> None:
    """Un retry legítimo conserva la semántica idempotente original."""
    existing = cast(PurchaseInvoice, SimpleNamespace(company="company-a", supplier_id="supplier-a"))
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(company_id="company-a", supplier_id="supplier-a"))

    assert _validate_idempotency_replay(existing, command) is existing


def test_non_po_invoice_requires_supplier_permission_without_receipt() -> None:
    """NON_PO drafts require both no-order and no-receipt supplier permissions."""
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(
            matching_mode="NON_PO_INVOICE",
            purchase_order_id=None,
            purchase_receipt_id=None,
        ),
    )
    settings = cast(
        CompanyParty,
        SimpleNamespace(
            allow_purchase_invoice_without_order=True,
            allow_purchase_invoice_without_receipt=False,
        ),
    )

    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _validate_sources(command, settings)

    assert exc_info.value.code == "RECEIPT_REQUIRED"


def test_non_po_invoice_accepts_both_supplier_permissions() -> None:
    """NON_PO drafts are accepted when both source bypasses are configured."""
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(
            matching_mode="NON_PO_INVOICE",
            purchase_order_id=None,
            purchase_receipt_id=None,
        ),
    )
    settings = cast(
        CompanyParty,
        SimpleNamespace(
            allow_purchase_invoice_without_order=True,
            allow_purchase_invoice_without_receipt=True,
        ),
    )

    _validate_sources(command, settings)


def test_non_purchasable_line_translates_template_before_interpolation() -> None:
    """El código de artículo se interpola después de resolver el catálogo inglés."""
    app = Flask(__name__)
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(TRANSLATIONS_DIR)
    Babel(app, locale_selector=lambda: "es")
    query = MagicMock()
    query.where.return_value = query
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    database_stub = SimpleNamespace(
        select=MagicMock(return_value=query),
        session=SimpleNamespace(execute=MagicMock(return_value=query_result)),
    )
    line = PurchaseInvoiceDraftLine(
        item_code="CACAO-01",
        quantity=Decimal("1"),
        rate=Decimal("1"),
        amount=Decimal("1"),
    )

    with (
        app.test_request_context(),
        force_locale("en"),
        patch("cacao_accounting.compras.purchase_invoice_draft_service.database", database_stub),
        pytest.raises(PurchaseInvoiceDraftError) as exc_info,
    ):
        _validate_line(line)

    assert exc_info.value.code == "LINE_UNRESOLVED"
    assert str(exc_info.value) == "Item 'CACAO-01' is not purchasable."
