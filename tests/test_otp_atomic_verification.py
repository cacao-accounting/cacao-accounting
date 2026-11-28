# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1696: el OTP se reclama y consume intentos de forma atómica.

Bajo concurrencia, un mismo código solo puede validarse una vez y cada
intento fallido ocupa exactamente un cupo del límite persistido.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from cacao_accounting import create_app
from cacao_accounting.auth import device_verification
from cacao_accounting.auth.device_verification import OTP_MAX_ATTEMPTS, generar_otp, validar_otp
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, OtpVerification, User, database

WORKERS = 6


@pytest.fixture
def otp_atomic_scenario(tmp_path):
    """Create a file-backed SQLite app so concurrent sessions see one row."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'otp-atomic.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(
                    id=f"otp-{suffix}",
                    user=f"otp-{suffix}",
                    name="Usuario OTP",
                    password=b"unused",
                    active=True,
                ),
            ]
        )
        database.session.commit()
        ids = {"user": f"otp-{suffix}"}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _issue_code(app, user_id: str) -> str:
    """Issue and persist one pending OTP for the user."""
    with app.app_context():
        code = generar_otp(user_id)
        database.session.commit()
        return code


def _run_concurrently(app, user_id: str, codes: list[str]) -> list[bool]:
    """Validate one code per worker after a common start line."""
    start = Barrier(len(codes))

    def attempt(code: str) -> bool:
        with app.app_context():
            try:
                start.wait(timeout=20)
                result = validar_otp(user_id, code)
                database.session.commit()
                return result
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=len(codes)) as workers:
        return list(workers.map(attempt, codes))


def _sync_digest_after_read(monkeypatch, workers: int) -> None:
    """Pause every validator after its read so the claim runs concurrently."""
    barrier = Barrier(workers)
    original = device_verification._otp_digest

    def synchronized(user_id: str, purpose: str, code: str) -> str:
        digest = original(user_id, purpose, code)
        barrier.wait(timeout=20)
        return digest

    monkeypatch.setattr(device_verification, "_otp_digest", synchronized)


def _retry_locked(callable_, attempts: int = 5):
    """Retry a SQLite write that hits the transient database lock."""
    for _ in range(attempts):
        try:
            return callable_()
        except OperationalError as exc:  # pragma: no cover - depends on scheduler
            if "locked" not in str(exc).lower():
                raise
    return callable_()


def test_concurrent_validations_accept_the_code_only_once(otp_atomic_scenario, monkeypatch):
    """Two or more simultaneous correct validations cannot all succeed."""
    app, ids = otp_atomic_scenario
    code = _issue_code(app, ids["user"])
    _sync_digest_after_read(monkeypatch, WORKERS)

    outcomes = _retry_locked(lambda: _run_concurrently(app, ids["user"], [code] * WORKERS))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == WORKERS - 1


def test_concurrent_wrong_attempts_consume_the_persisted_limit(otp_atomic_scenario, monkeypatch):
    """Parallel wrong attempts reach the limit and block the valid code."""
    app, ids = otp_atomic_scenario
    code = _issue_code(app, ids["user"])
    wrong = "000000" if code != "000000" else "111111"
    _sync_digest_after_read(monkeypatch, WORKERS)

    outcomes = _retry_locked(lambda: _run_concurrently(app, ids["user"], [wrong] * WORKERS))

    assert outcomes.count(True) == 0
    with app.app_context():
        registro = database.session.execute(database.select(OtpVerification).filter_by(user_id=ids["user"])).scalar_one()
        assert registro.attempts == OTP_MAX_ATTEMPTS
        assert registro.consumed is True
        assert validar_otp(ids["user"], code) is False
        database.session.commit()
