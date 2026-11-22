# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1057: purchase imports require an eligible supplier before execution."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import CompanyParty, Party, database
from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter as LegacyPurchaseOrderAdapter
from cacao_accounting.imports.services.import_service import ImportService


def _row(supplier_id: str) -> dict[str, str]:
    """Build one validly shaped purchase order row."""
    return {
        "document_ref": "PO-SUPPLIER-CHECK",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tipo_cambio": "1",
        "proveedor": supplier_id,
        "producto": "ART01",
        "cantidad": "1",
        "precio_unitario": "10",
    }


def _create_party(*, customer: bool, supplier: bool, active: bool, company_active: bool) -> Party:
    """Create an isolated party and company link for one eligibility case."""
    suffix = uuid4().hex[:10]
    party = Party(
        code=f"IMP-{suffix}",
        name="Proveedor para importación",
        is_customer=customer,
        is_supplier=supplier,
        is_active=active,
    )
    database.session.add(party)
    database.session.flush()
    database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=company_active))
    database.session.flush()
    return party


@pytest.mark.parametrize("registered", [False, True], ids=["legacy-adapter", "registered-adapter"])
@pytest.mark.parametrize(
    "party_flags",
    [
        pytest.param((True, False, True, True), id="wrong-role"),
        pytest.param((False, True, False, True), id="inactive-party"),
        pytest.param((False, True, True, False), id="inactive-company-link"),
    ],
)
def test_purchase_order_import_rejects_ineligible_supplier(entorno_contable, registered, party_flags):
    """Prevalidation and construction reject suppliers that cannot be used."""
    assert entorno_contable is not None
    customer, supplier, active, company_active = party_flags
    party = _create_party(customer=customer, supplier=supplier, active=active, company_active=company_active)
    adapter = ImportService.ADAPTERS["purchase_order"]() if registered else LegacyPurchaseOrderAdapter()
    rows = [_row(party.id)]
    if registered:
        rows[0]["tercero"] = rows[0].pop("proveedor")

    errors = adapter.validate_document(rows, {"company_id": "cacao"})

    assert any("proveedor" in error.lower() or "tercero" in error.lower() for error in errors)
    with pytest.raises(ValueError, match="proveedor|tercero"):
        adapter.build_document(rows, {"company_id": "cacao"})


@pytest.mark.parametrize("registered", [False, True], ids=["legacy-adapter", "registered-adapter"])
def test_purchase_order_import_accepts_active_supplier_for_company(entorno_contable, registered):
    """An active supplier enabled for the company remains importable."""
    assert entorno_contable is not None
    party = _create_party(customer=False, supplier=True, active=True, company_active=True)
    adapter = ImportService.ADAPTERS["purchase_order"]() if registered else LegacyPurchaseOrderAdapter()
    row = _row(party.id)
    if registered:
        row["tercero"] = row.pop("proveedor")
    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert not any("proveedor" in error.lower() or "tercero" in error.lower() for error in errors), errors


@pytest.mark.parametrize("registered", [False, True], ids=["legacy-adapter", "registered-adapter"])
def test_purchase_order_import_rejects_unknown_supplier_id(entorno_contable, registered):
    """An arbitrary party identifier cannot pass prevalidation or construction."""
    assert entorno_contable is not None
    adapter = ImportService.ADAPTERS["purchase_order"]() if registered else LegacyPurchaseOrderAdapter()
    row = _row("01M00000000000000000000000")
    if registered:
        row["tercero"] = row.pop("proveedor")

    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any("proveedor" in error.lower() or "tercero" in error.lower() for error in errors)
    with pytest.raises(ValueError):
        adapter.build_document([row], {"company_id": "cacao"})


@pytest.mark.parametrize("registered", [False, True], ids=["legacy-adapter", "registered-adapter"])
def test_purchase_order_import_rejects_missing_supplier(entorno_contable, registered):
    """Construction rejects a missing supplier even when validation was bypassed."""
    assert entorno_contable is not None
    adapter = ImportService.ADAPTERS["purchase_order"]() if registered else LegacyPurchaseOrderAdapter()
    row = _row("unused")
    if registered:
        row["tercero"] = row.pop("proveedor")
    row.pop("tercero" if registered else "proveedor")

    errors = adapter.validate_row(row) + adapter.validate_document([row], {"company_id": "cacao"})

    assert any("proveedor" in error.lower() or "tercero" in error.lower() for error in errors)
    with pytest.raises(ValueError):
        adapter.build_document([row], {"company_id": "cacao"})
