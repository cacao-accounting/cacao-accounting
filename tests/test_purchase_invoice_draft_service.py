"""Regresión de aislamiento para borradores de factura de compra."""

from types import SimpleNamespace
from typing import cast

import pytest

from cacao_accounting.compras.purchase_invoice_draft_service import (
    PurchaseInvoiceDraftCommand,
    PurchaseInvoiceDraftError,
    _validate_idempotency_replay,
)
from cacao_accounting.database import PurchaseInvoice


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
