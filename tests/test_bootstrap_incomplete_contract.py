# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Moreno Reyes

"""#1848: una base con seed parcial no se reporta como inicializada."""

from __future__ import annotations

from click.testing import CliRunner

from cacao_accounting import cli, create_app
from cacao_accounting import __main__ as entrypoint
from cacao_accounting.database import Currency, User, database
from cacao_accounting.database import helpers
from cacao_accounting.database.helpers import (
    datos_base_completos,
    estado_esquema_base_datos,
    inicia_base_de_datos,
)
from cacao_accounting.setup.catalogs import SETUP_SEED_CURRENCY_CODES


def _app(tmp_path, name="bootstrap.sqlite"):
    """Crea una aplicación real con una base SQLite aislada."""
    return create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / name}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )


def _sembrar_bootstrap_parcial(tmp_path, name="parcial.sqlite"):
    """Simula el fallo reportado: administrador confirmado y monedas incompletas."""
    app = _app(tmp_path, name)
    moneda = SETUP_SEED_CURRENCY_CODES[0]
    with app.app_context():
        database.create_all()
        database.session.add(User(user="admin", password=b"x", active=True, classification="admin"))
        database.session.add(Currency(code=moneda, name="Moneda parcial", decimals=2, active=True))
        database.session.commit()
    return app, moneda


def test_base_parcial_se_detecta_como_bootstrap_incompleto(tmp_path):
    """La existencia de User no declara completa una base con seed parcial (#1848)."""
    app, _ = _sembrar_bootstrap_parcial(tmp_path)
    with app.app_context():
        assert datos_base_completos() is False
        estado = estado_esquema_base_datos()
        assert estado["status"] == "bootstrap_incomplete"
        assert estado["users"] is True


def test_inicia_base_de_datos_no_muta_una_base_parcial(tmp_path):
    """Una base parcial no se completa silenciosamente y falla de forma cerrada (#1848)."""
    app, moneda = _sembrar_bootstrap_parcial(tmp_path, "parcial_helper.sqlite")
    assert inicia_base_de_datos(app, user="admin", passwd="AdminPass!123", with_examples=False) is False
    with app.app_context():
        codigos = set(database.session.execute(database.select(Currency.code)).scalars())
        assert codigos == {moneda}
        assert database.session.execute(database.select(database.func.count()).select_from(User)).scalar() == 1


def test_db_init_rechaza_base_parcial_sin_agregar_monedas(tmp_path, monkeypatch):
    """`db init` no declara éxito ni completa el catálogo de una base parcial (#1848)."""
    app, moneda = _sembrar_bootstrap_parcial(tmp_path, "parcial_cli.sqlite")
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)
    result = CliRunner().invoke(cli.db_init)
    assert result.exit_code != 0
    salida = result.output.lower()
    assert "parcial" in salida or "incompatible" in salida
    with app.app_context():
        assert set(database.session.execute(database.select(Currency.code)).scalars()) == {moneda}


def test_entrypoint_no_arranca_con_bootstrap_parcial(tmp_path, monkeypatch):
    """El entrypoint no inicia el servidor si el bootstrap no se completó (#1848)."""
    app, _ = _sembrar_bootstrap_parcial(tmp_path, "parcial_entrypoint.sqlite")
    monkeypatch.setenv("CACAO_USER", "admin")
    monkeypatch.setenv("CACAO_PSWD", "AdminPass!123")
    monkeypatch.setattr(helpers, "inicia_base_de_datos", lambda **kwargs: False)
    assert entrypoint.inicializar_si_hace_falta(app, esperar_segundos=0) is False


def test_bootstrap_completo_sigue_valido_y_sin_duplicados(tmp_path):
    """Un bootstrap completo mantiene la verificación idempotente (#1848)."""
    app = _app(tmp_path, "completa.sqlite")
    assert inicia_base_de_datos(app, user="admin", passwd="AdminPass!123", with_examples=False) is True
    with app.app_context():
        assert datos_base_completos() is True
        usuarios = database.session.execute(database.select(database.func.count()).select_from(User)).scalar()
        monedas = database.session.execute(database.select(database.func.count()).select_from(Currency)).scalar()
    assert inicia_base_de_datos(app, user="admin", passwd="AdminPass!123", with_examples=False) is True
    with app.app_context():
        assert database.session.execute(database.select(database.func.count()).select_from(User)).scalar() == usuarios
        assert database.session.execute(database.select(database.func.count()).select_from(Currency)).scalar() == monedas
