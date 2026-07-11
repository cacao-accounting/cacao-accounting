# SPDX-License-Identifier: Apache-2.0
import os
import sys
import subprocess


def test_run_py_fails_fast_in_production_without_credentials():
    """run.py should fail fast and exit 1 in non-dev envs when credentials are missing."""
    env = os.environ.copy()
    # Remove credentials from env
    env.pop("CACAO_USER", None)
    env.pop("CACAO_PSWD", None)

    # Set to production
    env["ENV"] = "production"
    env["FLASK_ENV"] = "production"

    result = subprocess.run([sys.executable, "run.py"], env=env, capture_output=True, text=True, timeout=10)

    assert result.returncode == 1
    # Check that it logged the critical message
    assert (
        "CACAO_USER and CACAO_PSWD must be set in environment" in result.stderr
        or "CACAO_USER and CACAO_PSWD must be set in environment" in result.stdout
    )


def test_run_py_allows_execution_in_dev_without_credentials():
    """run.py should not fail fast in dev mode even if credentials are missing, supporting various cases."""
    env = os.environ.copy()
    # Remove credentials from env
    env.pop("CACAO_USER", None)
    env.pop("CACAO_PSWD", None)

    # Set to different variations of dev
    for dev_val in ("dev", "Dev", "DEVELOPMENT", "DeV"):
        env["ENV"] = dev_val
        env["FLASK_ENV"] = dev_val
        env["CACAO_TEST"] = "True"

        try:
            result = subprocess.run([sys.executable, "run.py"], env=env, capture_output=True, text=True, timeout=4)
            # If it exits, it should not be returncode 1 (credential failure)
            assert result.returncode != 1
            assert "CACAO_USER and CACAO_PSWD must be set in environment" not in result.stderr
            assert "CACAO_USER and CACAO_PSWD must be set in environment" not in result.stdout
        except subprocess.TimeoutExpired:
            # Expected because run.py starts the blocking waitress server
            pass


def test_cli_db_init_fails_fast_in_production_without_credentials():
    """cacaoctl db init should fail fast and exit 1 in production without credentials."""
    env = os.environ.copy()
    # Remove credentials from env
    env.pop("CACAO_USER", None)
    env.pop("CACAO_PSWD", None)

    # Set to production
    env["ENV"] = "production"
    env["FLASK_ENV"] = "production"

    result = subprocess.run(
        [sys.executable, "-c", "from cacao_accounting import command; command()", "db", "init"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert (
        "CACAO_USER and CACAO_PSWD must be set in environment" in result.stdout
        or "CACAO_USER and CACAO_PSWD must be set in environment" in result.stderr
    )


def test_cli_db_reset_fails_fast_in_production_without_credentials():
    """cacaoctl db reset should fail fast and exit 1 in production without credentials."""
    env = os.environ.copy()
    # Remove credentials from env
    env.pop("CACAO_USER", None)
    env.pop("CACAO_PSWD", None)

    # Set to production
    env["ENV"] = "production"
    env["FLASK_ENV"] = "production"

    result = subprocess.run(
        [sys.executable, "-c", "from cacao_accounting import command; command()", "db", "reset"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert (
        "CACAO_USER and CACAO_PSWD must be set in environment" in result.stdout
        or "CACAO_USER and CACAO_PSWD must be set in environment" in result.stderr
    )


def test_cli_db_init_allows_dev_without_credentials():
    """cacaoctl db init should not fail due to credential validation in dev mode (various cases)."""
    env = os.environ.copy()
    # Remove credentials from env
    env.pop("CACAO_USER", None)
    env.pop("CACAO_PSWD", None)

    for dev_val in ("dev", "Dev", "DEVELOPMENT", "DeV"):
        env["ENV"] = dev_val
        env["FLASK_ENV"] = dev_val
        env["CACAO_TEST"] = "True"

        result = subprocess.run(
            [sys.executable, "-c", "from cacao_accounting import command; command()", "db", "init"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # In dev mode, it should not fail on credentials.
        # It might exit with 1 due to DB already existing, which is fine, but not because of CACAO_USER
        assert "CACAO_USER and CACAO_PSWD must be set in environment" not in result.stdout
        assert "CACAO_USER and CACAO_PSWD must be set in environment" not in result.stderr
