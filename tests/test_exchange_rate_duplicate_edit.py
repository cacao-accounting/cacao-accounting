# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La edición de tasas de cambio no colisiona con otra fila.

Escenario de negocio (issue #1763): el modelo impone unicidad por
(origen, destino, fecha), pero la ruta asignaba y confirmaba sin comprobar el
conflicto; IntegrityError terminaba en HTTP 500.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.contabilidad import routes as accounting_routes
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, ExchangeRate, Modules, User, database


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
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
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
        database.session.flush()
        primera = ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 1, 10))
        segunda = ExchangeRate(origin="USD", destination="NIO", rate=Decimal("37"), date=date(2026, 1, 11))
        database.session.add_all([primera, segunda])
        database.session.commit()
        ids = {"primera": primera.id, "segunda": segunda.id}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _simular_conflicto_confirmado_despues_del_precheck(monkeypatch):
    """Model a concurrent winner while leaving the database constraint real."""
    original = accounting_routes._exchange_rate_conflicts
    precheck_was_stale = False

    def check_after_concurrent_write(*args, **kwargs):
        nonlocal precheck_was_stale
        if not precheck_was_stale:
            precheck_was_stale = True
            return False
        return original(*args, **kwargs)

    monkeypatch.setattr(accounting_routes, "_exchange_rate_conflicts", check_after_concurrent_write)


def test_edicion_duplicada_responde_formulario_y_conserva_filas():
    """#1763: el par y fecha de otra tasa se rechaza sin HTTP 500."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            f"/accounting/exchange/{ids['primera']}/edit",
            data={"origin": "USD", "destination": "NIO", "rate": "38", "date": "2026-01-11"},
        )

        assert respuesta.status_code == 200
        assert "Ya existe una tasa de cambio para ese par de monedas y fecha." in respuesta.get_data(as_text=True)
        with application.app_context():
            primera = database.session.get(ExchangeRate, ids["primera"])
            segunda = database.session.get(ExchangeRate, ids["segunda"])
            assert primera is not None and primera.date == date(2026, 1, 10)
            assert primera.rate == Decimal("36.000000000")
            assert segunda is not None and segunda.rate == Decimal("37.000000000")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_sin_colision_se_guarda():
    """#1763: cambiar a un par/fecha libre sigue funcionando."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            f"/accounting/exchange/{ids['primera']}/edit",
            data={"origin": "USD", "destination": "NIO", "rate": "38", "date": "2026-01-12"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            primera = database.session.get(ExchangeRate, ids["primera"])
            assert primera is not None
            assert primera.date == date(2026, 1, 12)
            assert primera.rate == Decimal("38.000000000")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_maneja_conflicto_ganado_tras_precheck(monkeypatch):
    """A stale precheck is resolved by the database constraint and returns the form."""
    application, ids = _crear_app()
    try:
        _simular_conflicto_confirmado_despues_del_precheck(monkeypatch)
        respuesta = _cliente(application).post(
            f"/accounting/exchange/{ids['primera']}/edit",
            data={"origin": "USD", "destination": "NIO", "rate": "38", "date": "2026-01-11"},
        )

        assert respuesta.status_code == 200
        assert "Ya existe una tasa de cambio para ese par de monedas y fecha." in respuesta.get_data(as_text=True)
        with application.app_context():
            primera = database.session.get(ExchangeRate, ids["primera"])
            segunda = database.session.get(ExchangeRate, ids["segunda"])
            assert primera is not None and primera.date == date(2026, 1, 10)
            assert primera.rate == Decimal("36.000000000")
            assert segunda is not None and segunda.rate == Decimal("37.000000000")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_alta_duplicada_responde_formulario_y_conserva_filas():
    """El alta rechaza un par/fecha ocupado sin producir HTTP 500 ni reemplazar la tasa."""
    application, _ids = _crear_app()
    try:
        respuesta = _cliente(application).post(
            "/accounting/exchange/new",
            data={"origin": "USD", "destination": "NIO", "rate": "38", "date": "2026-01-10"},
        )

        assert respuesta.status_code == 200
        assert "Ya existe una tasa de cambio para ese par de monedas y fecha." in respuesta.get_data(as_text=True)
        with application.app_context():
            tasas = database.session.execute(database.select(ExchangeRate).order_by(ExchangeRate.date)).scalars().all()
            assert [(rate.date, rate.rate) for rate in tasas] == [
                (date(2026, 1, 10), Decimal("36.000000000")),
                (date(2026, 1, 11), Decimal("37.000000000")),
            ]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_alta_maneja_conflicto_ganado_tras_precheck(monkeypatch):
    """A concurrent duplicate commit is reported without changing either rate."""
    application, _ids = _crear_app()
    try:
        _simular_conflicto_confirmado_despues_del_precheck(monkeypatch)
        respuesta = _cliente(application).post(
            "/accounting/exchange/new",
            data={"origin": "USD", "destination": "NIO", "rate": "38", "date": "2026-01-10"},
        )

        assert respuesta.status_code == 200
        assert "Ya existe una tasa de cambio para ese par de monedas y fecha." in respuesta.get_data(as_text=True)
        with application.app_context():
            tasas = database.session.execute(database.select(ExchangeRate).order_by(ExchangeRate.date)).scalars().all()
            assert [(rate.date, rate.rate) for rate in tasas] == [
                (date(2026, 1, 10), Decimal("36.000000000")),
                (date(2026, 1, 11), Decimal("37.000000000")),
            ]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_alta_sin_colision_se_guarda():
    """El control positivo conserva el alta de tasas para un día libre."""
    application, _ids = _crear_app()
    try:
        respuesta = _cliente(application).post(
            "/accounting/exchange/new",
            data={"origin": "USD", "destination": "NIO", "rate": "38", "date": "2026-01-12"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            tasa = database.session.execute(
                database.select(ExchangeRate).filter_by(origin="USD", destination="NIO", date=date(2026, 1, 12))
            ).scalar_one()
            assert tasa.rate == Decimal("38.000000000")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
