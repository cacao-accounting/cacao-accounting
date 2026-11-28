# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1223: purchase notes must follow their source invoice's links and currency."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.compras import services
from cacao_accounting.database import (
    Currency,
    ExchangeRate,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseReceipt,
    User,
    database,
)


@pytest.fixture
def purchase_note_sources(entorno_contable_aislado):
    """Create one invoice flow and unrelated same-company purchase sources."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    with app.app_context():
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        for code in ("USD", "EUR"):
            currency = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
            if currency is None:
                database.session.add(Currency(code=code, name=code, decimals=2, active=True, default=False))
        database.session.add_all(
            [
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.5"), date=date(2026, 5, 20)),
                ExchangeRate(origin="EUR", destination="NIO", rate=Decimal("40.0"), date=date(2026, 5, 20)),
            ]
        )
        database.session.flush()
        source_order = PurchaseOrder(
            company="cacao",
            posting_date=date(2026, 5, 1),
            docstatus=1,
            document_no=f"PO-NOTE-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_order = PurchaseOrder(
            company="cacao",
            posting_date=date(2026, 5, 1),
            docstatus=1,
            document_no=f"PO-OTHER-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        database.session.add_all([source_order, unrelated_order])
        database.session.flush()
        original_receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 5),
            docstatus=1,
            document_no=f"PR-NOTE-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=source_order.id,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_usd_receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 6),
            docstatus=1,
            document_no=f"PR-USD-OTHER-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            base_currency="NIO",
        )
        unrelated_eur_receipt = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 6),
            docstatus=1,
            document_no=f"PR-EUR-OTHER-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="EUR",
            base_currency="NIO",
        )
        database.session.add_all([original_receipt, unrelated_usd_receipt, unrelated_eur_receipt])
        database.session.flush()
        source_invoice = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"PI-NOTE-{suffix}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=source_order.id,
            purchase_receipt_id=original_receipt.id,
            transaction_currency="USD",
            base_currency="NIO",
        )
        database.session.add(source_invoice)
        database.session.commit()
        return {
            "app": app,
            "supplier_id": str(supplier.id),
            "invoice_id": str(source_invoice.id),
            "order_id": str(source_order.id),
            "unrelated_order_id": str(unrelated_order.id),
            "receipt_id": str(original_receipt.id),
            "unrelated_usd_receipt_id": str(unrelated_usd_receipt.id),
            "unrelated_eur_receipt_id": str(unrelated_eur_receipt.id),
        }


def _bypass_unrelated_creation_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep source-link tests focused on the invoice-flow invariant."""
    monkeypatch.setattr(services, "_require_purchase_document_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "exige_acceso_compania", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_purchase_tax_template", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_supplier_company_membership", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_supplier_invoice_flags", lambda *args, **kwargs: None)
    monkeypatch.setattr(services, "_validate_duplicate_supplier_invoice", lambda *args, **kwargs: None)


def _note_form_data(sources: dict[str, str], **overrides: str) -> dict[str, str]:
    """Build the minimal posted form values needed by the creation context."""
    data = {
        "company": "cacao",
        "supplier_id": sources["supplier_id"],
        "posting_date": "2026-05-20",
        "document_type": "purchase_credit_note",
        "credit_note_type": "commercial_adjustment",
        "from_invoice": sources["invoice_id"],
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("receipt_currency", ["EUR", "USD"], ids=["foreign-currency", "same-currency"])
def test_unrelated_receipt_cannot_be_combined_with_source_invoice(
    purchase_note_sources,
    monkeypatch,
    receipt_currency,
):
    """A receipt is rejected when it is not linked to the reversal invoice, even at same currency."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    receipt_id = sources[f"unrelated_{receipt_currency.lower()}_receipt_id"]
    app = sources["app"]

    with (
        app.app_context(),
        app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data=_note_form_data(sources, from_receipt=receipt_id),
        ),
    ):
        invoice_count_before = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()
        result = services._create_purchase_invoice_from_request()
        invoice_count_after = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()

    assert result is None
    assert invoice_count_after == invoice_count_before


def test_unrelated_order_cannot_be_combined_with_source_invoice(purchase_note_sources, monkeypatch):
    """Matching supplier, company and currency do not make another order part of an invoice."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data=_note_form_data(sources, from_order=sources["unrelated_order_id"]),
        ),
    ):
        invoice_count_before = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()
        result = services._create_purchase_invoice_from_request()
        invoice_count_after = database.session.execute(database.select(PurchaseInvoice.id)).scalars().all()

    assert result is None
    assert invoice_count_after == invoice_count_before


