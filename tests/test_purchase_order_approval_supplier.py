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
    from cacao_accounting.database import NamingSeries
    from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

    suffix = uuid4().hex[:6]
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["purchase_order"])
        supplier = Party(code=f"SUP{suffix}", name=f"Proveedor {suffix}", is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=supplier.id, is_active=True))
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="purchase_order", company="cacao")
        ).scalar_one()
        database.session.commit()
        return {"supplier_id": supplier.id, "series_id": series_id}


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        ("inactive_supplier", "habilitado como proveedor"),
        ("inactive_membership", "habilitado para la compañía"),
        ("not_supplier", "habilitado como proveedor"),
    ],
)
def test_purchase_order_new_post_rejects_invalid_supplier(app, authenticated_client, entorno_contable, mutate, expected):
    """#1823: alta manual HTTP no crea OC con proveedor inválido o sin vínculo activo."""
    from cacao_accounting.database import PurchaseOrder

    del entorno_contable, expected
    ctx = _purchase_order_http_context(app)
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
    )

    assert response.status_code in {200, 302}
    with app.app_context():
        after = database.session.execute(database.select(database.func.count(PurchaseOrder.id))).scalar()
        assert after == before


def test_purchase_order_edit_post_rejects_invalid_supplier(app, authenticated_client, entorno_contable):
    """#1823: edición HTTP no muta OC con proveedor cuya membresía fue revocada."""
    from decimal import Decimal

    from cacao_accounting.database import NamingSeries, PurchaseOrder
    from cacao_accounting.document_identifiers import assign_document_identifier, ensure_default_naming_series_for_company

    del entorno_contable
    suffix = uuid4().hex[:6]
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["purchase_order"])
        valid = Party(code=f"V{suffix}", name="Proveedor valido", is_supplier=True, is_active=True)
        invalid = Party(code=f"I{suffix}", name="Proveedor invalido", is_supplier=True, is_active=True)
        database.session.add_all([valid, invalid])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=valid.id, is_active=True),
                CompanyParty(company="cacao", party_id=invalid.id, is_active=True),
            ]
        )
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="purchase_order", company="cacao")
        ).scalar_one()
        po = PurchaseOrder(
            company="cacao",
            supplier_id=valid.id,
            supplier_name="Proveedor valido",
            posting_date=__import__("datetime").date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(po)
        database.session.flush()
        assign_document_identifier(
            document=po,
            entity_type="purchase_order",
            posting_date_raw=po.posting_date,
            naming_series_id=series_id,
        )
        database.session.commit()
        po_id = po.id
        invalid_id = invalid.id
        membership = database.session.execute(
            database.select(CompanyParty).filter_by(party_id=invalid.id, company="cacao")
        ).scalar_one()
        membership.is_active = False
        database.session.commit()

    response = authenticated_client("admin").post(
        f"/buying/purchase-order/{po_id}/edit",
        data={
            "company": "cacao",
            "supplier_id": invalid_id,
            "posting_date": "2026-05-15",
            "naming_series": series_id,
            "transaction_currency": "NIO",
        },
    )

    assert response.status_code in {200, 302}
    with app.app_context():
        po = database.session.get(PurchaseOrder, po_id)
        assert po is not None
        assert po.supplier_id != invalid_id
