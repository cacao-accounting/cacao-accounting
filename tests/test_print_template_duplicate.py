# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Duplicar plantillas de impresión genera códigos únicos.

Escenario de negocio (issue #1929): la segunda duplicación reutilizaba
``<code>_copy`` y chocaba con la restricción única.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Roles, RolesUser, User, database
from cacao_accounting.printing.models import PrintTemplate


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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
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
                Roles(name="admin", note="Administrador"),
            ]
        )
        database.session.flush()
        role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
        database.session.add(RolesUser(user_id="admin", role_id=role.id, active=True))
        source = PrintTemplate(
            company_code="cacao",
            document_type="sales_invoice",
            code="BASE",
            name="Plantilla base",
            template_body="<html><body>ok</body></html>",
            status="published",
        )
        database.session.add(source)
        database.session.commit()
        template_id = source.id
    return application, template_id


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_duplicar_dos_veces_no_responde_500():
    """#1929: la segunda copia usa un código único y responde redirect."""
    application, template_id = _crear_app()
    try:
        client = _cliente(application)
        primera = client.post(f"/admin/print-templates/{template_id}/duplicate")
        segunda = client.post(f"/admin/print-templates/{template_id}/duplicate")

        assert primera.status_code == 302
        assert segunda.status_code == 302
        with application.app_context():
            codigos = {
                template.code
                for template in database.session.execute(
                    database.select(PrintTemplate).filter_by(company_code="cacao", document_type="sales_invoice")
                )
                .scalars()
                .all()
            }
            assert {"BASE", "BASE_copy", "BASE_copy_2"} <= codigos
            assert len(codigos) == 3
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
