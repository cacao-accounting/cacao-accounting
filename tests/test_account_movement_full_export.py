# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La exportación PDF del movimiento contable usa todas las filas.

Escenario de negocio (issue #1937): CSV/XLSX reconsultaban con
``export_all=True``, pero PDF se generaba con la página de 100 filas.
"""

from __future__ import annotations

import importlib

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


def test_pdf_reconsulta_el_reporte_completo(monkeypatch):
    """#1937: PDF sigue el mismo camino export_all que CSV/XLSX."""
    routes_module = importlib.import_module("cacao_accounting.reportes.routes")
    application = _crear_app()
    try:
        llamadas = []

        def _fake_report(filters):
            llamadas.append(filters)
            return object()

        monkeypatch.setattr(routes_module, "get_account_movement_detail", _fake_report)
        monkeypatch.setattr(routes_module, "_render_financial_report", lambda *args, **kwargs: "ok")

        client = _cliente(application)
        respuesta = client.get("/reports/account-movement?company=cacao&export=pdf&apply_filters=1")

        assert respuesta.status_code == 200
        assert len(llamadas) == 2
        assert llamadas[0].export_all is False
        assert llamadas[1].export_all is True
        assert llamadas[1].page == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
