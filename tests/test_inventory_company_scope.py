# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance de compañía en listados y formularios de inventario.

Escenarios de negocio (#1176 / #1543 / #1173, consolidación #1649): un
parámetro `company` manipulado en la URL no debe ampliar el alcance del
listado de movimientos (el servidor responde 403 sin compañía no
autorizada), y el formulario de movimientos no consulta bodegas de una
compañía que el usuario no puede consultar en inventario.
"""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CONTRASENA = "alcance-inv-2026"


def _sembrar_cloud(app):
    with app.app_context():
        database.create_all()
        from cacao_accounting.database import Entity, Modules, User, UserCompanyAccess, Warehouse

        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="secreta",
                    name="Compañía Secreta",
                    company_name="Compañía Secreta SA",
                    tax_id="J0009",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="almacen",
                    user="almacen",
                    name="Almacenista Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="almacen", company_code="cacao"),
                Warehouse(code="BODEGA-SECRET", name="Bodega Secreta", company="secreta", is_active=True),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("almacen", "inventory_auxiliar")


@pytest.fixture
def inventario_cloud():
    """Cloud con dos compañías: el usuario solo consulta inventario de cacao."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    _sembrar_cloud(application)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _movimiento_secreto(application) -> str:
    from cacao_accounting.database import StockEntry, database

    with application.app_context():
        database.session.add(
            StockEntry(
                company="secreta",
                document_no="SECRET-STOCK-DOC",
                purpose="material_receipt",
                posting_date=date(2026, 10, 1),
                docstatus=1,
                total_amount=Decimal("0"),
            )
        )
        database.session.commit()
    return "SECRET-STOCK-DOC"


def test_listado_rechaza_compania_ajena_en_el_filtro(inventario_cloud):
    """#1543/#1176: ?company=<ájan> no amplía el alcance; 403 sin filtrar."""
    application = inventario_cloud
    documento = _movimiento_secreto(application)
    client = application.test_client()
    assert client.post("/login", data={"usuario": "almacen", "acceso": CONTRASENA}, follow_redirects=True).status_code == 200
    response = client.get("/inventory/stock-entry/list?company=secreta")
    assert response.status_code == 403
    assert documento not in response.get_data(as_text=True)


def test_listado_acota_a_las_companias_autorizadas(inventario_cloud):
    """El usuario solo recibe movimientos de sus compañías asignadas."""
    application = inventario_cloud
    client = application.test_client()
    assert client.post("/login", data={"usuario": "almacen", "acceso": CONTRASENA}, follow_redirects=True).status_code == 200
    response = client.get("/inventory/stock-entry/list")
    assert response.status_code == 200
    assert "SECRET-STOCK-DOC" not in response.get_data(as_text=True)


def test_formulario_rechaza_bodegas_de_compania_ajena(inventario_cloud):
    """#1173: el formulario no consulta bodegas de una compañía sin ACL."""
    application = inventario_cloud
    client = application.test_client()
    assert client.post("/login", data={"usuario": "almacen", "acceso": CONTRASENA}, follow_redirects=True).status_code == 200
    response = client.get("/inventory/stock-entry/material-receipt/new?company=secreta")
    assert response.status_code == 403
    assert "BODEGA-SECRET" not in response.get_data(as_text=True)
