# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los CTAs del detalle de venta reflejan los permisos efectivos.

Escenario de negocio (issue #2053): las plantillas de factura y orden decidían
Editar, Duplicar, Aprobar y la carga de adjuntos solo por ``docstatus``. Un
perfil de solo lectura veía acciones que los endpoints rechazaban con 403.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    SalesInvoice,
    SalesOrder,
    User,
    UserCompanyAccess,
    database,
)

FECHA = date(2026, 10, 15)


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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
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
                    id="viewer",
                    user="viewer",
                    name="Solo Lectura",
                    password=b"x",
                    active=True,
                    classification="system",
                ),
                User(
                    id="editor",
                    user="editor",
                    name="Editor",
                    password=b"x",
                    active=True,
                    classification="system",
                ),
                User(
                    id="auxiliar",
                    user="auxiliar",
                    name="Auxiliar",
                    password=b"x",
                    active=True,
                    classification="system",
                ),
                UserCompanyAccess(user_id="viewer", company_code="cacao"),
                UserCompanyAccess(user_id="editor", company_code="cacao"),
                UserCompanyAccess(user_id="auxiliar", company_code="cacao"),
                SalesOrder(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=0,
                    customer_name="Cliente",
                    transaction_currency="NIO",
                ),
                SalesInvoice(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=0,
                    customer_name="Cliente",
                    transaction_currency="NIO",
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("viewer", "sales_user")
        asigna_rol_a_usuario("auxiliar", "sales_auxiliar")
        asigna_rol_a_usuario("editor", "sales_manager")
        database.session.commit()
        orden = database.session.execute(database.select(SalesOrder)).scalar_one()
        factura = database.session.execute(database.select(SalesInvoice)).scalar_one()
        ids = {"orden": orden.id, "factura": factura.id}
    return application, ids


def _cliente(application, usuario: str):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = usuario
        session["_fresh"] = True
    return client


def _html(application, usuario: str, ruta: str) -> str:
    client = _cliente(application, usuario)
    respuesta = client.get(ruta)
    assert respuesta.status_code == 200
    return respuesta.get_data(as_text=True)


def test_el_perfil_de_lectura_no_ve_acciones_de_mutacion():
    """Viewer conserva el detalle pero sin CTAs ni carga de adjuntos."""
    application, ids = _crear_app()
    try:
        for ruta in (
            f"/sales/sales-order/{ids['orden']}",
            f"/sales/sales-invoice/{ids['factura']}",
        ):
            html = _html(application, "viewer", ruta)
            assert "Editar" not in html
            assert "Duplicar" not in html
            assert "Aprobar" not in html
            assert "Subir adjunto" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_editor_conserva_las_acciones_permitidas():
    """El control positivo muestra los CTAs para quien puede ejecutarlos."""
    application, ids = _crear_app()
    try:
        for ruta in (
            f"/sales/sales-order/{ids['orden']}",
            f"/sales/sales-invoice/{ids['factura']}",
        ):
            html = _html(application, "editor", ruta)
            assert "Editar" in html
            assert "Duplicar" in html
            assert "Aprobar" in html
            assert "Subir adjunto" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_auxiliar_no_ve_aprobar_sin_autorizacion():
    """Editar y duplicar no implican poder aprobar el documento."""
    application, ids = _crear_app()
    try:
        for ruta in (
            f"/sales/sales-order/{ids['orden']}",
            f"/sales/sales-invoice/{ids['factura']}",
        ):
            html = _html(application, "auxiliar", ruta)
            assert "Editar" in html
            assert "Duplicar" in html
            assert "Aprobar" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
