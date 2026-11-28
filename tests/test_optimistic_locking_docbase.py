# SPDX-License-Identifier: Apache-2.0
"""#1680: DocBase optimistic locking detects stale concurrent edits."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import request
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from cacao_accounting.compras import services as compras_services
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseOrder,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    database,
)


def _seed(app):
    with app.app_context():
        code = "L1680"
        if database.session.execute(database.select(Entity).filter_by(code=code)).scalar_one_or_none() is None:
            database.session.add(
                Entity(code=code, name="Lock", company_name="Lock", tax_id="J0310000001680", currency="NIO", enabled=True)
            )
            database.session.commit()
        po = PurchaseOrder(
            company=code,
            posting_date=date(2026, 1, 1),
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=1,
            docstatus=0,
            remarks="original",
        )
        database.session.add(po)
        database.session.commit()
        return po.id


def test_docbase_version_increments_on_update(app):
    po_id = _seed(app)
    with app.app_context():
        po = database.session.get(PurchaseOrder, po_id)
        assert po.version == 1
        po.remarks = "first"
        database.session.commit()
        refreshed = database.session.get(PurchaseOrder, po_id)
        assert refreshed.version == 2


def test_docbase_stale_update_raises(app):
    po_id = _seed(app)
    with app.app_context():
        s1 = Session(bind=database.engine)
        s2 = Session(bind=database.engine)
        try:
            po1 = s1.get(PurchaseOrder, po_id)
            po2 = s2.get(PurchaseOrder, po_id)
            po1.remarks = "first writer"
            s1.commit()
            po2.remarks = "second writer"
            with pytest.raises(StaleDataError):
                s2.commit()
            s2.rollback()
        finally:
            s1.close()
            s2.close()
        final = database.session.get(PurchaseOrder, po_id)
        database.session.refresh(final)
        assert final.remarks == "first writer"
        assert final.version == 2


def test_purchase_order_edit_rejects_stale_form_version(app):
    po_id = _seed(app)
    with app.app_context():
        po = database.session.get(PurchaseOrder, po_id)
        po.remarks = "concurrent"
        database.session.commit()
        database.session.refresh(po)
        assert po.version == 2

        stale_po = database.session.get(PurchaseOrder, po_id)
        # simulate a form submitted with stale version=1 while current is 2
        with app.test_request_context("/compras/orden-compra/%s/editar" % po_id, method="POST", data={"version": "1"}):
            from cacao_accounting.compras.services import _check_optimistic_version

            result = _check_optimistic_version(stale_po)
        assert result == "stale"

        with app.test_request_context("/compras/orden-compra/%s/editar" % po_id, method="POST", data={"version": "2"}):
            from cacao_accounting.compras.services import _check_optimistic_version

            result_ok = _check_optimistic_version(stale_po)
        assert result_ok is None


@pytest.mark.parametrize("data", [{}, {"version": ""}, {"version": "invalid"}, {"version": "0"}])
def test_purchase_order_edit_rejects_missing_or_invalid_version(app, data):
    """Un formulario de edición sin versión utilizable falla cerrado."""
    po_id = _seed(app)
    with app.app_context():
        po = database.session.get(PurchaseOrder, po_id)
        assert po is not None and po.version == 1
        with app.test_request_context(f"/compras/orden-compra/{po_id}/editar", method="POST", data=data):
            from cacao_accounting.compras.services import _update_purchase_order_from_request

            response = _update_purchase_order_from_request(po)
            assert response.status_code == 302
        database.session.expire_all()
        persisted = database.session.get(PurchaseOrder, po_id)
        assert persisted.remarks == "original"
        assert persisted.version == 1


def _seed_edit_documents(app) -> dict[str, str | int]:
    """Crea una cotización y una factura borrador válidas para la carrera de edición."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one_or_none() is None:
            database.session.add(
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-LOCK", currency="NIO", enabled=True)
            )
        if database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad"))
        if database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one_or_none() is None:
            database.session.add(
                Item(
                    code="ART01",
                    name="Articulo Comercial",
                    item_type="goods",
                    is_stock_item=True,
                    is_purchase_item=True,
                    default_uom="UND",
                )
            )
        supplier = Party(code=f"PRV-LOCK-{suffix}", name=f"Proveedor lock {suffix}", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        settings = database.session.execute(
            database.select(CompanyParty).filter_by(party_id=supplier.id, company="cacao")
        ).scalar_one_or_none()
        if settings is None:
            settings = CompanyParty(party_id=supplier.id, company="cacao", is_active=True)
            database.session.add(settings)
        settings.is_active = True
        settings.allow_purchase_invoice_without_order = True
        settings.allow_purchase_invoice_without_receipt = True
        matching = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if matching is None:
            matching = PurchaseMatchingConfig(
                company="cacao",
                matching_type="2-way",
                require_purchase_order=False,
                bridge_account_required=False,
                auto_reconcile=False,
            )
            database.session.add(matching)
        else:
            matching.require_purchase_order = False

        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"SQ-LOCK-{suffix}",
            remarks="original",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"PI-LOCK-{suffix}",
            supplier_invoice_no=f"PROV-LOCK-{suffix}",
            remarks="original",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            document_type="purchase_invoice",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add_all([quotation, invoice])
        database.session.flush()
        database.session.add_all(
            [
                SupplierQuotationItem(
                    supplier_quotation_id=quotation.id,
                    item_code="ART01",
                    item_name="Articulo Comercial",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("3"),
                    amount=Decimal("3"),
                    base_rate=Decimal("3"),
                    base_amount=Decimal("3"),
                ),
                PurchaseInvoiceItem(
                    purchase_invoice_id=invoice.id,
                    item_code="ART01",
                    item_name="Articulo Comercial",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal("10"),
                    base_amount=Decimal("10"),
                ),
            ]
        )
        database.session.commit()
        return {
            "suffix": suffix,
            "supplier": supplier.id,
            "quotation": quotation.id,
            "quotation_version": quotation.version,
            "invoice": invoice.id,
            "invoice_version": invoice.version,
        }


def _edit_payload(ids: dict[str, str | int], kind: str) -> dict[str, str]:
    """Payload válido con la versión leída antes de la actualización concurrente."""
    version = ids["quotation_version"] if kind == "supplier_quotation" else ids["invoice_version"]
    rate = "3" if kind == "supplier_quotation" else "10"
    payload = {
        "version": str(version),
        "supplier_id": str(ids["supplier"]),
        "company": "cacao",
        "posting_date": "2026-05-15",
        "transaction_currency": "NIO",
        "remarks": "stale writer",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "uom_0": "UND",
        "rate_0": rate,
        "amount_0": rate,
    }
    if kind == "purchase_invoice":
        payload["supplier_invoice_no"] = f"PROV-LOCK-{ids['suffix']}"
    return payload


@pytest.mark.parametrize("kind", ["supplier_quotation", "purchase_invoice"])
def test_edit_handlers_report_commit_race(app, monkeypatch, kind):
    """Una actualización posterior al guard de versión devuelve conflicto, no HTTP 500."""
    ids = _seed_edit_documents(app)
    model = SupplierQuotation if kind == "supplier_quotation" else PurchaseInvoice
    document_id = ids["quotation"] if kind == "supplier_quotation" else ids["invoice"]
    original_version = ids["quotation_version"] if kind == "supplier_quotation" else ids["invoice_version"]

    with app.app_context():
        registro = database.session.get(model, document_id)
        winner = Session(bind=database.engine)
        winner_row = winner.get(model, document_id)
        original_capture = compras_services._capture_purchase_state
        competido = False

        def capturar_con_competidor(documento):
            nonlocal competido
            if not competido:
                competido = True
                winner_row.remarks = "winner"
                winner.commit()
            return original_capture(documento)

        monkeypatch.setattr(compras_services, "_capture_purchase_state", capturar_con_competidor)
        with app.test_request_context("/", method="POST", data=_edit_payload(ids, kind)):
            if kind == "supplier_quotation":
                response = compras_services._handle_supplier_quotation_update(registro, request.form, str(document_id))
            else:
                response = compras_services._handle_purchase_invoice_edit_post(registro)
        winner.close()

        assert response.status_code == 302
        database.session.expire_all()
        persisted = database.session.get(model, document_id)
        assert persisted.remarks == "winner"
        assert persisted.version == int(original_version) + 1
        if kind == "supplier_quotation":
            lines = (
                database.session.execute(database.select(SupplierQuotationItem).filter_by(supplier_quotation_id=document_id))
                .scalars()
                .all()
            )
        else:
            lines = (
                database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=document_id))
                .scalars()
                .all()
            )
        assert len(lines) == 1
        assert lines[0].item_name == "Articulo Comercial"
        assert lines[0].rate == Decimal("3" if kind == "supplier_quotation" else "10")
