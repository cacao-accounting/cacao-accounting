# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1053: imports preserve an explicit, unambiguous source line relation."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.database import (
    DocumentRelation,
    Item,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseRequest,
    PurchaseRequestItem,
    database,
)
from cacao_accounting.imports.adapters import transaction_documents
from cacao_accounting.imports.adapters.transaction_documents import PurchaseOrderAdapter, PurchaseReceiptAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


def _source_purchase_order(entorno_contable):
    """Create an approved order and one available source line."""
    supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
    item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
    source = PurchaseOrder(
        company="cacao",
        document_no="PO-1053",
        posting_date=date(2026, 5, 10),
        docstatus=1,
        supplier_id=supplier.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(source)
    database.session.flush()
    line = PurchaseOrderItem(
        purchase_order_id=source.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(line)
    database.session.flush()
    return source, line


def _receipt_row(source, line, entorno_contable, **overrides):
    """Build one valid receipt row referencing a source document line."""
    return {
        "document_ref": "PR-1053",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tercero": source.supplier_id,
        "documento_origen": source.id,
        "linea_origen_id": line.id,
        "producto": "ART01",
        "uom": "UND",
        "cantidad": "2",
        "precio_unitario": "10",
        "bodega": "BOD01",
        **overrides,
    }


def test_import_requires_a_source_line_identifier_when_source_is_given(entorno_contable):
    """A header FK alone cannot pass import validation for a linked receipt."""
    source, line = _source_purchase_order(entorno_contable)
    row = _receipt_row(source, line, entorno_contable)
    row.pop("linea_origen_id")

    adapter = PurchaseReceiptAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any("requiere documento_origen y linea_origen_id" in error for error in errors)
    assert adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "cacao"}) == []


def test_import_rejects_a_source_line_from_another_document(entorno_contable):
    """A line ID is valid only when it belongs to the declared source document."""
    source, line = _source_purchase_order(entorno_contable)
    other_source, _other_line = _source_purchase_order(entorno_contable)
    row = _receipt_row(other_source, line, entorno_contable)

    errors = PurchaseReceiptAdapter().validate_document([row], {"company_id": "cacao"})

    assert any("no existe, no pertenece" in error for error in errors)


def test_import_rejects_overallocation_before_document_persistence(entorno_contable):
    """Rows mapped to one source line are checked as a combined quantity."""
    source, line = _source_purchase_order(entorno_contable)
    rows = [
        _receipt_row(source, line, entorno_contable, document_ref="PR-1053-A", cantidad="3"),
        _receipt_row(source, line, entorno_contable, document_ref="PR-1053-A", cantidad="3"),
    ]

    errors = PurchaseReceiptAdapter().validate_document(rows, {"company_id": "cacao"})

    assert any("excede el pendiente" in error for error in errors)


def test_import_rejects_overallocation_across_documents_before_any_persist(entorno_contable):
    """All document groups in the batch share one source-line quantity budget."""
    source, line = _source_purchase_order(entorno_contable)
    rows_a = [_receipt_row(source, line, entorno_contable, document_ref="PR-1053-A", cantidad="3")]
    rows_b = [_receipt_row(source, line, entorno_contable, document_ref="PR-1053-B", cantidad="3")]
    adapter = PurchaseReceiptAdapter()

    assert adapter.validate_document(rows_a, {"company_id": "cacao"}) == []
    assert adapter.validate_document(rows_b, {"company_id": "cacao"}) == []
    batch = ImportBatch(company_id="cacao", record_type="purchase_receipt", import_status=3)
    database.session.add(batch)
    database.session.flush()
    error_count = ImportService()._collect_business_errors(adapter, batch.id, "cacao", {"A": rows_a, "B": rows_b})
    database.session.flush()
    batch_errors = (
        database.session.execute(database.select(ImportBatchError).filter_by(batch_id=batch.id, error_type="BUSINESS_RULE"))
        .scalars()
        .all()
    )

    assert error_count == 1
    assert len(batch_errors) == 1
    assert "en el archivo excede" in batch_errors[0].message


def test_import_ignores_active_relations_to_draft_targets(entorno_contable):
    """Draft targets do not consume source quantities during preflight or posting."""
    source, line = _source_purchase_order(entorno_contable)
    draft = PurchaseReceipt(
        company="cacao",
        document_no="PR-1053-DRAFT",
        posting_date=date(2026, 5, 12),
        docstatus=0,
        supplier_id=source.supplier_id,
        purchase_order_id=source.id,
    )
    database.session.add(draft)
    database.session.flush()
    draft_line = PurchaseReceiptItem(
        purchase_receipt_id=draft.id,
        item_code="ART01",
        item_name="Artículo borrador",
        qty=Decimal("4"),
        qty_in_base_uom=Decimal("4"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("40"),
    )
    database.session.add(draft_line)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="purchase_order",
            source_id=source.id,
            source_item_id=line.id,
            target_type="purchase_receipt",
            target_id=draft.id,
            target_item_id=draft_line.id,
            company="cacao",
            qty=Decimal("4"),
            qty_in_base_uom=Decimal("4"),
            uom="UND",
            relation_type="receives",
            status="active",
        )
    )
    database.session.flush()

    errors = PurchaseReceiptAdapter().validate_document(
        [_receipt_row(source, line, entorno_contable, cantidad="3")], {"company_id": "cacao"}
    )

    assert not any("excede el pendiente" in error for error in errors)


