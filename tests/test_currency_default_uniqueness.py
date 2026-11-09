# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El catálogo mantiene una única moneda predeterminada.

Escenario de negocio (issue #1766): el alta insertaba ``default=True`` sin
retirar la marca de la moneda anterior, mientras el editor y el setup sí
normalizaban el indicador.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Modules, User, database


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


def _defaults() -> set[str]:
    return {
        currency.code
        for currency in database.session.execute(database.select(Currency).where(Currency.default.is_(True))).scalars()
    }


def test_crear_predeterminada_retira_la_anterior():
    """#1766: al marcar la nueva moneda, la anterior deja de ser default."""
    application = _crear_app()
    try:
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
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_crear_sin_predeterminada_conserva_la_actual():
    """#1766: una moneda normal no altera la predeterminada existente."""
    application = _crear_app()
    try:
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
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_no_crea_predeterminada_inactiva():
    """#1766: la moneda predeterminada debe permanecer activa."""
    application = _crear_app()
    try:
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
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_editor_tambien_normaliza():
    """#1766: el contrato de edición se mantiene tras el refactor."""
    codigo = "ZZZ"
    application = _crear_app()
    try:
        with application.app_context():
            database.session.add(Currency(code=codigo, name="Moneda Z", decimals=2, active=True, default=False))
            database.session.commit()

        client = _cliente(application)
        respuesta = client.post(
            f"/accounting/currency/{codigo}/edit",
            data={"code": codigo, "name": "Moneda Z", "decimals": "2", "active": "y", "default": "y"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            assert _defaults() == {codigo}
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
