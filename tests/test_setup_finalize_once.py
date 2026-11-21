# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1021: el asistente inicial se completa una sola vez.

La finalización reclama la clave única `SETUP_COMPLETE` antes de crear la
compañía; dos solicitudes concurrentes no duplican compañía, libros ni
configuración, y un reintento reconoce la instalación completada.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Book,
    CacaoConfig,
    Currency,
    Entity,
    Modules,
    User,
    database,
)
from cacao_accounting.setup.service import SetupAlreadyComplete, finalize_setup
from cacao_accounting.setup.service import SETUP_COMPLETED

WORKERS = 2


def _company_payload() -> dict:
    """Build the initial company payload for the setup finalization."""
    suffix = uuid4().hex[:6]
    return {
        "id": f"INI{suffix}".upper()[:10],
        "razon_social": f"Compañía Inicial {suffix}",
        "nombre_comercial": f"Inicial {suffix}",
        "id_fiscal": f"J-{suffix}",
        "tipo_entidad": "company",
        "moneda": "NIO",
        "pais": "NI",
        "inicio_anio_fiscal": date(2026, 1, 1),
        "fin_anio_fiscal": date(2026, 12, 31),
    }


@pytest.fixture
def setup_once_scenario(tmp_path):
    """Create a file-backed app with the base currency and admin user."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'setup-once.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"timeout": 30}},
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        ids = {"admin": f"admin-{suffix}"}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _run_finalize(app, payload: dict) -> str:
    """Finalize once per worker and report the outcome."""
    with app.app_context():
        try:
            finalize_setup(payload, "nuevo", "NI", "es")
            return "completed"
        except SetupAlreadyComplete:
            return "already-complete"
        finally:
            database.session.remove()


def _retry_locked(callable_, attempts: int = 5):
    """Retry a SQLite write that hits the transient database lock."""
    for _ in range(attempts):
        try:
            return callable_()
        except OperationalError as exc:  # pragma: no cover - depends on scheduler
            if "locked" not in str(exc).lower():
                raise
    return callable_()


def test_concurrent_finalize_creates_one_company(setup_once_scenario):
    """Two simultaneous finalizations produce one company and one config row."""
    app, _ids = setup_once_scenario
    payload = _company_payload()
    barrier = Barrier(WORKERS)

    def finalize() -> str:
        barrier.wait(timeout=20)
        return _run_finalize(app, payload)

    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        outcomes = _retry_locked(lambda: list(workers.map(lambda _: finalize(), range(WORKERS))))

    assert sorted(outcomes) == ["already-complete", "completed"]
    with app.app_context():
        assert database.session.execute(database.select(database.func.count(Entity.id))).scalar_one() == 1
        rows = database.session.execute(database.select(CacaoConfig).filter_by(key=SETUP_COMPLETED)).scalars().all()
        assert len(rows) == 1
        assert database.session.execute(database.select(database.func.count(Book.id))).scalar_one() == 1


def test_retry_after_completion_is_rejected_without_side_effects(setup_once_scenario):
    """A later retry recognizes the completed installation."""
    app, _ids = setup_once_scenario
    payload = _company_payload()

    assert _run_finalize(app, payload) == "completed"
    assert _run_finalize(app, payload) == "already-complete"

    with app.app_context():
        assert database.session.execute(database.select(database.func.count(Entity.id))).scalar_one() == 1
        assert database.session.execute(database.select(database.func.count(Book.id))).scalar_one() == 1


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_setup_route_tolerates_a_corrupt_session_step(setup_once_scenario):
    """A non-numeric setup step falls back to step 1 instead of failing."""
    app, ids = setup_once_scenario
    client = _authenticated_client(app, ids["admin"])
    with client.session_transaction() as http_session:
        http_session["setup_step"] = "not-a-number"

    response = client.get("/setup/")

    assert response.status_code == 200


def test_setup_route_redirects_when_the_installation_is_complete(setup_once_scenario):
    """A completed installation never reopens the wizard."""
    app, ids = setup_once_scenario
    payload = _company_payload()
    assert _run_finalize(app, payload) == "completed"
    client = _authenticated_client(app, ids["admin"])

    response = client.get("/setup/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/index")
