# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Causa raíz #2207: entradas desconocidas responden 400/404, no 500.

Cubre los hijos restantes del paraguas:
- #1465: tipo destino desconocido en el API de flujo.
- #1787: entidad inexistente al predeterminar (ya corregida en faa62b68).
- #2164: unidad inexistente en el detalle.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_el_api_de_flujo_rechaza_tipo_destino_desconocido():
    """#1465: un target desconocido responde 400, no 500."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/api/document-flow/create-target",
            json={
                "source_document_type": "sales_request",
                "source_document_id": "SRC-1",
                "target_document_type": "not_a_document",
                "company": "cacao",
                "posting_date": "2026-01-02",
                "lines": [],
            },
        )

        assert respuesta.status_code in (400, 404)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_predeterminar_entidad_inexistente_responde_404():
    """#1787: la ruta no desreferencia un resultado vacío."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/accounting/entity/set_default/no-existe")

        assert respuesta.status_code == 404
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_unidad_inexistente_responde_404():
    """#2164: el detalle de unidad controla el registro ausente."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/accounting/unit/MISSING")

        assert respuesta.status_code == 404
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
