"""Credential defaults are available only in explicitly configured development environments."""

import os

import pytest
from click.testing import CliRunner

from cacao_accounting.cli import _entorno_actual, linea_comandos
from cacao_accounting.database.helpers import resolver_credenciales_iniciales


@pytest.mark.parametrize("environment_variable", ["ENV", "FLASK_ENV"])
@pytest.mark.parametrize("development_name", ["dev", "development"])
def test_default_initial_credentials_are_available_in_development(monkeypatch, environment_variable, development_name):
    """Local development can initialize the database without custom credentials."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("CACAO_TEST", raising=False)
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv(environment_variable, development_name)

    assert resolver_credenciales_iniciales() == ("cacao", "cacao")


@pytest.mark.parametrize("environment", ["production", "testing"])
def test_default_initial_credentials_are_rejected_outside_development(monkeypatch, environment):
    """Default administrator credentials cannot initialize non-development environments."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("ENV", environment)
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(ValueError):
        resolver_credenciales_iniciales()


def test_cli_recognizes_short_production_environment_name(monkeypatch):
    """The CLI recognizes the supported short production environment name."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("CACAO_TEST", raising=False)

    assert _entorno_actual() == "production"


@pytest.mark.parametrize("environment", ["production", "testing"])
def test_explicit_default_credentials_are_rejected_outside_development(monkeypatch, environment):
    """Explicit legacy aliases cannot bypass the non-development guard."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("ENV", environment)
    monkeypatch.setenv("CACAO_USER", "cacao")
    monkeypatch.setenv("CACAO_PSWD", "cacao")
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("CACAO_TEST", "True")
    monkeypatch.setenv("CHECK_DATABASE", "true")
    monkeypatch.setenv("CI", "true")

    with pytest.raises(ValueError):
        resolver_credenciales_iniciales()


def test_explicit_default_credentials_are_allowed_for_database_integration_tests(monkeypatch):
    """Isolated CI engine checks may initialize disposable databases with their test credentials."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("CACAO_TEST", "True")
    monkeypatch.setenv("CHECK_DATABASE", "true")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("CACAO_USER", "cacao")
    monkeypatch.setenv("CACAO_PSWD", "cacao")
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    assert resolver_credenciales_iniciales() == ("cacao", "cacao")


def test_engine_checks_outside_ci_still_reject_default_credentials(monkeypatch):
    """Engine-test flags alone cannot enable weak credentials outside CI."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("CACAO_TEST", "True")
    monkeypatch.setenv("CHECK_DATABASE", "true")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("CACAO_USER", "cacao")
    monkeypatch.setenv("CACAO_PSWD", "cacao")
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(ValueError):
        resolver_credenciales_iniciales()


def test_default_initial_credentials_are_rejected_for_cli_test_environment(monkeypatch):
    """The CLI test marker takes precedence over an inherited development setting."""
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("CACAO_TEST", "True")
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(ValueError):
        resolver_credenciales_iniciales()


def test_false_cli_test_marker_does_not_disable_development_credentials(monkeypatch):
    """False-like test markers keep CLI environment detection aligned with config."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("CACAO_TEST", "0")
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    result = CliRunner().invoke(linea_comandos, ["--env", "dev", "version"])

    assert result.exit_code == 0
    assert os.environ["FLASK_ENV"] == "development"
    assert resolver_credenciales_iniciales() == ("cacao", "cacao")


def test_cli_default_environment_requires_explicit_development(monkeypatch):
    """The CLI does not enable default credentials from an inferred environment."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("CACAO_TEST", raising=False)
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    result = CliRunner().invoke(linea_comandos, ["version"])

    assert result.exit_code == 0
    assert "FLASK_ENV" not in os.environ
    with pytest.raises(ValueError):
        resolver_credenciales_iniciales()


def test_explicit_cli_development_enables_initial_credentials(monkeypatch):
    """The explicit development option enables local setup credentials."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("CACAO_TEST", raising=False)
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    result = CliRunner().invoke(linea_comandos, ["--env", "dev", "version"])

    assert result.exit_code == 0
    assert resolver_credenciales_iniciales() == ("cacao", "cacao")


@pytest.mark.parametrize("configured_environment", ["production", "testing"])
def test_cli_development_option_does_not_override_other_environment(monkeypatch, configured_environment):
    """An explicit CLI environment cannot weaken an existing deployment setting."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("FLASK_ENV", configured_environment)
    monkeypatch.delenv("CACAO_TEST", raising=False)
    monkeypatch.delenv("CACAO_USER", raising=False)
    monkeypatch.delenv("CACAO_PSWD", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    result = CliRunner().invoke(linea_comandos, ["--env", "dev", "version"])

    assert result.exit_code == 0
    assert os.environ["FLASK_ENV"] == configured_environment
    with pytest.raises(ValueError):
        resolver_credenciales_iniciales()
