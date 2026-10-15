# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Independent approval policies preserve RBAC, tenant scope and preparer ranks."""

from types import SimpleNamespace

import pytest

from cacao_accounting import approval_policy as policy
from cacao_accounting.approval_engine import ApprovalEngine, assert_execution_authorized
from cacao_accounting.database import CacaoConfig, Modules, RolesAccess, UserCompanyAccess, database
from tests.test_approval_engine import (
    _assign_role,
    _create_role,
    _create_rule,
    _create_user,
    _enable_engine,
    fixture_app as approval_app,
)

app = approval_app


@pytest.fixture(autouse=True)
def cloud_mode(app):
    """Keep Cloud approval semantics explicit when the suite runs on Desktop."""
    app.config["MODO_ESCRITORIO"] = False


def _actor(name, module, rank, *, approve=True, scope=True):
    """Create an active classified user with independently assigned authority."""
    user = _create_user(name)
    user.active = True
    role = _create_role(name)
    _assign_role(user, role)
    database.session.add(RolesAccess(rol_id=role.id, module_id=module.id, access=True, approve=approve, approval_rank=rank))
    if not scope:
        for access in database.session.execute(database.select(UserCompanyAccess).filter_by(user_id=user.id)).scalars():
            database.session.delete(access)
    database.session.flush()
    return user


def test_independent_authority_matrix(app):
    """A rank never grants permission, scope, activity or self-approval rights."""
    with app.app_context():
        module = Modules(module="purchases", default=True, enabled=True)
        database.session.add(module)
        database.session.flush()
        manager = _actor("manager", module, 3)
        auxiliary = _actor("aux", module, 2)
        user = _actor("user", module, 1)
        no_permission = _actor("no_permission", module, 3, approve=False)
        no_scope = _actor("no_scope", module, 3, scope=False)
        unclassified = _actor("unclassified", module, None)
        admin = _create_user("admin", "admin")
        admin.active = True
        role_admin = _create_user("role_admin")
        role_admin.active = True
        assignment = _assign_role(role_admin, _create_role("admin"))
        snapshot = {"module": "purchases", "preparers": [{"user_id": admin.id, "rank": 4}]}
        assert not policy.permits_independent_approval(snapshot, manager, "comp_test")
        assert policy.permits_independent_approval(snapshot, role_admin, "comp_test")
        for rejected in (admin, auxiliary, user, no_permission, no_scope, unclassified):
            assert not policy.permits_independent_approval(snapshot, rejected, "comp_test")
        snapshot["preparers"] = [{"user_id": manager.id, "rank": 3}]
        assert policy.permits_independent_approval(snapshot, admin, "comp_test")
        assert not policy.permits_independent_approval(snapshot, auxiliary, "comp_test")
        snapshot["preparers"] = [{"user_id": user.id, "rank": 1}]
        assert policy.permits_independent_approval(snapshot, auxiliary, "comp_test")
        assignment.active = False
        from cacao_accounting.auth.permisos import Permisos
        from cacao_accounting.auth.roles import tiene_rol

        assert not tiene_rol(role_admin.id, "admin")
        assert not Permisos(modulo=module.id, usuario=role_admin.id).administrador
        assert not Permisos(modulo=module.id, usuario=role_admin.id).access
        assert not policy.is_admin(role_admin)
        assert policy.module_rank(role_admin, "purchases") is None
        auxiliary.active = False
        assert not Permisos(modulo=module.id, usuario=auxiliary.id).access
        assert not policy.authorized(auxiliary, "comp_test", "purchases")
        assert not policy.authorized(admin, "absent", "purchases")
        assert not policy.permits_independent_approval({"module": "purchases", "preparers": []}, manager, "comp_test")
        snapshot["preparers"] = [{"user_id": user.id, "rank": None}]
        assert not policy.permits_independent_approval(snapshot, manager, "comp_test")


def test_preparer_snapshot_and_persisted_policy(app):
    """Creator, last editor and requester remain excluded after configuration changes."""
    with app.app_context():
        _enable_engine()
        module = Modules(module="purchases", default=True, enabled=True)
        database.session.add(module)
        database.session.flush()
        creator = _actor("creator", module, 1)
        editor = _actor("editor", module, 2)
        requester = _actor("requester", module, 3)
        manager = _actor("manager", module, 3)
        doc = SimpleNamespace(
            id="document",
            company="comp_test",
            document_type="purchase_order",
            created_by=creator.id,
            modified_by=editor.id,
            grand_total=100,
        )
        snapshot = policy.build_policy(doc, requester.id, "purchase_order")
        assert {item["user_id"] for item in snapshot["preparers"]} == {creator.id, editor.id, requester.id}
        for preparer in (creator, editor, requester):
            assert not policy.permits_independent_approval(snapshot, preparer, "comp_test")
        assert policy.permits_independent_approval(snapshot, manager, "comp_test")
        request = SimpleNamespace(policy_snapshot=snapshot)
        assert ApprovalEngine._independent_policy(doc, request) == snapshot
        request.policy_snapshot = {"requires_independent": False}
        assert ApprovalEngine._independent_policy(doc, request) is None
        doc.created_by = None
        with pytest.raises(ValueError, match="missing_preparer"):
            policy.build_policy(doc, requester.id, "purchase_order")
        doc.created_by = "unknown"
        with pytest.raises(ValueError, match="unclassified_preparer"):
            policy.build_policy(doc, requester.id, "purchase_order")


