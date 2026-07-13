# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas unitarias para el Approval Engine (Motor de Aprobaciones)."""

from decimal import Decimal
import pytest
from flask_login import login_user
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Entity,
    Roles,
    RolesUser,
    User,
    ApprovalMatrix,
    ApprovalRequest,
    ApprovalAction,
    CacaoConfig,
    ComprobanteContable,
    PurchaseOrder,
)
from cacao_accounting.approval_engine import ApprovalEngine


@pytest.fixture(name="app")
def fixture_app():
    """Crea una instancia de la aplicación en modo de pruebas."""
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture(name="client")
def fixture_client(app):
    """Cliente de pruebas HTTP."""
    return app.test_client()


def test_approval_engine_is_enabled(app):
    """Prueba la habilitación del Approval Engine por compañía."""
    with app.app_context():
        # Por defecto, deshabilitado
        assert not ApprovalEngine.is_enabled("comp_test")

        # Habilitado en CacaoConfig
        cfg = CacaoConfig(key="approval_engine_enabled_comp_test", value="True")
        database.session.add(cfg)
        database.session.commit()

        assert ApprovalEngine.is_enabled("comp_test")


def test_approval_engine_get_document_amount(app):
    """Prueba la resolución de montos para distintos tipos documentales."""
    with app.app_context():
        # Documento operativo estándar con grand_total
        po = PurchaseOrder(grand_total=Decimal("1500.50"))
        assert ApprovalEngine.get_document_amount(po) == Decimal("1500.50")

        # Comprobante contable sin grand_total pero con propiedad total calculada
        journal = ComprobanteContable(id="journal123")
        database.session.add(journal)
        database.session.commit()
        # total de un journal sin líneas es 0
        assert ApprovalEngine.get_document_amount(journal) == Decimal("0")


def test_approval_matrix_rules_priority(app):
    """Prueba la prioridad de evaluación (Reglas de usuario > Reglas de rol)."""
    with app.app_context():
        # Habilitar el motor de aprobaciones para la compañía de prueba
        cfg = CacaoConfig(key="approval_engine_enabled_comp_test", value="True")
        database.session.add(cfg)

        # Setup de roles y usuarios
        rol_buyer = Roles(name="Buyer", note="Comprador")
        database.session.add(rol_buyer)
        database.session.flush()

        user_juan = User(user="juan", name="Juan Pérez", classification="user", password=b"securepassword")
        database.session.add(user_juan)
        database.session.flush()

        # Asignar rol a juan
        ru = RolesUser(user_id=user_juan.id, role_id=rol_buyer.id, active=True)
        database.session.add(ru)

        # Regla por rol: Buyer puede aprobar hasta 5,000
        rule_role = ApprovalMatrix(
            company_id="comp_test",
            document_type="purchase_order",
            role_id=rol_buyer.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("5000"),
            approval_level=1,
            enabled=True,
        )
        database.session.add(rule_role)

        # Excepción por usuario: Juan Pérez puede aprobar hasta 15,000
        rule_user = ApprovalMatrix(
            company_id="comp_test",
            document_type="purchase_order",
            user_id=user_juan.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("15000"),
            approval_level=1,
            enabled=True,
        )
        database.session.add(rule_user)
        database.session.commit()

        # Caso 1: Orden de 12,000. Juan Pérez debería poder aprobar debido a su regla específica.
        po = PurchaseOrder(company="comp_test", grand_total=Decimal("12000"))
        assert ApprovalEngine.can_approve(po, user_juan)

        # Caso 2: Sin regla aplicable si superan el límite (e.g., 20,000)
        po_large = PurchaseOrder(company="comp_test", grand_total=Decimal("20000"))
        assert not ApprovalEngine.can_approve(po_large, user_juan)


def test_approval_flow_draft_to_approved(app):
    """Prueba el flujo completo de aprobaciones del Approval Engine (Draft -> Approved)."""
    with app.app_context():
        # Setup configuración global de aprobaciones
        cfg = CacaoConfig(key="approval_engine_enabled_comp_test", value="True")
        database.session.add(cfg)

        user_juan = User(user="juan", name="Juan Pérez", classification="user", password=b"securepassword")
        database.session.add(user_juan)
        database.session.flush()

        # Regla de aprobación de Juan Pérez
        rule = ApprovalMatrix(
            company_id="comp_test",
            document_type="purchase_order",
            user_id=user_juan.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("15000"),
            approval_level=1,
            enabled=True,
        )
        database.session.add(rule)

        po = PurchaseOrder(id="po10025", company="comp_test", grand_total=Decimal("12000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        # Solicitar aprobación
        req = ApprovalEngine.request_approval(po)
        assert req is not None
        assert req.status == "Pending Approval"
        assert req.required_level == 1

        # Juan aprueba la orden
        is_fully_approved = ApprovalEngine.approve(po, user_juan, "Autorizado")
        assert is_fully_approved
        assert req.status == "Approved"
        assert po.docstatus == 1


def test_approval_flow_rejection(app):
    """Prueba el rechazo de un documento."""
    with app.app_context():
        cfg = CacaoConfig(key="approval_engine_enabled_comp_test", value="True")
        database.session.add(cfg)

        user_juan = User(user="juan", name="Juan", classification="user", password=b"securepassword")
        database.session.add(user_juan)
        database.session.flush()

        rule = ApprovalMatrix(
            company_id="comp_test",
            document_type="purchase_order",
            user_id=user_juan.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("5000"),
            approval_level=1,
            enabled=True,
        )
        database.session.add(rule)

        po = PurchaseOrder(id="po_rej", company="comp_test", grand_total=Decimal("4000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        # Solicitar aprobación
        ApprovalEngine.request_approval(po)

        # Rechazar
        ApprovalEngine.reject(po, user_juan, "Rechazado")

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type="purchase_order", document_id="po_rej")
        ).scalar_one()
        assert req.status == "Rejected"
        assert po.docstatus == 0  # Permanece en borrador


def test_pending_approvals_view(app, client):
    """Prueba el endpoint de Mis Aprobaciones Pendientes."""
    with app.app_context():
        # Configurar usuario y compañía
        user_juan = User(user="juan", name="Juan", classification="user", active=True, password=b"securepassword")
        database.session.add(user_juan)
        database.session.flush()

        po = PurchaseOrder(id="po_view_test", company="comp_test", grand_total=Decimal("3000"), docstatus=0)
        database.session.add(po)

        # Rule that allows Juan to approve
        rule = ApprovalMatrix(
            company_id="comp_test",
            document_type="purchase_order",
            user_id=user_juan.id,
            min_amount=Decimal("0"),
            max_amount=Decimal("5000"),
            approval_level=1,
            enabled=True,
        )
        database.session.add(rule)

        # Configuración global activa
        cfg = CacaoConfig(key="approval_engine_enabled_comp_test", value="True")
        database.session.add(cfg)
        database.session.commit()

        # Crear solicitud de aprobación
        ApprovalEngine.request_approval(po)
        database.session.commit()

        # Simular Login de Juan Pérez
        with client.session_transaction() as sess:
            sess["_user_id"] = user_juan.id

        # Realizar GET a /me/pending-approvals
        response = client.get("/me/pending-approvals")
        assert response.status_code == 200
        assert b"po_view_test" in response.data
