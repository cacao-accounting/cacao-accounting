# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Presentación y seguridad de las pantallas de caja.

Escenario de negocio:
- #1975: el estado vacío cubría 8 de 9 columnas.
- #1981: «Nuevo» se mostraba sin permiso cash.crear.
- #1985: custodian_id se interpolaba sin escape de contexto Alpine.
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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                ),
                User(
                    id="viewer",
                    user="viewer",
                    name="Consulta",
                    password=b"x",
                    active=True,
                    classification="user",
                ),
            ]
        )
        database.session.commit()
    return application


def _cliente(application, user_id: str = "admin"):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_estado_vacio_cubre_las_nueve_columnas():
    """#1975: el colspan coincide con los encabezados de la tabla."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/cash_management/petty-cash/list").get_data(as_text=True)

        assert html.count('<th scope="col">') == 9
        assert 'colspan="9"' in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_boton_nuevo_respeta_permiso_de_creacion():
    """#1981: el enlace solo se ofrece con cash.crear."""
    application = _crear_app()
    try:
        admin_html = _cliente(application).get("/cash_management/bank-account/list").get_data(as_text=True)
        viewer_html = _cliente(application, "viewer").get("/cash_management/bank-account/list").get_data(as_text=True)

        assert "Nuevo" in admin_html
        assert "Nuevo" not in viewer_html
        assert "/cash_management/bank-account/new" not in viewer_html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_custodian_id_se_serializa_para_alpine():
    """#1985: el valor reflejado no cierra el string de x-data."""
    application = _crear_app()
    try:
        client = _cliente(application)
        payload = "'); alert(1); //"
        respuesta = client.post(
            "/cash_management/petty-cash/new",
            data={"company": "cacao", "name": "Caja", "float_amount": "0", "custodian_id": payload},
        )

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "\\u0027); alert(1)" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
