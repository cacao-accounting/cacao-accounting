# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cacao_accounting.cli import linea_comandos


def _production_env() -> dict[str, str | None]:
    """Return a clean production environment for CLI credential checks."""
    return {
        "CACAO_USER": None,
        "CACAO_PSWD": None,
        "ADMIN_USER": None,
        "ADMIN_PASSWORD": None,
        "CACAO_TEST": None,
        "ENV": "production",
        "FLASK_ENV": "production",
    }


def test_run_py_fails_fast_in_production_without_credentials(monkeypatch):
    """run.py's credential resolver must reject missing production credentials."""
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("FLASK_ENV", "production")

    from cacao_accounting.database.helpers import resolver_credenciales_iniciales

    with pytest.raises(ValueError, match="CACAO_USER and CACAO_PSWD must be set in environment"):
        resolver_credenciales_iniciales()


@pytest.mark.parametrize("command", ["init", "reset"])
def test_cli_db_commands_fail_fast_in_production_without_credentials(command):
    """Database CLI commands must stop before application initialization."""
    result = CliRunner().invoke(linea_comandos, ["db", command], env=_production_env())

    assert result.exit_code == 1
    assert "CACAO_USER and CACAO_PSWD must be set in environment" in result.output


@pytest.mark.parametrize("dev_value", ["dev", "Dev", "DEVELOPMENT", "DeV"])
def test_cli_db_init_allows_dev_without_credentials(monkeypatch, dev_value):
    """The development CLI path resolves default credentials without starting a database."""
    from cacao_accounting.database import helpers

    monkeypatch.setattr(helpers, "usuarios_creados", lambda: True)
    monkeypatch.setattr(
        "cacao_accounting.cli._obtener_aplicacion",
        lambda: SimpleNamespace(app_context=lambda: nullcontext()),
    )

    result = CliRunner().invoke(
        linea_comandos,
        ["db", "init"],
        env={
            "CACAO_USER": None,
            "CACAO_PSWD": None,
            "ADMIN_USER": None,
            "ADMIN_PASSWORD": None,
            "ENV": dev_value,
            "FLASK_ENV": dev_value,
            "CACAO_TEST": "True",
        },
    )

    assert result.exit_code == 0
    assert "CACAO_USER and CACAO_PSWD must be set in environment" not in result.output
