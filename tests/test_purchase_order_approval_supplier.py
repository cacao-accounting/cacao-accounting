# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1823: la aprobación revalida que el proveedor siga vigente."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.compras.services import _validated_purchase_supplier
from cacao_accounting.database import ApprovalAction, ApprovalRequest, CompanyParty, Entity, Party, User, database


def _proveedor(company: str, activo: bool = True, miembro: bool = True) -> str:
    sufijo = uuid4().hex[:5]
    proveedor = Party(code=f"P{sufijo}", name="Proveedor", is_supplier=True, is_active=activo)
    database.session.add(proveedor)
    database.session.flush()
    if miembro:
        database.session.add(CompanyParty(company=company, party_id=proveedor.id, is_active=True))
    database.session.commit()
    return proveedor.id


def _empresa() -> str:
    sufijo = uuid4().hex[:5]
    codigo = f"S{sufijo}"
    database.session.add(
        Entity(
            code=codigo,
            name="Sociedad",
            company_name=f"Sociedad {sufijo}",
            tax_id=f"J{sufijo}",
            currency="NIO",
            enabled=True,
        )
    )
    database.session.commit()
    return codigo


def test_proveedor_desactivado_no_aprueba(app, entorno_contable):
    """Si el proveedor se desactiva mientras espera aprobación, se rechaza."""
    with app.app_context():
        empresa = _empresa()
        proveedor_id = _proveedor(empresa)

        assert _validated_purchase_supplier(proveedor_id, empresa) is not None

        database.session.get(Party, proveedor_id).is_active = False
        database.session.commit()

        with pytest.raises(ValueError, match="no está habilitado como proveedor"):
            _validated_purchase_supplier(proveedor_id, empresa)


def test_membresia_revocada_no_aprueba(app, entorno_contable):
    """Revocar el vínculo con la compañía también bloquea la aprobación."""
    with app.app_context():
        empresa = _empresa()
        proveedor_id = _proveedor(empresa)

        vinculo = database.session.execute(database.select(CompanyParty).filter_by(party_id=proveedor_id)).scalar_one()
        vinculo.is_active = False
        database.session.commit()

        with pytest.raises(ValueError, match="no está habilitado para la compañía"):
            _validated_purchase_supplier(proveedor_id, empresa)


@pytest.mark.parametrize("invalidity", ["inactive", "revoked"])
def test_aprobar_orden_revalida_proveedor_y_conserva_solicitud(app, entorno_contable, invalidity, monkeypatch):
    """Un proveedor inválido bloquea aprobar sin mutar solicitud ni acciones."""
    from cacao_accounting.approval_engine import ApprovalEngine

    with app.app_context():
        empresa = _empresa()
        proveedor_id = _proveedor(empresa)
        proveedor = database.session.get(Party, proveedor_id)
        if invalidity == "inactive":
            proveedor.is_active = False
        else:
            membership = database.session.execute(database.select(CompanyParty).filter_by(party_id=proveedor_id)).scalar_one()
            membership.is_active = False
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        document = SimpleNamespace(
            id=f"PO-{uuid4().hex}", company=empresa, document_type="purchase_order", supplier_id=proveedor_id
        )
        request = ApprovalRequest(
            document_type="purchase_order",
            document_id=document.id,
            company_id=empresa,
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(request)
        database.session.commit()
        monkeypatch.setattr(ApprovalEngine, "is_enabled", classmethod(lambda *_args, **_kwargs: True))
        monkeypatch.setattr(ApprovalEngine, "can_approve", staticmethod(lambda *_args, **_kwargs: True))
        monkeypatch.setattr(ApprovalEngine, "_resolve_doctype", classmethod(lambda *_args, **_kwargs: "purchase_order"))
        monkeypatch.setattr(
            ApprovalEngine,
            "_pending_request",
            classmethod(lambda _cls, _document, lock=False: request),
        )

        with pytest.raises(ValueError):
            ApprovalEngine.approve(document, admin)

        assert database.session.get(ApprovalRequest, request.id).status == "Pending Approval"
        assert (
            database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=request.id)).scalars().all()
            == []
        )


def test_rechazo_sigue_disponible_si_proveedor_se_desactiva(app, entorno_contable, monkeypatch):
    """La validez del proveedor no debe impedir rechazar la orden pendiente."""
    from cacao_accounting.approval_engine import ApprovalEngine

    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        document = SimpleNamespace(id=f"PO-{uuid4().hex}", company="cacao", document_type="purchase_order")
        request = ApprovalRequest(
            document_type="purchase_order",
            document_id=document.id,
            company_id="cacao",
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(request)
        database.session.commit()
        monkeypatch.setattr(ApprovalEngine, "is_enabled", classmethod(lambda *_args, **_kwargs: True))
        monkeypatch.setattr(ApprovalEngine, "can_approve", staticmethod(lambda *_args, **_kwargs: True))
        monkeypatch.setattr(ApprovalEngine, "_resolve_doctype", classmethod(lambda *_args, **_kwargs: "purchase_order"))
        monkeypatch.setattr(ApprovalEngine, "_get_user_rules", classmethod(lambda *_args, **_kwargs: []))
        purchases_services = importlib.import_module("cacao_accounting.compras.services")
        monkeypatch.setattr(
            purchases_services,
            "_validated_purchase_supplier",
            lambda *_args: (_ for _ in ()).throw(ValueError("proveedor inactivo")),
        )

        ApprovalEngine.reject(document, admin, "Proveedor inactivo")
        database.session.commit()

        assert database.session.get(ApprovalRequest, request.id).status == "Rejected"
        actions = (
            database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=request.id)).scalars().all()
        )
        assert len(actions) == 1