def test_import_rejects_unapproved_source_document(entorno_contable):
    """Relations cannot be imported from an unapproved source document."""
    source, line = _source_purchase_order(entorno_contable)
    source.docstatus = 0

    row = _receipt_row(source, line, entorno_contable)
    adapter = PurchaseReceiptAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any("debe estar aprobado" in error for error in errors)
    assert adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "cacao"}) == []


def test_import_rejects_source_document_outside_import_company(entorno_contable):
    """Source lines cannot cross the company boundary of the import batch."""
    source, line = _source_purchase_order(entorno_contable)

    row = _receipt_row(source, line, entorno_contable)
    adapter = PurchaseReceiptAdapter()
    errors = adapter.validate_document([row], {"company_id": "other-company"})

    assert any("pertenecer a la compañía importada" in error for error in errors)
    assert adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "other-company"}) == []


def test_import_rejects_source_party_mismatch(entorno_contable):
    """A source line cannot be attached to a target for another supplier."""
    source, line = _source_purchase_order(entorno_contable)
    other_party = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()

    row = _receipt_row(source, line, entorno_contable, tercero=other_party.id)
    adapter = PurchaseReceiptAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any("tercero del documento origen no coincide" in error for error in errors)
    assert adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "cacao"}) == []


def test_import_rejects_source_item_mismatch(entorno_contable):
    """Explicit line IDs cannot be used to import a different item."""
    source, line = _source_purchase_order(entorno_contable)

    row = _receipt_row(source, line, entorno_contable, producto="ART02")
    adapter = PurchaseReceiptAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any("artículo distinto al de la línea origen" in error for error in errors)
    assert adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "cacao"}) == []


def test_invalid_import_quantity_is_a_preflight_error(entorno_contable):
    """Non-numeric line quantities fail both per-document and file-wide checks safely."""
    source, line = _source_purchase_order(entorno_contable)
    row = _receipt_row(source, line, entorno_contable, cantidad="not-a-number")
    adapter = PurchaseReceiptAdapter()

    errors = adapter.validate_document([row], {"company_id": "cacao"})
    batch_errors = adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "cacao"})

    assert any("número decimal válido" in error for error in errors)
    assert batch_errors == []


def test_pending_quantity_failures_are_reported_by_both_preflights(entorno_contable, monkeypatch):
    """A corrupted availability query becomes a validation error, not a fatal batch error."""
    source, line = _source_purchase_order(entorno_contable)

    def invalid_pending(*_args, **_kwargs):
        raise ValueError("La evidencia activa de origen es inconsistente.")

    monkeypatch.setattr(transaction_documents, "pending_qty", invalid_pending)
    row = _receipt_row(source, line, entorno_contable)
    adapter = PurchaseReceiptAdapter()

    document_errors = adapter.validate_document([row], {"company_id": "cacao"})
    batch_errors = adapter.validate_batch_documents({"PR-1053": [row]}, {"company_id": "cacao"})

    assert "La evidencia activa de origen es inconsistente." in document_errors
    assert batch_errors == ["La evidencia activa de origen es inconsistente."]


def test_purchase_order_rejects_ambiguous_source_document_types(entorno_contable):
    """Matching IDs across supported source types are rejected rather than guessed."""
    request = PurchaseRequest(
        id="SRC1053",
        company="cacao",
        document_no="REQ-1053-AMB",
        posting_date=date(2026, 5, 10),
        docstatus=1,
    )
    quotation = PurchaseQuotation(
        id="SRC1053",
        company="cacao",
        document_no="RFQ-1053-AMB",
        posting_date=date(2026, 5, 10),
        docstatus=1,
    )
    database.session.add_all([request, quotation])
    database.session.flush()
    request_line = PurchaseRequestItem(
        id="LINE1053",
        purchase_request_id=request.id,
        item_code="ART01",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="UND",
    )
    quotation_line = PurchaseQuotationItem(
        id="LINE1053",
        purchase_quotation_id=quotation.id,
        item_code="ART01",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="UND",
    )
    database.session.add_all([request_line, quotation_line])
    database.session.flush()
    supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
    row = {
        "document_ref": "PO-1053-AMB",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tercero": supplier.id,
        "documento_origen": request.id,
        "linea_origen_id": request_line.id,
        "producto": "ART01",
        "uom": "UND",
        "cantidad": "2",
        "precio_unitario": "10",
    }

    adapter = PurchaseOrderAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})

    assert any("no existe, no pertenece al documento indicado o es ambigua" in error for error in errors)
    assert adapter.validate_batch_documents({"PO-1053-AMB": [row]}, {"company_id": "cacao"}) == []


