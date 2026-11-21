# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Posted inventory documents and their source lines stay immutable in both modes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentTaxLine,
    DocumentTaxSummary,
    Entity,
    Item,
    Party,
    PaymentEntry,
    PaymentReference,
    StockEntry,
    StockEntryItem,
    UOM,
    WithholdingCertificate,
    database,
)


@pytest.fixture(params=[True, False], ids=["desktop", "cloud"])
def posted_stock_entry(request):
    """Create a posted stock document with its original inventory source line."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": request.param,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        supplier = Party(code=f"SUP-{suffix}", name=f"Proveedor {suffix}", is_supplier=True)
        database.session.add(supplier)
        database.session.flush()
        item = Item(code=f"ITEM-{suffix}", name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA")
        entry = StockEntry(
            company="alpha", purpose="receipt", posting_date=date(2026, 11, 20), docstatus=0, remarks="original"
        )
        payment = PaymentEntry(
            company="alpha",
            payment_type="pay",
            party_type="supplier",
            party_id=supplier.id,
            docstatus=0,
            remarks="pago original",
        )
        database.session.add_all([item, entry, payment])
        database.session.flush()
        line = StockEntryItem(
            stock_entry_id=entry.id,
            item_code=item.code,
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="EA",
            amount=Decimal("20"),
        )
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type="purchase_invoice",
            reference_id=f"INV-{suffix}",
            party_type="supplier",
            party_id=supplier.id,
            company="alpha",
            allocated_amount=Decimal("20"),
        )
        certificate = WithholdingCertificate(
            company="alpha",
            payment_id=payment.id,
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            certificate_no=f"RET-{suffix}",
            posting_date=date(2026, 11, 20),
            document_date=date(2026, 11, 20),
            currency="NIO",
            gross_amount=Decimal("20"),
            withheld_amount=Decimal("2"),
            cash_amount=Decimal("18"),
            lines_json='[{"concept":"ISR","amount":"2"}]',
            status="issued",
            docstatus=0,
        )
        tax_summary = DocumentTaxSummary(
            company="alpha",
            document_type="payment_entry",
            document_id=payment.id,
            currency="NIO",
            subtotal=Decimal("20"),
            document_tax_total=Decimal("2"),
            grand_total=Decimal("22"),
        )
        database.session.add_all([line, reference, certificate, tax_summary])
        database.session.flush()
        tax_line = DocumentTaxLine(
            document_tax_summary_id=tax_summary.id,
            line_index=0,
            concept="Retención",
            tax_type="withholding",
            calculation_method="manual",
            amount=Decimal("2"),
        )
        database.session.add(tax_line)
        database.session.commit()
        entry.docstatus = 1
        payment.docstatus = 1
        certificate.docstatus = 1
        database.session.commit()
        ids = {
            "entry": entry.id,
            "line": line.id,
            "reference": reference.id,
            "certificate": certificate.id,
            "tax_summary": tax_summary.id,
            "tax_line": tax_line.id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize("model_name", ["entry", "line"])
@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize("channel", ["orm", "core", "textual"])
def test_posted_stock_evidence_rejects_mutations_in_both_modes(posted_stock_entry, model_name, operation, channel):
    """No write path may rewrite or cascade-delete posted inventory evidence."""
    app, ids = posted_stock_entry
    model = StockEntry if model_name == "entry" else StockEntryItem
    row_id = ids[model_name]

    with app.app_context():
        with pytest.raises(ValueError):
            if channel == "orm":
                row = database.session.get(model, row_id)
                assert row is not None
                if operation == "delete":
                    database.session.delete(row)
                elif model_name == "entry":
                    row.remarks = "mutated"
                else:
                    row.qty = Decimal("9")
                database.session.commit()
            elif channel == "core":
                if operation == "delete":
                    statement = database.delete(model)
                elif model_name == "entry":
                    statement = database.update(model).values(remarks="mutated")
                else:
                    statement = database.update(model).values(qty=Decimal("9"))
                database.session.execute(statement.where(model.id == row_id))
                database.session.commit()
            else:
                table = model.__tablename__
                if operation == "delete":
                    statement = text(f"DELETE FROM {table} WHERE id = :row_id")
                    parameters = {"row_id": row_id}
                elif model_name == "entry":
                    statement = text("UPDATE stock_entry SET remarks = :value WHERE id = :row_id")
                    parameters = {"row_id": row_id, "value": "mutated"}
                else:
                    statement = text("UPDATE stock_entry_item SET qty = :value WHERE id = :row_id")
                    parameters = {"row_id": row_id, "value": 9}
                database.session.execute(statement, parameters)
                database.session.commit()
        database.session.rollback()

    with app.app_context():
        entry = database.session.get(StockEntry, ids["entry"])
        line = database.session.get(StockEntryItem, ids["line"])
        assert entry is not None and entry.remarks == "original"
        assert line is not None and Decimal(str(line.qty)) == Decimal("2")


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (PaymentReference, "allocated_amount", Decimal("99")),
        (WithholdingCertificate, "withheld_amount", Decimal("99")),
        (WithholdingCertificate, "lines_json", "[]"),
    ],
)
def test_posted_payment_evidence_rejects_snapshot_rewrites(posted_stock_entry, model, field, value):
    """Payment allocations and issued tax certificate snapshots remain immutable."""
    app, ids = posted_stock_entry
    row_id = ids["reference"] if model is PaymentReference else ids["certificate"]

    with app.app_context():
        with pytest.raises(ValueError):
            row = database.session.get(model, row_id)
            assert row is not None
            setattr(row, field, value)
            database.session.commit()
        database.session.rollback()

        row = database.session.get(model, row_id)
        assert row is not None
        assert getattr(row, field) != value


def test_posted_withholding_certificate_allows_status_only_cancellation(posted_stock_entry):
    """The approved cancellation flow may update lifecycle state, not fiscal values."""
    app, ids = posted_stock_entry

    with app.app_context():
        certificate = database.session.get(WithholdingCertificate, ids["certificate"])
        assert certificate is not None
        certificate.status = "cancelled"
        certificate.docstatus = 2
        database.session.commit()

        cancelled = database.session.get(WithholdingCertificate, ids["certificate"])
        assert cancelled is not None
        assert (cancelled.status, cancelled.docstatus) == ("cancelled", 2)
        assert cancelled.withheld_amount == Decimal("2")


@pytest.mark.parametrize(
    ("model", "key", "field", "value"),
    [
        (DocumentTaxSummary, "tax_summary", "subtotal", Decimal("99")),
        (DocumentTaxLine, "tax_line", "amount", Decimal("99")),
    ],
)
def test_posted_polymorphic_tax_evidence_rejects_rewrites(posted_stock_entry, model, key, field, value):
    """Fiscal snapshots linked polymorphically to a posted payment stay immutable."""
    app, ids = posted_stock_entry

    with app.app_context():
        with pytest.raises(ValueError):
            row = database.session.get(model, ids[key])
            assert row is not None
            setattr(row, field, value)
            database.session.commit()
        database.session.rollback()

        row = database.session.get(model, ids[key])
        assert row is not None
        assert getattr(row, field) != value


def test_posted_advance_accepts_a_new_document_reference(posted_stock_entry):
    """A valid later application remains possible for a posted advance payment."""
    app, _ids = posted_stock_entry

    with app.app_context():
        advance = PaymentEntry(company="alpha", payment_type="pay", is_advance=True, docstatus=0)
        database.session.add(advance)
        database.session.commit()
        advance.docstatus = 1
        database.session.commit()

        reference = PaymentReference(
            payment_id=advance.id,
            reference_type="purchase_invoice",
            reference_id=f"INV-{uuid4().hex[:8]}",
            company="alpha",
            allocated_amount=Decimal("20"),
        )
        database.session.add(reference)
        database.session.commit()

        persisted = database.session.get(PaymentReference, reference.id)
        assert persisted is not None
        assert persisted.payment_id == advance.id
        assert persisted.allocated_amount == Decimal("20")