def _purchase_order_http_context(app):
    """Crea proveedor, serie y datos mínimos para POST HTTP de OC."""
    from decimal import Decimal

    from cacao_accounting.database import Item, NamingSeries
    from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

    suffix = uuid4().hex[:6]
    item_code = f"IT{suffix}"
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["purchase_order"])
        supplier = Party(code=f"SUP{suffix}", name=f"Proveedor {suffix}", is_supplier=True, is_active=True)
        item = Item(
            code=item_code,
            name=f"Artículo {suffix}",
            item_type="service",
            is_stock_item=False,
            is_sale_item=True,
            is_purchase_item=True,
            default_uom="UND",
            standard_rate=Decimal("10"),
        )
        database.session.add_all([supplier, item])
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=supplier.id, is_active=True))
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="purchase_order", company="cacao")
        ).scalar_one()
        database.session.commit()
        return {
            "supplier_id": supplier.id,
            "series_id": series_id,
            "item_code": item_code,
            "party_ids": [supplier.id],
            "item_codes": [item_code],
        }


def _purge_purchase_data(app, *, party_ids=(), item_codes=(), order_ids=()):
    """Elimina solo los datos creados por estas pruebas, incluso tras un fallo."""
    from cacao_accounting.database import Item, PurchaseOrder, PurchaseOrderItem

    with app.app_context():
        ids = set(order_ids)
        if party_ids:
            ids.update(
                database.session.execute(
                    database.select(PurchaseOrder.id).where(PurchaseOrder.supplier_id.in_(party_ids))
                ).scalars()
            )
        if ids:
            database.session.execute(database.delete(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id.in_(ids)))
            database.session.execute(database.delete(PurchaseOrder).where(PurchaseOrder.id.in_(ids)))
        for item_code in item_codes:
            database.session.execute(database.delete(Item).where(Item.code == item_code))
        for party_id in party_ids:
            database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id == party_id))
            database.session.execute(database.delete(Party).where(Party.id == party_id))
        database.session.commit()


@pytest.fixture
def po_http_context(app, entorno_contable):
    """Contexto HTTP de OC con limpieza garantizada de terceros, ítems y órdenes."""
    del entorno_contable
    context = _purchase_order_http_context(app)
    yield context
    _purge_purchase_data(app, party_ids=context["party_ids"], item_codes=context["item_codes"])


