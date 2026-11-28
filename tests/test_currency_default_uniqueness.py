# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión HTTP de la moneda predeterminada (#1766).

El catálogo debe mantener una única moneda predeterminada, activa y coherente
tanto al crear monedas como al editarlas o desactivarlas.
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

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


def _concurrent_application(tmp_path) -> Flask:
    """Crea una aplicación SQLite aislada para dos escrituras simultáneas."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'currency-default.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
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
    return app


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


def test_dos_altas_predeterminadas_concurrentes_dejan_una_sola(tmp_path, monkeypatch):
    """La segunda transición espera el lock global y vuelve a normalizar."""
    from cacao_accounting.contabilidad import currency_guard
    from cacao_accounting.contabilidad.currency_guard import CurrencyGuard

    app = _concurrent_application(tmp_path)
    original_lock = currency_guard.lock_default_scope
    original_clear = CurrencyGuard._clear_other_defaults
    state_lock = Lock()
    lock_calls = 0
    clear_calls = 0
    first_clearing = Event()
    second_lock_attempted = Event()
    second_clearing = Event()
    release_first = Event()

    def observed_lock(category: str, *parts: str | None) -> None:
        nonlocal lock_calls
        with state_lock:
            lock_calls += 1
            call_number = lock_calls
        if call_number == 2:
            second_lock_attempted.set()
        original_lock(category, *parts)

    def controlled_clear(self, code: str) -> None:
        nonlocal clear_calls
        with state_lock:
            clear_calls += 1
            call_number = clear_calls
        if call_number == 1:
            first_clearing.set()
            if not release_first.wait(timeout=15):
                raise AssertionError("La primera normalización no fue liberada.")
        elif call_number == 2:
            second_clearing.set()
        original_clear(self, code)

    monkeypatch.setattr(currency_guard, "lock_default_scope", observed_lock)
    monkeypatch.setattr(CurrencyGuard, "_clear_other_defaults", controlled_clear)

    def create(code: str) -> int:
        response = _cliente(app).post(
            "/accounting/currency/new",
            data={"code": code, "name": f"Moneda {code}", "decimals": "2", "active": "y", "default": "y"},
        )
        return response.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(create, "ZZZ")
            assert first_clearing.wait(timeout=10)
            second = workers.submit(create, "YYY")
            assert second_lock_attempted.wait(timeout=10)
            assert not second_clearing.wait(timeout=0.3), "La segunda transición no esperó el lock global."
            release_first.set()
            statuses = [first.result(timeout=20), second.result(timeout=20)]
        assert statuses == [302, 302]
        assert lock_calls == 2
        assert clear_calls == 2
        with app.app_context():
            defaults = _defaults()
            assert len(defaults) == 1
            assert defaults <= {"ZZZ", "YYY"}
            selected = database.session.execute(database.select(Currency).filter_by(code=next(iter(defaults)))).scalar_one()
            assert selected.active is True
    finally:
        release_first.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
