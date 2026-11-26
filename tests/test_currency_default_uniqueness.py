# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión HTTP de la moneda predeterminada (#1766).

El catálogo debe mantener una única moneda predeterminada, activa y coherente
tanto al crear monedas como al editarlas o desactivarlas.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Modules, User, database


@pytest.fixture
def application() -> Iterator[Flask]:
    """Crea un catálogo aislado con una moneda predeterminada inicial."""
    app = create_app(
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
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
    try:
        yield app
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def _cliente(application: Flask) -> FlaskClient:
    """Autentica un administrador sin pasar por el formulario de acceso."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _defaults() -> set[str]:
    """Devuelve los códigos actualmente marcados como predeterminados."""
    return {
        currency.code
        for currency in database.session.execute(database.select(Currency).where(Currency.default.is_(True))).scalars()
    }


def test_crear_predeterminada_retira_la_anterior(application):
    """Al marcar la nueva moneda, la anterior deja de ser predeterminada."""
    client = _cliente(application)
    respuesta = client.post(
        "/accounting/currency/new",
        data={"code": "ZZZ", "name": "Moneda Z", "decimals": "2", "active": "y", "default": "y"},
    )

    assert respuesta.status_code == 302
    with application.app_context():
        assert _defaults() == {"ZZZ"}
        nueva = database.session.execute(database.select(Currency).filter_by(code="ZZZ")).scalar_one()
        assert nueva.active is True
        assert nueva.default is True


def test_crear_sin_predeterminada_conserva_la_actual(application):
    """Una moneda normal no altera la predeterminada existente."""
    client = _cliente(application)
    respuesta = client.post(
        "/accounting/currency/new",
        data={"code": "ZZZ", "name": "Moneda Z", "decimals": "2", "active": "y"},
    )

    assert respuesta.status_code == 302
    with application.app_context():
        assert _defaults() == {"NIO"}
        nueva = database.session.execute(database.select(Currency).filter_by(code="ZZZ")).scalar_one()
        assert nueva.active is True
        assert nueva.default is False


def test_no_crea_predeterminada_inactiva(application):
    """Una moneda predeterminada debe permanecer activa desde su alta."""
    client = _cliente(application)
    respuesta = client.post(
        "/accounting/currency/new",
        data={"code": "ZZZ", "name": "Moneda Z", "decimals": "2", "default": "y"},
    )

    assert respuesta.status_code == 200
    assert "La moneda predeterminada del sistema debe permanecer activa." in respuesta.get_data(as_text=True)
    with application.app_context():
        assert database.session.execute(database.select(Currency).filter_by(code="ZZZ")).scalar_one_or_none() is None
        assert _defaults() == {"NIO"}


def test_el_editor_tambien_normaliza(application):
    """Editar una moneda normal como predeterminada retira la marca anterior."""
    with application.app_context():
        database.session.add(Currency(code="ZZZ", name="Moneda Z", decimals=2, active=True, default=False))
        database.session.commit()

    client = _cliente(application)
    respuesta = client.post(
        "/accounting/currency/ZZZ/edit",
        data={"code": "ZZZ", "name": "Moneda Z", "decimals": "2", "active": "y", "default": "y"},
    )

    assert respuesta.status_code == 302
    with application.app_context():
        assert _defaults() == {"ZZZ"}


def test_no_desactiva_la_moneda_predeterminada(application):
    """La acción HTTP de desactivar protege la moneda predeterminada."""
    client = _cliente(application)
    respuesta = client.post("/accounting/currency/NIO/toggle-active", follow_redirects=True)

    assert respuesta.status_code == 200
    assert "No se puede deshabilitar la moneda predeterminada del sistema." in respuesta.get_data(as_text=True)
    with application.app_context():
        moneda = database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one()
        assert moneda.active is True
        assert moneda.default is True
        assert _defaults() == {"NIO"}