def test_engine_enforces_frozen_policy_and_admin_limit(app, monkeypatch):
    """Configuration cannot weaken a pending request and approvals execute once."""
    from cacao_accounting.database import PurchaseOrder

    with app.app_context():
        _enable_engine()
        cfg = CacaoConfig(key="approval_require_different_approver_comp_test", value="1")
        database.session.add(cfg)
        creator = _create_user("creator", "admin")
        approver = _create_user("approver", "admin")
        creator.active = approver.active = True
        _create_rule("comp_test", "purchase_order", user_id=creator.id, max_amount=100)
        _create_rule("comp_test", "purchase_order", user_id=approver.id, max_amount=10)
        doc = PurchaseOrder(company="comp_test", created_by=creator.id, grand_total=100, docstatus=0)
        database.session.add(doc)
        database.session.flush()
        with pytest.raises(ValueError, match="usuario activo identificado"):
            ApprovalEngine.request_approval(doc)
        with pytest.raises(ValueError, match="usuario activo identificado"):
            ApprovalEngine.request_cancellation(doc)
        creator.active = False
        with pytest.raises(ValueError, match="usuario activo identificado"):
            ApprovalEngine.request_approval(doc, actor=creator)
        creator.active = True
        request = ApprovalEngine.request_approval(doc, actor=creator)
        assert request and request.policy_snapshot["requires_independent"]
        cfg.value = "0"
        assert not ApprovalEngine.can_approve(doc, creator)
        assert ApprovalEngine.can_approve(doc, approver)
        with pytest.raises(ValueError, match="independencia"):
            ApprovalEngine.approve(doc, creator)
        with pytest.raises(ValueError, match="aprobación autorizada"):
            assert_execution_authorized(doc, approver.id)
        database.session.query(CacaoConfig).filter_by(key="approval_engine_enabled_comp_test").first().value = "0"
        assert not ApprovalEngine.can_approve(doc, creator)
        calls = []

        def execute(doctype, document, user):
            assert_execution_authorized(document, user.id)
            calls.append(doctype)

        monkeypatch.setattr(ApprovalEngine, "_execute_submit", execute)
        assert ApprovalEngine.approve(doc, approver)
        assert ApprovalEngine.approve(doc, approver)
        assert calls == ["purchase_order"]
        assert request.status == "Approved"


def test_direct_execution_requires_authority_and_scoped_generated_child(app):
    """Direct calls require real authority; derived authorization is bound to its parent."""
    from cacao_accounting.approval_engine import approved_child_execution, approved_execution, execution_actor

    with app.app_context():
        module = Modules(module="sales", default=True, enabled=True)
        database.session.add(module)
        database.session.flush()
        user = _actor("poster", module, 3)
        parent = SimpleNamespace(id="parent", company="comp_test", document_type="sales_invoice")
        child = SimpleNamespace(id="child", company="comp_test", document_type="delivery_note")
        assert_execution_authorized(parent, user.id)
        with pytest.raises(ValueError, match="usuario autorizados"):
            assert_execution_authorized(parent)
        with approved_child_execution(parent, child, "delivery_note"):
            assert execution_actor(child.id) is None
        with approved_execution(parent, user.id):
            assert execution_actor(parent.id) == user.id
            with approved_child_execution(parent, child, "delivery_note"):
                assert execution_actor(child.id) == user.id
                assert_execution_authorized(child, user.id)
            child.company = "other"
            with pytest.raises(ValueError, match="documento generado"):
                with approved_child_execution(parent, child, "delivery_note"):
                    pass
            child.company = "comp_test"
            with pytest.raises(ValueError, match="documento generado"):
                with approved_child_execution(parent, child, "purchase_order"):
                    pass
        assert execution_actor(parent.id) is None
        database.session.get(type(user), user.id).active = False
        with pytest.raises(ValueError, match="usuario autorizados"):
            assert_execution_authorized(parent, user.id)
