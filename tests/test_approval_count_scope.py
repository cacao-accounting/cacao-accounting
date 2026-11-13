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

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalRequest,
    Currency,
    Entity,
    Modules,
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="aprobador", company_code="alpha"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id="INV-ALPHA",
                    company_id="alpha",
                    requested_by="aprobador",
                    status="Pending Approval",
                    cancellation_date=date(2026, 10, 31),
                ),
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id="INV-BETA",
                    company_id="beta",
                    requested_by="aprobador",
                    status="Pending Approval",
                    cancellation_date=date(2026, 10, 31),
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


def test_aprobador_solo_cuenta_su_compania(aprobaciones_cloud):
    """La insignia no suma solicitudes de compañías fuera del alcance."""
    assert _contar(aprobaciones_cloud, "aprobador") == 1


def test_usuario_sin_companias_no_ve_solicitudes(aprobaciones_cloud):
    """Sin compañías autorizadas la insignia queda en cero."""
    assert _contar(aprobaciones_cloud, "sinacceso") == 0


def test_administrador_global_conserva_el_total(aprobaciones_cloud):
    """Control positivo: el administrador sigue viendo ambas compañías."""
    assert _contar(aprobaciones_cloud, "admin") == 2