def test_persist_aborts_if_the_source_line_becomes_invalid_after_preflight(entorno_contable):
    """Persistence remains fail-closed if source identity changes after validation."""
    source, line = _source_purchase_order(entorno_contable)
    row = _receipt_row(source, line, entorno_contable)
    adapter = PurchaseReceiptAdapter()
    document = adapter.build_document([row], {"company_id": "cacao"})
    document["source_lines"][0] = (source.id, "missing-source-line")

    with pytest.raises(ValueError, match="no existe, no pertenece"):
        adapter.persist_document(document)

    target_id = document["header"].id
    database.session.rollback()
    assert database.session.get(PurchaseReceipt, target_id) is None


def test_persisted_import_creates_relation_for_the_exact_source_line(entorno_contable):
    """The real adapter stores source/target line IDs through DocumentRelation."""
    source, _line = _source_purchase_order(entorno_contable)
    duplicate_item_line = PurchaseOrderItem(
        purchase_order_id=source.id,
        item_code="ART01",
        item_name="Artículo duplicado",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(duplicate_item_line)
    database.session.flush()
    row = _receipt_row(source, duplicate_item_line, entorno_contable)
    adapter = PurchaseReceiptAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})
    assert errors == []

    document = adapter.build_document([row], {"company_id": "cacao"})
    adapter.persist_document(document)
    database.session.flush()

    relation = database.session.execute(
        database.select(DocumentRelation).filter_by(
            source_type="purchase_order",
            source_id=source.id,
            source_item_id=duplicate_item_line.id,
            target_type="purchase_receipt",
            target_id=document["header"].id,
            target_item_id=document["items"][0].id,
            status="active",
        )
    ).scalar_one()
    assert relation.qty == Decimal("2")
    assert relation.qty_in_base_uom == Decimal("2")


def test_purchase_order_import_preserves_request_line_origin(entorno_contable):
    """Purchase orders can retain a request line without a source FK on the header."""
    request = PurchaseRequest(
        company="cacao",
        document_no="REQ-1053",
        posting_date=date(2026, 5, 10),
        docstatus=1,
    )
    database.session.add(request)
    database.session.flush()
    source_line = PurchaseRequestItem(
        purchase_request_id=request.id,
        item_code="ART01",
        item_name="Artículo",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="UND",
    )
    database.session.add(source_line)
    database.session.flush()
    row = {
        "document_ref": "PO-1053-IMPORT",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tercero": database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one().id,
        "documento_origen": request.id,
        "linea_origen_id": source_line.id,
        "producto": "ART01",
        "uom": "UND",
        "cantidad": "2",
        "precio_unitario": "10",
        "bodega": "BOD01",
    }
    adapter = PurchaseOrderAdapter()
    errors = adapter.validate_document([row], {"company_id": "cacao"})
    assert errors == []

    document = adapter.build_document([row], {"company_id": "cacao"})
    adapter.persist_document(document)
    database.session.flush()

    relation = database.session.execute(
        database.select(DocumentRelation).filter_by(
            source_type="purchase_request",
            source_id=request.id,
            source_item_id=source_line.id,
            target_type="purchase_order",
            target_id=document["header"].id,
            target_item_id=document["items"][0].id,
            status="active",
        )
    ).scalar_one()
    assert relation.qty_in_base_uom == Decimal("2")


def test_purchase_order_without_source_keeps_relation_optional(entorno_contable):
    """Imports without an upstream document remain valid and create no relation."""
    supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
    row = {
        "document_ref": "PO-1053-NO-SOURCE",
        "fecha": "2026-05-15",
        "moneda": "NIO",
        "tercero": supplier.id,
        "producto": "ART01",
        "uom": "UND",
        "cantidad": "2",
        "precio_unitario": "10",
        "bodega": "BOD01",
    }
    adapter = PurchaseOrderAdapter()
    assert adapter.validate_document([row], {"company_id": "cacao"}) == []

    document = adapter.build_document([row], {"company_id": "cacao"})
    adapter.persist_document(document)

    relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type="purchase_order", target_id=document["header"].id, status="active"
            )
        )
        .scalars()
        .all()
    )
    assert relations == []
