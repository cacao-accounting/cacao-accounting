# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas unitarias para el Approval Engine (Motor de Aprobaciones)."""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Roles,
    RolesUser,
    User,
    ApprovalMatrix,
    ApprovalRequest,
    ApprovalAction,
    CacaoConfig,
    ComprobanteContable,
    PurchaseOrder,
    PurchaseRequest,
    PaymentEntry,
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


def _enable_engine(company_id: str = "comp_test") -> None:
    """Habilita el motor de aprobaciones para una compañía."""
    cfg = CacaoConfig(key=f"approval_engine_enabled_{company_id}", value="True")
    database.session.add(cfg)
    database.session.flush()


def _create_user(username: str = "juan", classification: str = "user") -> User:
    """Crea un usuario de prueba."""
    user = User(user=username, name=username.title(), classification=classification, password=b"testpass")
    database.session.add(user)
    database.session.flush()
    return user


def _create_role(name: str, note: str = "") -> Roles:
    """Crea un rol de prueba."""
    rol = Roles(name=name, note=note or name)
    database.session.add(rol)
    database.session.flush()
    return rol


def _assign_role(user: User, role: Roles) -> RolesUser:
    """Asigna un rol a un usuario."""
    ru = RolesUser(user_id=user.id, role_id=role.id, active=True)
    database.session.add(ru)
    database.session.flush()
    return ru


def _create_rule(
    company_id: str,
    document_type: str,
    role_id: str | None = None,
    user_id: str | None = None,
    min_amount: Decimal = Decimal("0"),
    max_amount: Decimal | None = None,
    approval_level: int = 1,
    enabled: bool = True,
) -> ApprovalMatrix:
    """Crea una regla de aprobación."""
    rule = ApprovalMatrix(
        company_id=company_id,
        document_type=document_type,
        role_id=role_id,
        user_id=user_id,
        min_amount=min_amount,
        max_amount=max_amount,
        approval_level=approval_level,
        enabled=enabled,
    )
    database.session.add(rule)
    database.session.flush()
    return rule


# ---------------------------------------------------------------------------
# Tests existentes (mantenidos)
# ---------------------------------------------------------------------------


def test_approval_engine_is_enabled(app):
    """Prueba la habilitación del Approval Engine por compañía."""
    with app.app_context():
        assert not ApprovalEngine.is_enabled("comp_test")
        _enable_engine()
        assert ApprovalEngine.is_enabled("comp_test")


def test_approval_engine_get_document_amount(app):
    """Prueba la resolución de montos para distintos tipos documentales."""
    with app.app_context():
        po = PurchaseOrder(grand_total=Decimal("1500.50"))
        assert ApprovalEngine.get_document_amount(po) == Decimal("1500.50")

        journal = ComprobanteContable(id="journal123")
        database.session.add(journal)
        database.session.commit()
        assert ApprovalEngine.get_document_amount(journal) == Decimal("0")


def test_approval_matrix_rules_priority(app):
    """Prueba la prioridad de evaluación (Reglas de usuario > Reglas de rol)."""
    with app.app_context():
        _enable_engine()
        rol_buyer = _create_role("Buyer", "Comprador")
        user_juan = _create_user("juan")
        _assign_role(user_juan, rol_buyer)

        _create_rule("comp_test", "purchase_order", role_id=rol_buyer.id, max_amount=Decimal("5000"))
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("15000"))

        po = PurchaseOrder(company="comp_test", grand_total=Decimal("12000"))
        assert ApprovalEngine.can_approve(po, user_juan)

        po_large = PurchaseOrder(company="comp_test", grand_total=Decimal("20000"))
        assert not ApprovalEngine.can_approve(po_large, user_juan)


