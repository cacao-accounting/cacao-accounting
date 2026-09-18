# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de caracterizacion de la validacion de notas de credito de compra."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from cacao_accounting.compras import services as purchase_services


def _fake_database(*, scalar=None, relations=None, targets=None):
    """Construye un doble minimo de la capa de datos usada por los helpers."""
    session = SimpleNamespace(
        execute=lambda _query: SimpleNamespace(
            scalar_one_or_none=lambda: scalar,
            scalars=lambda: relations or [],
        ),
        get=lambda _model, target_id: (targets or {})[target_id],
    )
    return SimpleNamespace(select=select, session=session)


def test_load_reversal_source_missing_raises(monkeypatch):
    """A non existent source invoice is rejected."""
    monkeypatch.setattr(purchase_services, "database", _fake_database(scalar=None))
    with pytest.raises(ValueError):
        purchase_services._load_reversal_source("INV-1", False)


def test_load_reversal_source_returns_invoice(monkeypatch):
    """An existing source invoice is returned even when locked."""
    invoice = object()
    monkeypatch.setattr(purchase_services, "database", _fake_database(scalar=invoice))
    assert purchase_services._load_reversal_source("INV-1", True) is invoice


def test_validate_reversal_source_rejects_unapproved_and_mismatches():
    """Approval, supplier and company of the source are enforced."""
    unapproved = SimpleNamespace(docstatus=0, supplier_id="SUP", company="cacao")
    with pytest.raises(ValueError):
        purchase_services._validate_reversal_source(unapproved, None, None, "INV-1")

    approved = SimpleNamespace(docstatus=1, supplier_id="SUP", company="cacao")
    with pytest.raises(ValueError):
        purchase_services._validate_reversal_source(approved, "OTHER", None, "INV-1")
    with pytest.raises(ValueError):
        purchase_services._validate_reversal_source(approved, None, "OTHER", "INV-1")
    purchase_services._validate_reversal_source(approved, "SUP", "cacao", "INV-1")


def test_assert_no_issued_withholding_raises(monkeypatch):
    """An issued withholding blocks the reversal."""
    monkeypatch.setattr(purchase_services, "database", _fake_database(scalar="WH-1"))
    with pytest.raises(ValueError):
        purchase_services._assert_no_issued_withholding(SimpleNamespace(id="INV-1"))

    monkeypatch.setattr(purchase_services, "database", _fake_database(scalar=None))
    purchase_services._assert_no_issued_withholding(SimpleNamespace(id="INV-1"))


def test_assert_credit_note_within_capacity():
    """The credit note cannot exceed the available source credit."""
    with pytest.raises(ValueError):
        purchase_services._assert_credit_note_within_capacity(Decimal("150"), Decimal("100"))
    purchase_services._assert_credit_note_within_capacity(Decimal("100"), Decimal("100"))


def test_compute_credit_capacity_counts_active_credit_and_debit_notes(monkeypatch):
    """Active credit notes reduce and debit notes increase the credit capacity."""
    relations = [
        SimpleNamespace(target_id="CN", amount=Decimal("40")),
        SimpleNamespace(target_id="DN", amount=Decimal("10")),
        SimpleNamespace(target_id="CANCELLED", amount=Decimal("5")),
    ]
    targets = {
        "CN": SimpleNamespace(docstatus=1, document_type="purchase_credit_note", grand_total=Decimal("40")),
        "DN": SimpleNamespace(docstatus=1, document_type="purchase_debit_note", grand_total=Decimal("10")),
        "CANCELLED": SimpleNamespace(docstatus=2, document_type="purchase_credit_note", grand_total=Decimal("5")),
    }
    monkeypatch.setattr(purchase_services, "database", _fake_database(relations=relations, targets=targets))
    source = SimpleNamespace(id="INV-1", grand_total=Decimal("100"))

    assert purchase_services._compute_credit_capacity(source) == Decimal("70")
