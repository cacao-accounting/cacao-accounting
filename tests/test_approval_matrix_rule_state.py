# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La matriz distingue reglas activas e inactivas.

Escenario de negocio (issue #2002): las filas con ``enabled=False`` se
mostraban como activas y el botón las «eliminaba» de nuevo; no había forma de
distinguirlas ni reactivarlas desde la pantalla.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalMatrix,
    Currency,
    Entity,
    Modules,
    Roles,
    User,
    database,
)


def _crear_app(enabled: bool):
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
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
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Roles(name="approver", note="Aprobador"),
            ]
        )
        database.session.flush()
        rol = database.session.execute(database.select(Roles).filter_by(name="approver")).scalar_one()
        regla = ApprovalMatrix(
            company_id="cacao",
            document_type="sales_invoice",
            role_id=rol.id,
            min_amount=Decimal("0"),
            approval_level=1,
            enabled=enabled,
        )
        database.session.add(regla)
        database.session.commit()
        rule_id = regla.id
    return application, rule_id


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_la_regla_inactiva_se_muestra_y_se_reactiva():
    """La fila inactiva tiene badge/acción propios y toggle_rule la activa."""
    application, rule_id = _crear_app(enabled=False)
    try:
        client = _cliente(application)
        html = client.get("/settings/approval-matrix?company=cacao").get_data(as_text=True)

        assert "Inactiva" in html
        assert "Habilitar regla de aprobación" in html

        respuesta = client.post(
            "/settings/approval-matrix",
            data={"action": "toggle_rule", "company": "cacao", "rule_id": rule_id},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            regla = database.session.get(ApprovalMatrix, rule_id)
            assert regla is not None and regla.enabled is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_regla_activa_ofrece_deshabilitar():
    """El estado activo muestra su badge y la acción contraria."""
    application, rule_id = _crear_app(enabled=True)
    try:
        client = _cliente(application)
        html = client.get("/settings/approval-matrix?company=cacao").get_data(as_text=True)

        assert "Activa" in html
        assert "Deshabilitar regla de aprobación" in html

        respuesta = client.post(
            "/settings/approval-matrix",
            data={"action": "toggle_rule", "company": "cacao", "rule_id": rule_id},
        )
        assert respuesta.status_code == 302
        with application.app_context():
            regla = database.session.get(ApprovalMatrix, rule_id)
            assert regla is not None and regla.enabled is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