def test_approval_flow_draft_to_approved(app):
    """Prueba el flujo completo de aprobaciones (Draft -> Approved)."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("15000"))

        po = PurchaseOrder(id="po10025", company="comp_test", grand_total=Decimal("12000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        req = ApprovalEngine.request_approval(po)
        assert req is not None
        assert req.status == "Pending Approval"
        assert req.required_level == 1

        is_fully_approved = ApprovalEngine.approve(po, user_juan, "Autorizado")
        assert is_fully_approved
        assert req.status == "Approved"
        assert po.docstatus == 1


def test_approval_flow_rejection(app):
    """Prueba el rechazo de un documento."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("5000"))

        po = PurchaseOrder(id="po_rej", company="comp_test", grand_total=Decimal("4000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_approval(po)
        ApprovalEngine.reject(po, user_juan, "Rechazado")

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type="purchase_order", document_id="po_rej")
        ).scalar_one()
        assert req.status == "Rejected"
        assert po.docstatus == 0


def test_pending_approvals_view(app, client):
    """Prueba el endpoint de Mis Aprobaciones Pendientes."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("5000"))

        po = PurchaseOrder(id="po_view_test", company="comp_test", grand_total=Decimal("3000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_approval(po)
        database.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user_juan.id

        response = client.get("/me/pending-approvals")
        assert response.status_code == 200
        assert b"po_view_test" in response.data


# ---------------------------------------------------------------------------
# Tests nuevos: Multi-level approval
# ---------------------------------------------------------------------------


def test_multilevel_approval_three_levels(app):
    """Prueba aprobación multi-nivel: Buyer(1) < PM(2) < CFO(3)."""
    with app.app_context():
        _enable_engine()

        rol_buyer = _create_role("Buyer", "Comprador")
        rol_pm = _create_role("Purchase Manager", "Gerente de Compras")
        rol_cfo = _create_role("CFO", "Director Financiero")

        user_juan = _create_user("juan")
        user_maria = _create_user("maria")
        user_pedro = _create_user("pedro")
        _assign_role(user_juan, rol_buyer)
        _assign_role(user_maria, rol_pm)
        _assign_role(user_pedro, rol_cfo)

        _create_rule("comp_test", "purchase_order", role_id=rol_buyer.id, max_amount=Decimal("5000"), approval_level=1)
        _create_rule("comp_test", "purchase_order", role_id=rol_pm.id, max_amount=Decimal("50000"), approval_level=2)
        _create_rule("comp_test", "purchase_order", role_id=rol_cfo.id, max_amount=None, approval_level=3)

        po = PurchaseOrder(id="po_multi", company="comp_test", grand_total=Decimal("42000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        req = ApprovalEngine.request_approval(po)
        assert req.required_level == 2

        # Buyer (nivel 1) no puede aprobar 42,000 (requiere nivel 2)
        assert not ApprovalEngine.can_approve(po, user_juan)

        # PM (nivel 2) puede aprobar 42,000
        assert ApprovalEngine.can_approve(po, user_maria)

        # PM aprueba → nivel alcanzado
        result = ApprovalEngine.approve(po, user_maria, "Aprobado por PM")
        assert result is True
        assert req.status == "Approved"
        assert po.docstatus == 1


def test_multilevel_approval_tiers(app):
    """Prueba que distintos montos requieren distintos niveles de aprobación."""
    with app.app_context():
        _enable_engine()

        rol_pm = _create_role("PM", "Gerente")
        rol_cfo = _create_role("CFO", "Director")

        user_maria = _create_user("maria")
        user_pedro = _create_user("pedro")
        _assign_role(user_maria, rol_pm)
        _assign_role(user_pedro, rol_cfo)

        _create_rule("comp_test", "purchase_order", role_id=rol_pm.id, max_amount=Decimal("50000"), approval_level=1)
        _create_rule("comp_test", "purchase_order", role_id=rol_cfo.id, max_amount=None, approval_level=2)

        po_low = PurchaseOrder(id="po_low", company="comp_test", grand_total=Decimal("30000"), docstatus=0)
        database.session.add(po_low)
        database.session.commit()

        req_low = ApprovalEngine.request_approval(po_low)
        assert req_low.required_level == 1

        assert ApprovalEngine.can_approve(po_low, user_maria)
        result = ApprovalEngine.approve(po_low, user_maria, "PM aprueba low")
        assert result is True
        assert req_low.status == "Approved"

        po_high = PurchaseOrder(id="po_high", company="comp_test", grand_total=Decimal("100000"), docstatus=0)
        database.session.add(po_high)
        database.session.commit()

        req_high = ApprovalEngine.request_approval(po_high)
        assert req_high.required_level == 2

        assert not ApprovalEngine.can_approve(po_high, user_maria)

        assert ApprovalEngine.can_approve(po_high, user_pedro)
        result = ApprovalEngine.approve(po_high, user_pedro, "CFO aprueba high")
        assert result is True
        assert req_high.status == "Approved"


# ---------------------------------------------------------------------------
# Tests nuevos: Cancelación con aprobación
# ---------------------------------------------------------------------------


def test_cancellation_request(app):
    """Prueba que request_cancellation crea una solicitud de cancelación."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_cancel", company="comp_test", grand_total=Decimal("5000"), docstatus=1)
        database.session.add(po)
        database.session.commit()

        req = ApprovalEngine.request_cancellation(po)
        assert req is not None
        assert req.status == "Pending Cancellation"
        assert req.document_type == "cancel_purchase_order"
        assert po.docstatus == 1  # Sigue aprobado


