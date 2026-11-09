# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contratos de interfaz R2R para plantillas y filtros de reportes.

Escenario de negocio:
- #1921: la plantilla recurrente no ofrecía ningún control de envío.
- #1936: el smart select de período dependía de #report-company inexistente.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database


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
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_plantilla_recurrente_tiene_control_de_envio():
    """#1921: la vista ofrece un botón submit para guardar la plantilla."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/accounting/journal/recurring/new")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'type="submit"' in html
        assert "Guardar plantilla" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_reporte_operativo_expone_company_para_el_selector():
    """#1936: el filtro de compañía tiene el ID que consume el smart select."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/reports/sales-by-customer?company=cacao")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'id="report-company"' in html
        assert 'value="cacao"' in html
        assert "accounting_period_from" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
