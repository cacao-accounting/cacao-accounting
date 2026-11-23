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