def test_cancellation_approval(app):
    """Prueba que la aprobación de cancelación ejecuta _execute_cancel."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_request", user_id=user_juan.id, max_amount=Decimal("50000"))

        pr = PurchaseRequest(id="pr_cancel", company="comp_test", grand_total=Decimal("3000"), docstatus=1)
        database.session.add(pr)
        database.session.commit()

        ApprovalEngine.request_cancellation(pr)
        result = ApprovalEngine.approve(pr, user_juan, "Cancelación autorizada")
        assert result is True

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type="cancel_purchase_request", document_id="pr_cancel")
        ).scalar_one()
        assert req.status == "Approved"
        assert pr.docstatus == 2


def test_cancellation_rejection(app):
    """Prueba que el rechazo de cancelación mantiene el documento activo."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_rej_cancel", company="comp_test", grand_total=Decimal("8000"), docstatus=1)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_cancellation(po)
        ApprovalEngine.reject(po, user_juan, "No autorizado")

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type="cancel_purchase_order", document_id="po_rej_cancel")
        ).scalar_one()
        assert req.status == "Rejected"
        assert po.docstatus == 1  # Sigue activo


# ---------------------------------------------------------------------------
# Tests nuevos: Modo Escritorio
# ---------------------------------------------------------------------------


def test_desktop_mode_disables_engine(app):
    """Prueba que el Approval Engine está deshabilitado en modo escritorio."""
    with app.app_context():
        app.config["MODO_ESCRITORIO"] = True
        _enable_engine()
        assert not ApprovalEngine.is_enabled("comp_test")


def test_desktop_mode_can_approve_returns_true(app):
    """Prueba que can_approve retorna True en modo escritorio sin reglas."""
    with app.app_context():
        app.config["MODO_ESCRITORIO"] = True
        _enable_engine()
        user_juan = _create_user("juan")
        po = PurchaseOrder(company="comp_test", grand_total=Decimal("999999"))
        assert ApprovalEngine.can_approve(po, user_juan)


