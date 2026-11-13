# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La comparación de pronósticos muestra la moneda funcional.

Escenario de negocio (issue #2015): la matriz calcula en la moneda de la
compañía, pero la plantilla llamaba ``format_money_with_currency(value)`` sin
código; los saldos aparecían sin unidad monetaria.
"""

from __future__ import annotations

import importlib
from decimal import Decimal
from types import SimpleNamespace

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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
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


def _fila() -> dict:
    return {
        "period": "Enero",
        "zone": "Real",
        "base_projected": Decimal("800"),
        "compare_projected": Decimal("900"),
        "variance": Decimal("100"),
        "variance_manual_inflow": Decimal("0"),
        "variance_manual_outflow": Decimal("0"),
    }


def test_la_comparacion_incluye_la_moneda_de_la_compania(monkeypatch):
    """Saldo y varianza se imprimen con el código NIO."""
    application = _crear_app()
    try:
        modulo = importlib.import_module("cacao_accounting.bancos.cash_forecast")
        monkeypatch.setattr(
            modulo,
            "_cash_forecast_comparison",
            lambda company, base_id, compare_id: (
                SimpleNamespace(version="Base", status="Draft"),
                SimpleNamespace(version="Comparada", status="Approved"),
                [_fila()],
            ),
        )
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/cash_management/cash-forecast/compare?company=cacao&base_id=b&compare_id=c")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "NIO 800.00" in html
        assert "NIO 900.00" in html
        assert "NIO 100.00" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
