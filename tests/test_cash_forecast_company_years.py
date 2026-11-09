# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El alta de pronóstico refresca los años fiscales al cambiar compañía.

Escenario de negocio (issue #2016): el selector de compañía no recargaba el
formulario; al elegir otra compañía se conservaban los años fiscales
anteriores y el POST era rechazado.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, FiscalYear, Modules, User, database


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
                Modules(module="cash", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="other",
                    name="Other",
                    company_name="Other SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                FiscalYear(
                    entity="cacao",
                    name="FY-CACAO",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
                FiscalYear(
                    entity="other",
                    name="FY-OTHER",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
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


def test_cambiar_compania_muestra_sus_anos_fiscales():
    """El GET ?company=other solo lista los años de esa compañía."""
    application = _crear_app()
    try:
        client = _cliente(application)
        cacao = client.get("/cash_management/cash-forecast/new?company=cacao").get_data(as_text=True)
        other = client.get("/cash_management/cash-forecast/new?company=other").get_data(as_text=True)

        assert "FY-CACAO" in cacao
        assert "FY-OTHER" not in cacao
        assert "FY-OTHER" in other
        assert "FY-CACAO" not in other
        assert "this.form.submit()" in other
        assert 'value="company"' in other or 'name="company"' in other
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
