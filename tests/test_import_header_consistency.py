# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1054: grouped import rows must agree on document header values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter as LegacyPurchaseOrderAdapter
from cacao_accounting.imports.adapters.transaction_documents import PurchaseRequestAdapter
from cacao_accounting.imports.services.import_service import ImportService


def _transaction_rows() -> list[dict[str, object]]:
    """Return two validly shaped transaction rows in one import group."""
    return [
        {
            "document_ref": "PO-IMPORT-1",
            "fecha": "2026-05-15",
            "moneda": "NIO",
            "tipo_cambio": "1",
            "tercero": "SUP-1",
            "documento_origen": "PO-SOURCE-1",
            "producto": "ART01",
            "cantidad": "1",
            "precio_unitario": "10",
            "notas": "Import batch",
        },
        {
            "document_ref": "PO-IMPORT-1",
            "fecha": "2026-05-15",
            "moneda": "NIO",
            "tipo_cambio": "1.0",
            "tercero": "SUP-1",
            "documento_origen": "PO-SOURCE-1",
            "producto": "ART01",
            "cantidad": "1",
            "precio_unitario": "10",
            "notas": "Import batch",
        },
    ]


@pytest.mark.parametrize(
    ("field", "conflicting_value"),
    [
        ("fecha", "2026-05-16"),
        ("moneda", "USD"),
        ("tipo_cambio", "2"),
        ("tercero", "SUP-2"),
        ("documento_origen", "PO-SOURCE-2"),
        ("notas", "Different header note"),
    ],
)
def test_transaction_import_rejects_conflicting_header_fields(entorno_contable, field, conflicting_value):
    """Transaction adapters reject each header conflict instead of using row one silently."""
    rows = _transaction_rows()
    rows[1][field] = conflicting_value

    errors = PurchaseRequestAdapter().validate_document(rows, {"company_id": "cacao"})

    assert any(f"'{field}'" in error and "fila 2" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "conflicting_value"),
    [
        ("fecha", "2026-05-16"),
        ("moneda", "USD"),
        ("tipo_cambio", "2"),
        ("proveedor", "SUP-2"),
    ],
)
def test_purchase_order_import_rejects_conflicting_header_fields(entorno_contable, field, conflicting_value):
    """Purchase order groups reject dates, currencies, rates, or supplier changes."""
    rows = [
        {
            "document_ref": "PO-IMPORT-2",
            "fecha": "2026-05-15",
            "moneda": "NIO",
            "tipo_cambio": "1",
            "proveedor": "SUP-1",
            "producto": "ART01",
            "cantidad": "1",
            "precio_unitario": "10",
        },
        {
            "document_ref": "PO-IMPORT-2",
            "fecha": "2026-05-15",
            "moneda": "NIO",
            "tipo_cambio": "1.0",
            "proveedor": "SUP-1",
            "producto": "ART01",
            "cantidad": "1",
            "precio_unitario": "10",
        },
    ]
    rows[1][field] = conflicting_value

    errors = LegacyPurchaseOrderAdapter().validate_document(rows, {"company_id": "cacao"})

    assert any(f"'{field}'" in error and "fila 2" in error for error in errors)


def test_import_service_purchase_order_adapter_rejects_supplier_conflict(entorno_contable):
    """The registered purchase order adapter rejects grouped supplier changes."""
    rows = _transaction_rows()
    rows[0]["tercero"] = "SUP-1"
    rows[1]["tercero"] = "SUP-2"
    adapter = ImportService()._get_adapter("purchase_order")

    errors = adapter.validate_document(rows, {"company_id": "cacao"})

    assert any("'tercero'" in error and "fila 2" in error for error in errors)


def test_journal_import_rejects_a_date_conflict_before_building(entorno_contable):
    """Journal rows sharing a reference cannot silently inherit the first date."""
    rows = [
        {"document_ref": "JE-IMPORT-1", "fecha": "2026-05-15", "cuenta": "1101", "debito": "10", "credito": "0"},
        {"document_ref": "JE-IMPORT-1", "fecha": "2026-05-16", "cuenta": "4101", "debito": "0", "credito": "10"},
    ]

    errors = JournalEntryAdapter().validate_document(rows, {"company_id": "cacao"})

    assert any("'fecha'" in error and "fila 2" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [("fecha", "not-a-date"), ("tipo_cambio", "NaN")],
)
def test_invalid_header_values_are_rejected_as_conflicts(entorno_contable, field, invalid_value):
    """An invalid later row cannot bypass consistency checks or crash validation."""
    rows = _transaction_rows()
    rows[1][field] = invalid_value

    errors = PurchaseRequestAdapter().validate_document(rows, {"company_id": "cacao"})

    assert any(f"'{field}'" in error and "fila 2" in error for error in errors)


def test_conflict_reports_original_source_row_when_group_is_interleaved(entorno_contable):
    """The diagnostic points to the actual source row, not its group position."""
    first, second = _transaction_rows()
    other_document = {**first, "document_ref": "OTHER-IMPORT"}
    second["moneda"] = "USD"
    rows = [first, other_document, second]
    columns = list(first)
    groups = ImportService()._group_by_reference(columns, rows, PurchaseRequestAdapter())

    errors = PurchaseRequestAdapter().validate_document(groups["PO-IMPORT-1"], {"company_id": "cacao"})

    assert any("'moneda'" in error and "fila 3" in error for error in errors)


def test_equivalent_header_representations_do_not_create_conflicts(entorno_contable):
    """Equivalent spreadsheet dates, decimal formatting, and blank cells compare equal."""
    rows = _transaction_rows()
    rows[0]["fecha"] = date(2026, 5, 15)
    rows[1]["fecha"] = "2026-05-15"
    for row in rows:
        row.pop("moneda")
        row["transaction_currency"] = "NIO"
        row.pop("tipo_cambio")
    rows[0]["exchange_rate"] = Decimal("1.000")
    rows[1]["exchange_rate"] = "1"
    rows[0]["notas"] = None
    rows[1]["notas"] = "   "

    errors = PurchaseRequestAdapter().validate_document(rows, {"company_id": "cacao"})

    assert not any("no coincide" in error for error in errors)
