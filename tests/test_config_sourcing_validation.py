# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Banderas booleanas y validación de abastecimiento.

Escenario de negocio:
- #1924: strings como «false» activaban modo test y el tracking de SQLAlchemy.
- #1996: minimum_offers no numérico exponía el error crudo de int().
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_sourcing_service import get_purchase_sourcing_config
from cacao_accounting.config import configuracion, env_bool
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


def test_env_bool_no_usa_truthiness(monkeypatch):
    """#1924: false/0 no activan la bandera; true/1/on sí."""
    for raw in ("false", "0", "no", "off", ""):
        monkeypatch.setenv("CACAO_FLAG_TEST", raw)
        assert env_bool("CACAO_FLAG_TEST") is False
    for raw in ("true", "1", "yes", "on"):
        monkeypatch.setenv("CACAO_FLAG_TEST", raw)
        assert env_bool("CACAO_FLAG_TEST") is True
    monkeypatch.delenv("CACAO_FLAG_TEST", raising=False)
    assert env_bool("CACAO_FLAG_TEST", True) is True


def test_configuracion_usa_booleanos_reales():
    """#1924: Flask-SQLAlchemy recibe False, no el string 'False'."""
    assert configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] is False
    assert isinstance(configuracion["EXTERNAL_DOCUMENT_VALIDATION_ENABLED"], bool)


def test_minimo_de_ofertas_invalido_no_expone_int():
    """#1996: el error se traduce y no muta la configuración."""
    application = _crear_app()
    try:
        client = _cliente(application)
        with application.app_context():
            antes = get_purchase_sourcing_config()
        respuesta = client.post(
            "/settings/purchase-sourcing",
            data={"minimum_offers": "not-a-number"},
            follow_redirects=True,
        )

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "El mínimo de ofertas debe ser un número entero." in html
        assert "invalid literal for int()" not in html
        with application.app_context():
            assert get_purchase_sourcing_config() == antes
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
