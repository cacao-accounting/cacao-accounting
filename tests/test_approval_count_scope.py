# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance por compañía de la insignia de aprobaciones pendientes.

Escenario de negocio: un aprobador autorizado solo en ``alpha`` no debe ver en
la navegación el volumen agregado de solicitudes pendientes de ``beta``. La
insignia debe contar únicamente las solicitudes de las compañías vigentes del
usuario, igual que el listado de ``/admin/me/pending-approvals``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalRequest,
    ApprovalMatrix,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "aprobaciones-scope-2026"


@pytest.fixture
def aprobaciones_cloud():
    """Cloud de dos compañías con solicitudes pendientes en ambas."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="aprobador",
                    user="aprobador",
                    name="Aprobador Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="sinacceso",
                    user="sinacceso",
                    name="Sin Compañías",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="sales-only",
                    user="sales-only",
                    name="Aprobador solo de ventas",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="aprobador", company_code="alpha"),
                UserCompanyAccess(user_id="sales-only", company_code="beta"),
                UserCompanyAccess(user_id="admin", company_code="alpha"),
                User(
                    id="admin-sin",
                    user="admin-sin",
                    name="Administrador sin compañías",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        sales_module_id = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        admin_module_id = database.session.execute(database.select(Modules.id).filter_by(module="admin")).scalar_one()
        approver_role = Roles(name="sales-approver-count-scope", note="Aprobador de ventas")
        database.session.add(approver_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=approver_role.id,
                    module_id=sales_module_id,
                    access=True,
                    view=True,
                    approve=True,
                    setup=True,
                    approval_rank=1,
                ),
                RolesAccess(
                    rol_id=approver_role.id,
                    module_id=admin_module_id,
                    access=True,
                    view=True,
                    edit=True,
                    approve=True,
                    approval_rank=1,
                ),
                RolesUser(user_id="aprobador", role_id=approver_role.id, active=True),
                RolesUser(user_id="sales-only", role_id=approver_role.id, active=True),
            ]
        )
        visible_invoice = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 10, 31),
            document_type="sales_invoice",
            document_no="INV-ALPHA-VISIBLE",
            grand_total=Decimal("50"),
        )
        out_of_range_invoice = SalesInvoice(
            company="alpha",
            posting_date=date(2026, 10, 31),
            document_type="sales_invoice",
            document_no="INV-ALPHA-OUT-OF-RANGE",
            grand_total=Decimal("150"),
        )
        foreign_invoice = SalesInvoice(
            company="beta",
            posting_date=date(2026, 10, 31),
            document_type="sales_invoice",
            document_no="INV-BETA",
            grand_total=Decimal("50"),
        )
        database.session.add_all([visible_invoice, out_of_range_invoice, foreign_invoice])
        database.session.flush()
        database.session.add(
            ApprovalMatrix(
                company_id="alpha",
                document_type="sales_invoice",
                user_id="aprobador",
                min_amount=Decimal("0"),
                max_amount=Decimal("100"),
                approval_level=1,
                enabled=True,
            )
        )
        database.session.add(
            ApprovalMatrix(
                company_id="beta",
                document_type="sales_invoice",
                user_id="sales-only",
                min_amount=Decimal("0"),
                max_amount=Decimal("100"),
                approval_level=1,
                enabled=True,
            )
        )
        database.session.add_all(
            [
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id=visible_invoice.id,
                    company_id="alpha",
                    requested_by="aprobador",
                    status="Pending Approval",
                    cancellation_date=date(2026, 10, 31),
                ),
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id=foreign_invoice.id,
                    company_id="beta",
                    requested_by="aprobador",
                    status="Pending Approval",
                    cancellation_date=date(2026, 10, 31),
                ),
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id=out_of_range_invoice.id,
                    company_id="alpha",
                    requested_by="aprobador",
                    status="Pending Approval",
                    cancellation_date=date(2026, 10, 31),
                ),
                ApprovalRequest(
                    document_type="config_change",
                    document_id="config-sales-alpha",
                    company_id="alpha",
                    requested_by="aprobador",
                    status="Pending Approval",
                    policy_snapshot={
                        "requires_independent": True,
                        "module": "admin",
                        "preparers": [{"user_id": "otro", "rank": 1}],
                    },
                    review_payload={"model": "sales"},
                ),
                ApprovalRequest(
                    document_type="config_change",
                    document_id="config-purchases-alpha",
                    company_id="alpha",
                    requested_by="aprobador",
                    status="Pending Approval",
                    policy_snapshot={
                        "requires_independent": True,
                        "module": "purchases",
                        "preparers": [{"user_id": "otro", "rank": 1}],
                    },
                    review_payload={"model": "purchases"},
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("aprobador", "accounting_user")
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _contar(application, usuario: str):
    from flask_login import login_user

    from cacao_accounting import pending_approval_count
    from cacao_accounting.database import User, database

    with application.test_request_context("/app"):
        user = database.session.execute(database.select(User).filter_by(user=usuario)).scalar_one()
        login_user(user)
        return pending_approval_count()


def _authenticated_client(application, user_id: str):
    """Authenticate a client against the isolated Cloud fixture."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_aprobador_solo_cuenta_su_compania(aprobaciones_cloud):
    """Badge and inbox include only reviews allowed by company and domain policy."""
    assert _contar(aprobaciones_cloud, "aprobador") == 2
    client = _authenticated_client(aprobaciones_cloud, "aprobador")
    response = client.get("/me/pending-approvals")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "INV-ALPHA-VISIBLE" in body
    assert "INV-ALPHA-OUT-OF-RANGE" not in body
    assert "INV-BETA" not in body
    assert "sales:alpha" in body
    assert "purchases:alpha" not in body


def test_usuario_sin_companias_no_ve_solicitudes(aprobaciones_cloud):
    """Sin compañías autorizadas la insignia queda en cero."""
    assert _contar(aprobaciones_cloud, "sinacceso") == 0


def test_sales_only_reviewer_keeps_other_module_company_scope(aprobaciones_cloud):
    """Company candidates do not depend on the accounting module permission."""
    assert _contar(aprobaciones_cloud, "sales-only") == 1


def test_administrador_cloud_se_limita_a_sus_concesiones(aprobaciones_cloud):
    """#2059: en Cloud el administrador solo ve las compañías concedidas."""
    # Alpha tiene cuatro solicitudes; beta queda fuera pese a la clasificación admin.
    assert _contar(aprobaciones_cloud, "admin") == 4
    client = _authenticated_client(aprobaciones_cloud, "admin")
    body = client.get("/me/pending-approvals").get_data(as_text=True)
    assert "INV-ALPHA-VISIBLE" in body
    assert "INV-BETA" not in body


def test_administrador_cloud_sin_concesiones_no_ve_solicitudes(aprobaciones_cloud):
    """#2059: la clasificación admin no concede compañías por sí sola en Cloud."""
    assert _contar(aprobaciones_cloud, "admin-sin") == 0
