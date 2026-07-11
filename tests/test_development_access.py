# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para verificar restricciones de acceso a las rutas de desarrollo."""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_func import init_test_db  # noqa: E402
from cacao_accounting import create_app  # noqa: E402
from cacao_accounting.database import User, database  # noqa: E402
from cacao_accounting.auth import proteger_passwd  # noqa: E402

app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)


def test_development_access_restrictions(request):
    """Verifica que solo los administradores puedan acceder a /development, /dev e /info."""
    if request.config.getoption("--slow") == "True":
        with app.app_context():
            init_test_db(app)

            hashed_pwd = proteger_passwd("passwd123")
            non_admin = User(
                user="test_non_admin",
                password=hashed_pwd,
                active=True,
                classification="user",
            )
            database.session.add(non_admin)
            database.session.commit()

            with app.test_client() as client:
                # Test 1: Sin iniciar sesión
                for path in ["/development", "/dev", "/info"]:
                    res = client.get(path)
                    assert res.status_code in [302, 401, 403]

                # Test 2: Como usuario estándar (no admin)
                client.post("/login", data={"usuario": "test_non_admin", "acceso": "passwd123"})
                for path in ["/development", "/dev", "/info"]:
                    res = client.get(path)
                    assert res.status_code == 403

                # Cerrar sesión
                client.get("/logout")

                # Test 3: Como usuario administrador
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                for path in ["/development", "/dev", "/info"]:
                    res = client.get(path)
                    assert res.status_code == 200
