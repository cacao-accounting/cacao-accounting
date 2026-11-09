# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El botón de eliminar reglas de aprobación tiene nombre accesible.

Escenario de negocio (issue #2004): el botón contenía solo un icono; las
tecnologías de asistencia no recibían nombre ni descripción para la acción.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalMatrix,
    Entity,
    Modules,
    Roles,
    User,
    database,
)


def _crear_app():
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
        database.session.add(
            ApprovalMatrix(
                company_id="cacao",
                document_type="sales_invoice",
                role_id=rol.id,
                min_amount=Decimal("0"),
                approval_level=1,
                enabled=True,
            )
        )
        database.session.commit()
    return application


def test_el_boton_de_borrado_tiene_nombre_accesible():
    """Se sirven aria-label y title traducibles."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/settings/approval-matrix?company=cacao")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'aria-label="Deshabilitar regla de aprobación"' in html
        assert 'title="Deshabilitar regla de aprobación"' in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
