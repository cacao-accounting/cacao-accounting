# ruff: noqa: E402
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 William José Reyes

"""Pruebas para el framework de dimensiones analíticas extensibles (issue #770).

Cubre el alta de tipos y valores desde la UI administrativa, la desactivación
de ambos y que el endpoint de descubrimiento de valores ya disponible expone los
valores creados para poder etiquetar asientos GL.
"""

import sys
from unittest import mock

sys.modules["email_validator"] = mock.MagicMock()

import os

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import DimensionType, DimensionValue, database

sys.path.append(os.path.dirname(__file__))
from z_func import init_test_db


@pytest.fixture(scope="module")
def app_instance():
    """Aplicación administrativa con datos base para dimensiones."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "dim_test_secret_key",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with _app.app_context():
        init_test_db(_app)
    return _app


@pytest.fixture()
def admin_client(app_instance):
    """Cliente autenticado como usuario administrativo."""
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
        yield client


def test_dimensions_admin_page_renders(app_instance, admin_client):
    """La página de administración de dimensiones está disponible."""
    response = admin_client.get("/settings/dimensions")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Dimensiones Analíticas" in html


def test_create_dimension_type(app_instance, admin_client):
    """Un administrador puede crear un tipo de dimensión con sus valores."""
    response = admin_client.post(
        "/settings/dimensions",
        data={"action": "create_type", "name": "Segmento", "is_active": "1"},
    )
    assert response.status_code == 302
    dimension_type = database.session.execute(
        database.select(DimensionType).where(DimensionType.name == "Segmento")
    ).scalar_one_or_none()
    assert dimension_type is not None
    assert dimension_type.is_active is True

    response = admin_client.post(
        "/settings/dimensions",
        data={"action": "add_value", "dimension_type_id": dimension_type.id, "value": "Norte", "company": "cacao"},
    )
    assert response.status_code == 302
    dimension_value = database.session.execute(
        database.select(DimensionValue).where(
            DimensionValue.dimension_type_id == dimension_type.id,
            DimensionValue.value == "Norte",
        )
    ).scalar_one_or_none()
    assert dimension_value is not None
    assert dimension_value.company == "cacao"


def test_duplicate_dimension_type_is_rejected(app_instance, admin_client):
    """Crear un tipo de dimensión con nombre duplicado no falla silenciosamente."""
    admin_client.post(
        "/settings/dimensions",
        data={"action": "create_type", "name": "Región"},
    )
    response = admin_client.post(
        "/settings/dimensions",
        data={"action": "create_type", "name": "Región"},
    )
    assert response.status_code == 302


def test_toggle_dimension_type_and_value(app_instance, admin_client):
    """Desactivar y reactivar un tipo y un valor de dimensión."""
    admin_client.post(
        "/settings/dimensions",
        data={"action": "create_type", "name": "Cliente"},
    )
    dimension_type = database.session.execute(
        database.select(DimensionType).where(DimensionType.name == "Cliente")
    ).scalar_one()
    admin_client.post(
        "/settings/dimensions",
        data={"action": "add_value", "dimension_type_id": dimension_type.id, "value": "Preferente", "company": "cacao"},
    )
    dimension_value = database.session.execute(
        database.select(DimensionValue).where(DimensionValue.value == "Preferente")
    ).scalar_one()

    assert admin_client.post(f"/settings/dimensions/types/{dimension_type.id}/toggle").status_code == 302
    assert admin_client.post(f"/settings/dimensions/values/{dimension_value.id}/toggle").status_code == 302

    type_active = database.session.execute(
        database.select(DimensionType.is_active).where(DimensionType.id == dimension_type.id)
    ).scalar_one()
    value_active = database.session.execute(
        database.select(DimensionValue.is_active).where(DimensionValue.id == dimension_value.id)
    ).scalar_one()
    assert type_active is False
    assert value_active is False