def test_valid_note_uses_source_invoice_currency_and_links(purchase_note_sources, monkeypatch):
    """Valid note defaults come from the invoice, not an independently selected source."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with (
        app.app_context(),
        app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data=_note_form_data(sources),
        ),
    ):
        context = services._purchase_invoice_creation_context()

    assert context["source"].id == sources["invoice_id"]
    assert context["transaction_currency"] == "USD"
    assert context["from_order"] == sources["order_id"]
    assert context["from_receipt"] == sources["receipt_id"]


def _draft_note(sources: dict[str, str], *, currency: str = "USD") -> str:
    """Crea una nota borrador con la evidencia mínima para editar."""
    note = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 20),
        docstatus=0,
        document_no=f"NC-EDIT-{sources['invoice_id'][-6:]}",
        document_type="purchase_credit_note",
        credit_note_type="commercial_adjustment",
        is_return=True,
        supplier_id=sources["supplier_id"],
        supplier_name="Proveedor Principal SA",
        purchase_order_id=sources["order_id"],
        purchase_receipt_id=sources["receipt_id"],
        reversal_of=sources["invoice_id"],
        transaction_currency=currency,
        base_currency="NIO",
        exchange_rate=Decimal("36.5") if currency == "USD" else Decimal("40"),
        total=Decimal("20"),
        grand_total=Decimal("20"),
        base_grand_total=Decimal("730") if currency == "USD" else Decimal("800"),
        outstanding_amount=Decimal("20"),
        remarks="Nota original",
    )
    database.session.add(note)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=note.id,
            item_code="ART01",
            item_name="Artículo comercial",
            qty=Decimal("2"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
            is_superseded=False,
        )
    )
    database.session.commit()
    return str(note.id)


def _cliente(app):
    """Cliente autenticado como administrador de la app aislada."""
    client = app.test_client()
    with app.app_context():
        admin_id = str(database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one())
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def _edit_form(sources: dict[str, str], note: PurchaseInvoice, *, currency: str, remarks: str) -> dict[str, str]:
    """Formulario completo de edición para una nota vinculada a su factura."""
    return {
        "version": str(note.version),
        "supplier_id": sources["supplier_id"],
        "company": "cacao",
        "posting_date": "2026-05-20",
        "transaction_currency": currency,
        "credit_note_type": "commercial_adjustment",
        "from_order": sources["order_id"],
        "from_receipt": sources["receipt_id"],
        "from_invoice": sources["invoice_id"],
        "remarks": remarks,
        "item_code_0": "ART01",
        "item_name_0": "Artículo comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }


def test_edicion_fija_fuente_y_bloquea_moneda(purchase_note_sources):
    """El formulario de edición conserva la factura origen y su moneda."""
    sources = purchase_note_sources
    app = sources["app"]
    with app.app_context():
        note_id = _draft_note(sources)

    response = _cliente(app).get(f"/buying/purchase-invoice/{note_id}/edit")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": "purchase_invoice"' in body
    assert '"flowLockedFields": ["company", "currency"]' in body
    assert '"currency": "USD"' in body
    assert f'name="from_invoice" value="{sources["invoice_id"]}"' in body
    assert "loadSourceFromUrl" not in body


def test_edicion_rechaza_moneda_ajena_sin_mutar_borrador(purchase_note_sources, monkeypatch):
    """Una nota editada en EUR no reemplaza la moneda USD de la factura origen."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with app.app_context():
        note_id = _draft_note(sources)
        note = database.session.get(PurchaseInvoice, note_id)
        assert note is not None
        original_item_id = database.session.execute(
            database.select(PurchaseInvoiceItem.id).filter_by(purchase_invoice_id=note_id, is_superseded=False)
        ).scalar_one()
        data = _edit_form(sources, note, currency="EUR", remarks="No debe persistir")

    response = _cliente(app).post(f"/buying/purchase-invoice/{note_id}/edit", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert "La moneda debe coincidir con el documento origen." in response.get_data(as_text=True)
    with app.app_context():
        persisted = database.session.get(PurchaseInvoice, note_id)
        assert persisted is not None
        assert persisted.transaction_currency == "USD"
        assert persisted.exchange_rate == Decimal("36.5")
        assert persisted.remarks == "Nota original"
        assert persisted.purchase_order_id == sources["order_id"]
        assert persisted.purchase_receipt_id == sources["receipt_id"]
        active_items = list(
            database.session.execute(
                database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=note_id, is_superseded=False)
            )
            .scalars()
            .all()
        )
        assert [item.id for item in active_items] == [original_item_id]


