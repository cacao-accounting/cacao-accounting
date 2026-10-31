# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Fixtures compartidas y control de recolección de la suite de pruebas."""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


def pytest_addoption(parser):
    """Registrar las banderas historicas --slow y --full de la suite."""
    parser.addoption("--slow", action="store", default="False", help="Run all tests, even those that take the longest.")
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="Run and report full end-to-end business-cycle tests.",
    )


def _check_database_habilitado() -> bool:
    """Verifica si CHECK_DATABASE habilita la ejecución de pruebas de motor real."""
    import os

    return os.environ.get("CHECK_DATABASE", "").strip().lower() in {"1", "true", "yes"}


def pytest_collection_modifyitems(config, items):
    """Salta las pruebas marcadas ``database`` salvo que CHECK_DATABASE este habilitado."""
    if _check_database_habilitado():
        return
    skip_database = pytest.mark.skip(reason="Habilita CHECK_DATABASE=true para validar contra el motor configurado")
    for item in items:
        if "database" in item.keywords:
            item.add_marker(skip_database)


@pytest.fixture
def app():
    """Aplicación de prueba en SQLite en memoria con datos semilla mínimos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with application.app_context():
        from cacao_accounting.database import Book, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(id="admin", user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Book(
                    entity="cacao",
                    code="DEFAULT_BOOK",
                    name="Default",
                    status="activo",
                    is_primary=True,
                    currency="NIO",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        from cacao_accounting.database import database

        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def client(app):
    """Cliente de prueba HTTP sobre la aplicación sembrada."""
    return app.test_client()