def test_desktop_mode_request_approval_returns_none(app):
    """Prueba que request_approval retorna None en modo escritorio."""
    with app.app_context():
        app.config["MODO_ESCRITORIO"] = True
        _enable_engine()
        po = PurchaseOrder(id="po_desktop", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()
        result = ApprovalEngine.request_approval(po)
        assert result is None


def test_handle_submission_returns_false_in_desktop(app):
    """Prueba que handle_submission retorna False en modo escritorio."""
    with app.app_context():
        app.config["MODO_ESCRITORIO"] = True
        _enable_engine()
        user_juan = _create_user("juan")
        po = PurchaseOrder(id="po_hs_desktop", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()
        result = ApprovalEngine.handle_submission(po, user_juan, "Test")
        assert result is False


# ---------------------------------------------------------------------------
# Tests nuevos: Edge cases
# ---------------------------------------------------------------------------


def test_document_with_no_amount(app):
    """Prueba que documentos sin monto retornan 0."""
    with app.app_context():
        po = PurchaseOrder(company="comp_test")
        assert ApprovalEngine.get_document_amount(po) == Decimal("0")


def test_user_without_roles(app):
    """Prueba que usuario sin roles no tiene reglas aplicables."""
    with app.app_context():
        _enable_engine()
        user_orphan = _create_user("orphan")
        rules = ApprovalEngine._get_user_rules(user_orphan.id, "comp_test", "purchase_order")
        assert rules == []


def test_disabled_rule_not_evaluated(app):
    """Prueba que reglas deshabilitadas no se evalúan."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("5000"), enabled=False)

        po = PurchaseOrder(company="comp_test", grand_total=Decimal("3000"))
        assert not ApprovalEngine.can_approve(po, user_juan)


def test_request_approval_no_rule_returns_none(app):
    """Prueba que request_approval retorna None cuando no hay regla que cubra el monto."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("1000"))

        po = PurchaseOrder(id="po_no_rule", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        result = ApprovalEngine.request_approval(po)
        assert result is None


def test_request_approval_existing_request(app):
    """Prueba que request_approval retorna la solicitud existente si ya existe."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_exists", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        req1 = ApprovalEngine.request_approval(po)
        req2 = ApprovalEngine.request_approval(po)
        assert req1 is not None
        assert req2 is not None
        assert req1.id == req2.id


def test_approve_already_approved_request(app):
    """Prueba que approve sobre solicitud ya aprobada retorna True sin acción."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_already", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_approval(po)
        ApprovalEngine.approve(po, user_juan)

        # Intentar aprobar de nuevo
        result = ApprovalEngine.approve(po, user_juan, "Segunda vez")
        assert result is True


def test_reject_without_pending_request(app):
    """Prueba que reject sin solicitud pendiente lanza ValueError."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_no_req", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        with pytest.raises(ValueError, match="No existe ninguna solicitud"):
            ApprovalEngine.reject(po, user_juan, "Test")


def test_next_approver_no_pending(app):
    """Prueba que next_approver retorna dict vacío sin solicitud pendiente."""
    with app.app_context():
        _enable_engine()
        po = PurchaseOrder(id="po_next", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()
        result = ApprovalEngine.next_approver(po)
        assert result == {}


def test_next_approver_with_pending(app):
    """Prueba que next_approver retorna roles/usuarios disponibles."""
    with app.app_context():
        _enable_engine()
        rol_cfo = _create_role("CFO", "Director Financiero")
        user_pedro = _create_user("pedro")
        _assign_role(user_pedro, rol_cfo)

        _create_rule("comp_test", "purchase_order", role_id=rol_cfo.id, max_amount=None, approval_level=1)

        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("1000"), approval_level=1)

        po = PurchaseOrder(id="po_next2", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_approval(po)
        database.session.commit()

        approvers = ApprovalEngine.next_approver(po)
        assert "roles" in approvers
        assert "users" in approvers
        assert "Director Financiero" in approvers["roles"]


# ---------------------------------------------------------------------------
# Tests nuevos: Auditoría (ApprovalAction)
# ---------------------------------------------------------------------------


def test_approval_action_on_approve(app):
    """Prueba que se registra ApprovalAction al aprobar con todos los campos."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("15000"))

        po = PurchaseOrder(id="po_audit", company="comp_test", grand_total=Decimal("12000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_approval(po)
        ApprovalEngine.approve(po, user_juan, "Aprobado con comentario")
        database.session.commit()

        action = database.session.execute(select(ApprovalAction).filter_by(approved_by=user_juan.id)).scalar_one()
        assert action.action == "approve"
        assert action.comments == "Aprobado con comentario"
        assert action.document_amount == Decimal("12000")
        assert action.limit_allowed == Decimal("15000")
        assert action.level == 1
        assert action.approved_by == user_juan.id


def test_approval_action_on_reject(app):
    """Prueba que se registra ApprovalAction al rechazar."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("5000"))

        po = PurchaseOrder(id="po_rej_audit", company="comp_test", grand_total=Decimal("4000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine.request_approval(po)
        ApprovalEngine.reject(po, user_juan, "Rechazado por política")
        database.session.commit()

        action = database.session.execute(select(ApprovalAction).filter_by(approved_by=user_juan.id)).scalar_one()
        assert action.action == "reject"
        assert action.comments == "Rechazado por política"
        assert action.document_amount == Decimal("4000")


# ---------------------------------------------------------------------------
# Tests nuevos: _execute_submit por tipo documental
# ---------------------------------------------------------------------------


def test_execute_submit_purchase_request(app):
    """Prueba que _execute_submit para purchase_request hace docstatus=1 directo."""
    with app.app_context():
        user_juan = _create_user("juan")
        pr = PurchaseRequest(id="pr_exec", company="comp_test", grand_total=Decimal("1000"), docstatus=0)
        database.session.add(pr)
        database.session.commit()

        ApprovalEngine._execute_submit("purchase_request", pr, user_juan)
        assert pr.docstatus == 1


def test_execute_submit_purchase_order(app):
    """Prueba que _execute_submit para purchase_order hace docstatus=1 directo."""
    with app.app_context():
        user_juan = _create_user("juan")
        po = PurchaseOrder(id="po_exec", company="comp_test", grand_total=Decimal("1000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine._execute_submit("purchase_order", po, user_juan)
        assert po.docstatus == 1


def test_execute_cancel_purchase_request(app):
    """Prueba que _execute_cancel para purchase_request hace docstatus=2."""
    with app.app_context():
        user_juan = _create_user("juan")
        pr = PurchaseRequest(id="pr_cancel_exec", company="comp_test", grand_total=Decimal("1000"), docstatus=1)
        database.session.add(pr)
        database.session.commit()

        ApprovalEngine._execute_cancel("purchase_request", pr, user_juan)
        assert pr.docstatus == 2


def test_execute_cancel_purchase_order(app):
    """Prueba que _execute_cancel para purchase_order hace docstatus=2."""
    with app.app_context():
        user_juan = _create_user("juan")
        po = PurchaseOrder(id="po_cancel_exec", company="comp_test", grand_total=Decimal("1000"), docstatus=1)
        database.session.add(po)
        database.session.commit()

        ApprovalEngine._execute_cancel("purchase_order", po, user_juan)
        assert po.docstatus == 2


# ---------------------------------------------------------------------------
# Tests nuevos: handle_submission helper
# ---------------------------------------------------------------------------


def test_handle_submission_engine_disabled(app):
    """Prueba que handle_submission retorna False cuando el engine está deshabilitado."""
    with app.app_context():
        user_juan = _create_user("juan")
        po = PurchaseOrder(id="po_hs_dis", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()
        result = ApprovalEngine.handle_submission(po, user_juan, "Test")
        assert result is False


def test_handle_submission_no_rule(app):
    """Prueba que handle_submission retorna True pero no aprueba cuando no hay regla."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        po = PurchaseOrder(id="po_hs_norule", company="comp_test", grand_total=Decimal("99999"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        with app.test_request_context():
            result = ApprovalEngine.handle_submission(po, user_juan, "Test")
        assert result is True
        assert po.docstatus == 0  # Sigue en borrador


def test_handle_submission_auto_approve(app):
    """Prueba que handle_submission aprueba directamente cuando el usuario tiene autoridad."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        _create_rule("comp_test", "purchase_order", user_id=user_juan.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_hs_auto", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        with app.test_request_context():
            result = ApprovalEngine.handle_submission(po, user_juan, "Orden de prueba")
        assert result is True
        assert po.docstatus == 1


def test_handle_submission_pending(app):
    """Prueba que handle_submission deja pendiente cuando el usuario no tiene autoridad."""
    with app.app_context():
        _enable_engine()
        user_juan = _create_user("juan")
        user_maria = _create_user("maria")
        _create_rule("comp_test", "purchase_order", user_id=user_maria.id, max_amount=Decimal("50000"))

        po = PurchaseOrder(id="po_hs_pending", company="comp_test", grand_total=Decimal("5000"), docstatus=0)
        database.session.add(po)
        database.session.commit()

        with app.test_request_context():
            result = ApprovalEngine.handle_submission(po, user_juan, "Orden de prueba")
        assert result is True
        assert po.docstatus == 0

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type="purchase_order", document_id="po_hs_pending")
        ).scalar_one()
        assert req.status == "Pending Approval"


# ---------------------------------------------------------------------------
# Tests nuevos: _get_required_level
# ---------------------------------------------------------------------------


def test_get_required_level_no_rules_returns_zero(app):
    """Prueba que _get_required_level retorna 0 cuando no hay reglas."""
    with app.app_context():
        _enable_engine()
        level = ApprovalEngine._get_required_level("comp_test", "purchase_order", Decimal("5000"))
        assert level == 0


def test_get_required_level_selects_minimum(app):
    """Prueba que _get_required_level selecciona el nivel mínimo que cubra el monto."""
    with app.app_context():
        _enable_engine()
        _create_rule("comp_test", "purchase_order", max_amount=Decimal("5000"), approval_level=1)
        _create_rule("comp_test", "purchase_order", max_amount=Decimal("50000"), approval_level=2)
        _create_rule("comp_test", "purchase_order", max_amount=None, approval_level=3)

        # Para 3,000: todas cubren → nivel mínimo = 1
        assert ApprovalEngine._get_required_level("comp_test", "purchase_order", Decimal("3000")) == 1
        # Para 30,000: nivel 2 y 3 cubren → nivel mínimo = 2
        assert ApprovalEngine._get_required_level("comp_test", "purchase_order", Decimal("30000")) == 2
        # Para 300,000: solo nivel 3 cubre → nivel = 3
        assert ApprovalEngine._get_required_level("comp_test", "purchase_order", Decimal("300000")) == 3


def test_deferred_approval_rejects_changed_payment_snapshot(app):
    """El hash persistido detecta cambios aunque el timestamp no avance."""
    with app.app_context():
        _enable_engine()
        user = _create_user("snapshot_user")
        _create_rule("comp_test", "payment_entry", user_id=user.id, max_amount=Decimal("5000"))
        payment = PaymentEntry(
            id="payment_snapshot",
            company="comp_test",
            posting_date=date(2026, 6, 1),
            payment_type="pay",
            bank_account_id="bank-1",
            paid_amount=Decimal("100.00"),
            docstatus=0,
        )
        database.session.add(payment)
        database.session.commit()

        request = ApprovalEngine.request_approval(payment)
        assert request is not None
        payment.paid_amount = Decimal("250.00")
        with pytest.raises(ValueError, match="cambió después"):
            ApprovalEngine._assert_approval_snapshot(request, payment)


def test_final_payment_submission_revalidates_header(app):
    """Un pago diferido no puede aprobarse con encabezado inválido."""
    with app.app_context():
        payment = PaymentEntry(
            company="comp_test",
            posting_date=date(2026, 6, 1),
            payment_type="pay",
            paid_amount=Decimal("0"),
            docstatus=0,
        )
        with pytest.raises(ValueError, match="monto del pago"):
            ApprovalEngine._validate_final_submission("payment_entry", payment)
