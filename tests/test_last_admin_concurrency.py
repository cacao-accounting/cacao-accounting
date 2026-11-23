# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1767: dos desactivaciones concurrentes no dejan el sistema sin admin."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.admin import services as admin_services
from cacao_accounting.config import configuracion
from cacao_accounting.database import User, database

pytestmark = pytest.mark.database


@pytest.fixture
def admin_app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'last-admin.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    sufijo = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                User(
                    id=f"adm-a-{sufijo}",
                    user=f"adm-a-{sufijo}",
                    name="A",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                User(
                    id=f"adm-b-{sufijo}",
                    user=f"adm-b-{sufijo}",
                    name="B",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        ids = [f"adm-a-{sufijo}", f"adm-b-{sufijo}"]
    yield app, ids


def _desactivar(app, user_id: str, barrera: Barrier) -> str:
    with app.app_context():
        try:
            barrera.wait(timeout=10)
            admin_services._lock_last_admin_users(user_id)
            usuario = database.session.get(User, user_id, populate_existing=True)
            if admin_services._would_leave_no_admin(usuario, active=False, classification=usuario.classification):
                database.session.rollback()
                return "rechazado"
            usuario.active = False
            database.session.commit()
            return "desactivado"
        except Exception:
            database.session.rollback()
            return "error"


def test_dos_desactivaciones_concurrentes_conservan_un_admin(admin_app):
    """Exactamente una de las dos transiciones puede completarse."""
    app, ids = admin_app
    barrera = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda uid: _desactivar(app, uid, barrera), ids))

    assert resultados.count("desactivado") == 1, resultados
    with app.app_context():
        consulta = database.select(User).filter_by(active=True, classification="admin")
        activos = database.session.execute(consulta).scalars().all()
        assert len([u for u in activos if u.id in ids]) == 1
