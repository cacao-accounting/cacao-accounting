# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Credenciales iniciales seguras en los entrypoints de la aplicación."""

from __future__ import annotations

import runpy
import time
from contextlib import nullcontext
from importlib import import_module
from pathlib import Path

import pytest
from click.testing import CliRunner

import cacao_accounting

database_helpers = import_module("cacao_accounting.database.helpers")
server_module = import_module("cacao_accounting.server")
cli_module = import_module("cacao_accounting.cli")
waitress_module = import_module("waitress")


def _remove_credentials(monkeypatch):
    """Remove primary and legacy credential variables for deterministic checks."""
    for variable in ("CACAO_USER", "CACAO_PSWD", "ADMIN_USER", "CACAO_PASSWORD", "ADMIN_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)


def _raise_missing_credentials():
    """Represent a production environment without initial administrator credentials."""
    raise ValueError("CACAO_USER and CACAO_PSWD must be set in environment")


def test_resolver_rechaza_credenciales_ausentes_en_produccion(monkeypatch):
    """Production must not silently use the public setup credentials."""
    _remove_credentials(monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENV", "production")

    with pytest.raises(ValueError, match="CACAO_USER and CACAO_PSWD"):
        database_helpers.resolver_credenciales_iniciales()


def test_resolver_acepta_credenciales_explicitas_en_produccion(monkeypatch):
    """Production initialization continues when an administrator is configured."""
    _remove_credentials(monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("CACAO_USER", "operador-inicial")
    monkeypatch.setenv("CACAO_PSWD", "clave-inicial-segura")

    assert database_helpers.resolver_credenciales_iniciales() == (
        "operador-inicial",
        "clave-inicial-segura",
    )


@pytest.mark.parametrize(
    ("user_variable", "password_variable"),
    [("CACAO_USER", "CACAO_PSWD"), ("ADMIN_USER", "ADMIN_PASSWORD")],
)
def test_resolver_rechaza_credencial_predeterminada_en_produccion(monkeypatch, user_variable, password_variable):
    """The well-known administrator pair is never accepted outside development."""
    _remove_credentials(monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv(user_variable, "cacao")
    monkeypatch.setenv(password_variable, "cacao")

    with pytest.raises(ValueError, match="predeterminadas CACAO"):
        database_helpers.resolver_credenciales_iniciales()


def test_resolver_falla_cerrado_con_senales_de_entorno_contradictorias(monkeypatch):
    """A development marker cannot override a simultaneous production marker."""
    _remove_credentials(monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENV", "development")

    with pytest.raises(ValueError, match="CACAO_USER and CACAO_PSWD"):
        database_helpers.resolver_credenciales_iniciales()


def test_resolver_conserva_credenciales_de_desarrollo(monkeypatch):
    """Development remains able to initialize a local database without secrets."""
    _remove_credentials(monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("ENV", raising=False)

    assert database_helpers.resolver_credenciales_iniciales() == ("cacao", "cacao")


def test_entrypoint_modulo_aborta_si_faltan_credenciales(monkeypatch):
    """The python -m path stops before initializing an administrator with defaults."""
    initialization_calls = []

    class FakeAppContext:
        """Provide only the context stack operation used by the module entrypoint."""

        def push(self):
            """Match Flask's pushed application context."""

    class FakeApp:
        """Avoid creating a real database for the entrypoint rejection test."""

        def app_context(self):
            """Return a minimal context object."""
            return FakeAppContext()

    monkeypatch.setattr(cacao_accounting, "create_app", lambda **_kwargs: FakeApp())
    monkeypatch.setattr(database_helpers, "usuarios_creados", lambda: False)
    monkeypatch.setattr(database_helpers, "resolver_credenciales_iniciales", _raise_missing_credentials)
    monkeypatch.setattr(database_helpers, "inicia_base_de_datos", lambda *args, **kwargs: initialization_calls.append(True))
    monkeypatch.setattr(server_module, "server", lambda: None)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("cacao_accounting.__main__", run_name="__main__")

    assert exit_info.value.code == 1
    assert initialization_calls == []


def test_entrypoint_modulo_inicializa_con_credenciales_configuradas(monkeypatch):
    """The module entrypoint passes explicit credentials to first initialization."""
    initialization_calls = []

    class FakeAppContext:
        """Provide only the context stack operation used by the module entrypoint."""

        def push(self):
            """Match Flask's pushed application context."""

    class FakeApp:
        """Avoid creating a real database for the entrypoint test."""

        def app_context(self):
            """Return a minimal context object."""
            return FakeAppContext()

    monkeypatch.setattr(cacao_accounting, "create_app", lambda **_kwargs: FakeApp())
    monkeypatch.setattr(database_helpers, "usuarios_creados", lambda: False)
    monkeypatch.setattr(database_helpers, "resolver_credenciales_iniciales", lambda: ("operador", "clave-segura"))
    monkeypatch.setattr(
        database_helpers,
        "inicia_base_de_datos",
        lambda **kwargs: initialization_calls.append(kwargs),
    )
    monkeypatch.setattr(server_module, "server", lambda: None)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    runpy.run_module("cacao_accounting.__main__", run_name="__main__")

    assert len(initialization_calls) == 1
    assert initialization_calls[0]["user"] == "operador"
    assert initialization_calls[0]["passwd"] == "clave-segura"
    assert initialization_calls[0]["with_examples"] is False


def test_server_entrypoint_aborta_antes_de_crear_usuario_predeterminado(monkeypatch):
    """The WSGI fallback path also refuses an implicit production administrator."""
    calls = []
    monkeypatch.setattr(database_helpers, "verifica_coneccion_db", lambda _app: False)
    monkeypatch.setattr(database_helpers, "resolver_credenciales_iniciales", _raise_missing_credentials)
    monkeypatch.setattr(database_helpers, "inicia_base_de_datos", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(server_module, "serve", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(SystemExit) as exit_info:
        server_module.server()

    assert exit_info.value.code == 1
    assert calls == []


def test_server_entrypoint_inicializa_con_credenciales_configuradas(monkeypatch):
    """The WSGI fallback passes explicit credentials to database initialization."""
    calls = []

    class FakeApp:
        """Provide the application context required by the WSGI startup."""

        def app_context(self):
            """Return an inert context for the fallback initialization."""
            return nullcontext()

    monkeypatch.setattr(server_module, "app", FakeApp())
    monkeypatch.setattr(database_helpers, "verifica_coneccion_db", lambda _app: False)
    monkeypatch.setattr(database_helpers, "resolver_credenciales_iniciales", lambda: ("operador", "clave-segura"))
    monkeypatch.setattr(database_helpers, "inicia_base_de_datos", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(server_module, "serve", lambda *args, **kwargs: calls.append({"served": True}))

    server_module.server()

    assert calls[0]["user"] == "operador"
    assert calls[0]["passwd"] == "clave-segura"
    assert calls[1] == {"served": True}


def test_run_py_sirve_base_existente_sin_credenciales_de_alta(monkeypatch):
    """An initialized database does not need initial-admin credentials to start."""
    served = []

    class FakeApp:
        """Provide the app context required by the startup script."""

        def app_context(self):
            """Return an inert context for the existing-database branch."""
            return nullcontext()

    monkeypatch.setattr(cacao_accounting, "create_app", lambda *_args, **_kwargs: FakeApp())
    monkeypatch.setattr(database_helpers, "verifica_coneccion_db", lambda **_kwargs: True)
    monkeypatch.setattr(database_helpers, "usuarios_creados", lambda: True)
    monkeypatch.setattr(database_helpers, "resolver_credenciales_iniciales", _raise_missing_credentials)
    monkeypatch.setattr(waitress_module, "serve", lambda *args, **kwargs: served.append((args, kwargs)))

    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run.py"), run_name="__main__")

    assert len(served) == 1


def test_cli_db_init_es_idempotente_sin_credenciales_de_alta(monkeypatch):
    """The idempotent init command returns before resolving initial credentials."""

    class FakeApp:
        """Provide the app context required by the CLI command."""

        def app_context(self):
            """Return an inert context for the existing-database branch."""
            return nullcontext()

    monkeypatch.setattr(cli_module, "_obtener_aplicacion", lambda: FakeApp())
    monkeypatch.setattr(database_helpers, "usuarios_creados", lambda: True)
    monkeypatch.setattr(database_helpers, "resolver_credenciales_iniciales", _raise_missing_credentials)

    result = CliRunner().invoke(cli_module.linea_comandos, ["db", "init"])

    assert result.exit_code == 0
    assert "nada que hacer" in result.output
