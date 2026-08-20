# ruff: noqa: E402
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 William José Moreno Reyes

"""Pruebas unitarias para la configuración de idioma global y por usuario."""

import os
import sys
from unittest import mock
import pytest

# Mock email_validator module to avoid environment dependency errors in WTForms Email validator
sys.modules["email_validator"] = mock.MagicMock()

sys.path.append(os.path.join(os.path.dirname(__file__)))
from cacao_accounting import _get_locale, create_app
from cacao_accounting.database import User, database
from cacao_accounting.setup.service import SETUP_LANGUAGE, set_setup_value
from z_func import init_test_db


@pytest.fixture(scope="module")
def app_instance():
    """Instancia de aplicación Flask con base de datos en memoria para pruebas de idioma."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "language_test_secret_key",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with _app.app_context():
        init_test_db(_app)
        cacao_user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one_or_none()
        if cacao_user:
            cacao_user.classification = "admin"
            cacao_user.language = None
            database.session.commit()
    return _app


def test_user_profile_language_update(app_instance):
    """Verifica que el usuario pueda actualizar su idioma preferido desde /auth/profile."""
    with app_instance.test_client() as client:
        # Autenticar
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET perfil contiene campo de idioma
        response = client.get("/auth/profile")
        assert response.status_code == 200
        assert b"Idioma" in response.data

        # POST actualizar idioma a 'en'
        response = client.post(
            "/auth/profile",
            data={
                "name": "Cacao",
                "e_mail": "cacao@example.com",
                "language": "en",
                "guardar_perfil": "Guardar cambios",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"actualizada correctamente" in response.data

        with app_instance.app_context():
            user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
            assert user.language == "en"

        # POST actualizar idioma a vacío (predeterminado del sistema -> None)
        response = client.post(
            "/auth/profile",
            data={
                "name": "Cacao",
                "e_mail": "cacao@example.com",
                "language": "",
                "guardar_perfil": "Guardar cambios",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app_instance.app_context():
            user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
            assert user.language is None


def test_get_locale_cascade(app_instance):
    """Verifica la resolución en cascada de _get_locale()."""
    from flask_login import login_user

    # 1. Sin usuario autenticado -> usa SETUP_LANGUAGE global
    with app_instance.test_request_context():
        set_setup_value(SETUP_LANGUAGE, "es")
        database.session.commit()
        assert _get_locale() == "es"

        set_setup_value(SETUP_LANGUAGE, "en")
        database.session.commit()
        assert _get_locale() == "en"

    # 2. Con usuario autenticado que tiene idioma preferido -> prevalece usuario
    with app_instance.test_request_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        user.language = "es"
        database.session.commit()
        login_user(user)

        # Aunque el setup global sea 'en', el usuario tiene 'es'
        assert _get_locale() == "es"

    # 3. Usuario autenticado sin idioma preferido -> hereda setup global
    with app_instance.test_request_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        user.language = None
        database.session.commit()
        login_user(user)

        assert _get_locale() == "en"

    # Restaurar setup global a 'es'
    with app_instance.app_context():
        set_setup_value(SETUP_LANGUAGE, "es")
        database.session.commit()