@pytest.mark.parametrize(
    ("mutate", "mensaje"),
    [
        ("inactive_supplier", "no está habilitado como proveedor"),
        ("inactive_membership", "no está habilitado para la compañía"),
        ("missing_membership", "no está habilitado para la compañía"),
        ("not_supplier", "no está habilitado como proveedor"),
    ],
)
def test_purchase_order_new_post_rejects_invalid_supplier(app, authenticated_client, po_http_context, mutate, mensaje):
    """#1823/#2328: alta HTTP rechaza proveedor inválido o sin vínculo y no persiste."""
    from cacao_accounting.database import PurchaseOrder

    ctx = po_http_context
    with app.app_context():
        supplier = database.session.get(Party, ctx["supplier_id"])
        if mutate == "inactive_supplier":
            supplier.is_active = False
        elif mutate == "not_supplier":
            supplier.is_supplier = False
        elif mutate == "inactive_membership":
            membership = database.session.execute(
                database.select(CompanyParty).filter_by(party_id=ctx["supplier_id"], company="cacao")
            ).scalar_one()
            membership.is_active = False
        elif mutate == "missing_membership":
            database.session.execute(
                database.delete(CompanyParty).where(
                    CompanyParty.party_id == ctx["supplier_id"], CompanyParty.company == "cacao"
                )
            )
        database.session.commit()
        before = database.session.execute(database.select(database.func.count(PurchaseOrder.id))).scalar()

    response = authenticated_client("admin").post(
        "/buying/purchase-order/new",
        data={
            "company": "cacao",
            "supplier_id": ctx["supplier_id"],
            "posting_date": "2026-05-15",
            "naming_series": ctx["series_id"],
            "transaction_currency": "NIO",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert mensaje in response.get_data(as_text=True)
    with app.app_context():
        after = database.session.execute(database.select(database.func.count(PurchaseOrder.id))).scalar()
        assert after == before


def test_purchase_order_new_post_accepts_valid_supplier(app, authenticated_client, po_http_context):
    """Control positivo: el mismo POST con proveedor vigente sí crea la orden."""
    from cacao_accounting.database import PurchaseOrder

    ctx = po_http_context
    with app.app_context():
        before = database.session.execute(database.select(database.func.count(PurchaseOrder.id))).scalar()

    response = authenticated_client("admin").post(
        "/buying/purchase-order/new",
        data={
            "company": "cacao",
            "supplier_id": ctx["supplier_id"],
            "posting_date": "2026-05-15",
            "naming_series": ctx["series_id"],
            "transaction_currency": "NIO",
            "item_code_0": ctx["item_code"],
            "qty_0": "1",
            "rate_0": "10",
            "uom_0": "UND",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        after = database.session.execute(database.select(database.func.count(PurchaseOrder.id))).scalar()
        assert after == before + 1


def _orden_con_dos_proveedores(app):
    """Prepara una orden en borrador con un proveedor válido y otro mutable."""
    from datetime import date
    from decimal import Decimal

    from cacao_accounting.database import NamingSeries, PurchaseOrder
    from cacao_accounting.document_identifiers import assign_document_identifier, ensure_default_naming_series_for_company

    suffix = uuid4().hex[:6]
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["purchase_order"])
        valido = Party(code=f"V{suffix}", name="Proveedor valido", is_supplier=True, is_active=True)
        mutable = Party(code=f"I{suffix}", name="Proveedor mutable", is_supplier=True, is_active=True)
        database.session.add_all([valido, mutable])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=valido.id, is_active=True),
                CompanyParty(company="cacao", party_id=mutable.id, is_active=True),
            ]
        )
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="purchase_order", company="cacao")
        ).scalar_one()
        orden = PurchaseOrder(
            company="cacao",
            supplier_id=valido.id,
            supplier_name="Proveedor valido",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(orden)
        database.session.flush()
        assign_document_identifier(
            document=orden,
            entity_type="purchase_order",
            posting_date_raw=orden.posting_date,
            naming_series_id=series_id,
        )
        database.session.commit()
        return {
            "order_id": orden.id,
            "valid_id": valido.id,
            "mutable_id": mutable.id,
            "series_id": series_id,
            "party_ids": [valido.id, mutable.id],
        }


@pytest.fixture
def po_two_suppliers(app, entorno_contable):
    """Orden con dos proveedores y limpieza garantizada al terminar."""
    del entorno_contable
    data = _orden_con_dos_proveedores(app)
    yield data
    _purge_purchase_data(app, party_ids=data["party_ids"], order_ids=[data["order_id"]])


@pytest.mark.parametrize(
    ("invalidity", "mensaje"),
    [
        ("inactive_supplier", "no está habilitado como proveedor"),
        ("not_supplier", "no está habilitado como proveedor"),
        ("inactive_membership", "no está habilitado para la compañía"),
        ("missing_membership", "no está habilitado para la compañía"),
    ],
)
def test_purchase_order_edit_post_rejects_invalid_supplier(app, authenticated_client, po_two_suppliers, invalidity, mensaje):
    """#1823/#2328: la edición rechaza proveedor inválido o sin vínculo."""
    from cacao_accounting.database import PurchaseOrder

    data = po_two_suppliers
    orden_id = data["order_id"]
    valido_id = data["valid_id"]
    mutable_id = data["mutable_id"]
    with app.app_context():
        proveedor = database.session.get(Party, mutable_id)
        if invalidity == "inactive_supplier":
            proveedor.is_active = False
        elif invalidity == "not_supplier":
            proveedor.is_supplier = False
        elif invalidity == "inactive_membership":
            vinculo = database.session.execute(
                database.select(CompanyParty).filter_by(party_id=mutable_id, company="cacao")
            ).scalar_one()
            vinculo.is_active = False
        elif invalidity == "missing_membership":
            database.session.execute(
                database.delete(CompanyParty).where(CompanyParty.party_id == mutable_id, CompanyParty.company == "cacao")
            )
        database.session.commit()

    response = authenticated_client("admin").post(
        f"/buying/purchase-order/{orden_id}/edit",
        data={
            "company": "cacao",
            "supplier_id": mutable_id,
            "posting_date": "2026-05-15",
            "naming_series": data["series_id"],
            "transaction_currency": "NIO",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert mensaje in response.get_data(as_text=True)
    with app.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden is not None
        assert orden.supplier_id == valido_id


def test_purchase_order_edit_post_accepts_valid_supplier(app, authenticated_client, po_http_context, po_two_suppliers):
    """Control positivo: la edición con proveedor vigente sí se persiste."""
    from cacao_accounting.database import PurchaseOrder

    ctx = po_http_context
    data = po_two_suppliers
    orden_id = data["order_id"]
    with app.app_context():
        database.session.get(PurchaseOrder, orden_id).supplier_id = None
        database.session.commit()

    response = authenticated_client("admin").post(
        f"/buying/purchase-order/{orden_id}/edit",
        data={
            "company": "cacao",
            "supplier_id": data["valid_id"],
            "posting_date": "2026-05-15",
            "naming_series": data["series_id"],
            "transaction_currency": "NIO",
            "item_code_0": ctx["item_code"],
            "qty_0": "1",
            "rate_0": "10",
            "uom_0": "UND",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden is not None
        assert orden.supplier_id == data["valid_id"]