@pytest.mark.parametrize(
    ("field", "source_key", "message"),
    [
        ("from_receipt", "unrelated_usd_receipt_id", "La recepción indicada no pertenece al flujo de la factura origen."),
        ("from_order", "unrelated_order_id", "La orden indicada no pertenece al flujo de la factura origen."),
    ],
)
def test_edicion_rechaza_enlaces_ajenos(
    purchase_note_sources,
    monkeypatch,
    field: str,
    source_key: str,
    message: str,
):
    """La edición tampoco acepta orden o recepción fuera del flujo origen."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with app.app_context():
        note_id = _draft_note(sources)
        note = database.session.get(PurchaseInvoice, note_id)
        assert note is not None
        data = _edit_form(sources, note, currency="USD", remarks="No debe persistir")
        data[field] = sources[source_key]

    response = _cliente(app).post(f"/buying/purchase-invoice/{note_id}/edit", data=data, follow_redirects=True)

    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        persisted = database.session.get(PurchaseInvoice, note_id)
        assert persisted is not None
        assert persisted.purchase_order_id == sources["order_id"]
        assert persisted.purchase_receipt_id == sources["receipt_id"]
        assert persisted.remarks == "Nota original"


def test_edicion_valida_recalcula_tasa_de_la_factura_origen(purchase_note_sources, monkeypatch):
    """Una edición válida conserva USD y recalcula importes base con su tasa."""
    sources = purchase_note_sources
    _bypass_unrelated_creation_guards(monkeypatch)
    app = sources["app"]
    with app.app_context():
        note_id = _draft_note(sources)
        note = database.session.get(PurchaseInvoice, note_id)
        assert note is not None
        data = _edit_form(sources, note, currency="USD", remarks="Nota editada")

    response = _cliente(app).post(f"/buying/purchase-invoice/{note_id}/edit", data=data, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        persisted = database.session.get(PurchaseInvoice, note_id)
        assert persisted is not None
        assert persisted.transaction_currency == "USD"
        assert persisted.exchange_rate == Decimal("36.5")
        assert persisted.grand_total == Decimal("20")
        assert persisted.base_grand_total == Decimal("730.0000")
        assert persisted.remarks == "Nota editada"
        assert persisted.purchase_order_id == sources["order_id"]
        assert persisted.purchase_receipt_id == sources["receipt_id"]
        active_items = list(
            database.session.execute(
                database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=note_id, is_superseded=False)
            )
            .scalars()
            .all()
        )
        assert len(active_items) == 1
        assert active_items[0].amount == Decimal("20")
