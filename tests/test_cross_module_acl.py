# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Aislamiento por módulo de catálogos y fuentes del flujo documental.

Escenarios de negocio (#1515 y #1327, consolidación #1649): el acceso a
un módulo no concede la lectura de catálogos de otro módulo (un usuario
de ventas no consulta cuentas contables ni bancarias) ni anuncia
documentos fuente de módulos cuyo detalle no puede pedir (un usuario de
inventario no ve órdenes de venta como fuentes de su entrega).
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

CONTRASENA = "cross-acl-2026"


def _sembrar_empresa(app):
    with app.app_context():
        database.create_all()
        from cacao_accounting.database import (
            Currency,
            Entity,
            Item,
            Modules,
            SalesOrder,
            SalesOrderItem,
            UOM,
            User,
            UserCompanyAccess,
        )

        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="Unidad", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code="CHOCOLATE-100G", name="Chocolate 100g", item_type="goods", default_uom="Unidad", is_stock_item=False
                ),
                User(id="vendedor", user="vendedor", name="Vendedor", password=proteger_passwd(CONTRASENA), active=True),
                User(id="bodeguero", user="bodeguero", name="Bodeguero", password=proteger_passwd(CONTRASENA), active=True),
                User(id="conta", user="conta", name="Contabilidad", password=proteger_passwd(CONTRASENA), active=True),
                UserCompanyAccess(user_id="vendedor", company_code="cacao"),
                UserCompanyAccess(user_id="bodeguero", company_code="cacao"),
                UserCompanyAccess(user_id="conta", company_code="cacao"),
                SalesOrder(
                    company="cacao",
                    document_no="SO-SECRET-88",
                    posting_date=date(2026, 10, 1),
                    docstatus=1,
                    is_pos=False,
                ),
            ]
        )
        database.session.commit()
        orden = database.session.execute(database.select(SalesOrder)).scalar_one()
        database.session.add(
            SalesOrderItem(
                sales_order_id=orden.id,
                item_code="CHOCOLATE-100G",
                item_name="Chocolate 100g",
                qty=Decimal("10"),
                qty_in_base_uom=Decimal("10"),
                uom="Unidad",
                rate=Decimal("25"),
                amount=Decimal("250"),
            )
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        database.session.commit()
        for usuario, rol in (
            ("vendedor", "sales_auxiliar"),
            ("bodeguero", "inventory_auxiliar"),
            ("conta", "accounting_auxiliar"),
        ):
            asigna_rol_a_usuario(usuario, rol)
    return app


@pytest.fixture
def empresa_cross():
    """Empresa con dos usuarios de módulos distintos y una orden de venta aprobada."""
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
    _sembrar_empresa(application)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _como(client, usuario: str) -> None:
    assert client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True).status_code == 200


def test_search_select_rechaza_catalogos_de_modulo_ajeno(empresa_cross):
    """#1327: el usuario de ventas no consulta cuentas contables ni bancarias."""
    application = empresa_cross
    client = application.test_client()
    _como(client, "vendedor")
    for doctype in ("account", "bank_account"):
        response = client.get(f"/api/search-select?doctype={doctype}&company=cacao&q=a")
        assert response.status_code == 403
        assert b"No se encuentra autorizado" in response.data


def test_search_select_autoriza_catalogos_del_modulo_propio(empresa_cross):
    """Control positivo: ventas ve clientes; contabilidad ve cuentas; admin ve todo."""
    application = empresa_cross
    client_vendedor = application.test_client()
    _como(client_vendedor, "vendedor")
    assert client_vendedor.get("/api/search-select?doctype=customer&company=cacao&q=a").status_code == 200

    client_conta = application.test_client()
    _como(client_conta, "conta")
    assert client_conta.get("/api/search-select?doctype=account&company=cacao&q=a").status_code == 200


def test_source_documents_no_anuncia_origenes_de_modulo_ajeno(empresa_cross):
    """#1515: el usuario de inventario no ve la orden de venta como fuente."""
    application = empresa_cross
    client = application.test_client()
    _como(client, "bodeguero")
    response = client.get("/api/document-flow/source-documents?target_type=delivery_note&company=cacao")
    assert response.status_code == 200
    assert response.get_json()["source_documents"] == []


def test_source_documents_muestra_origenes_del_modulo_propio(empresa_cross):
    """Control positivo: el usuario de ventas ve su pedido como fuente de factura."""
    application = empresa_cross
    client = application.test_client()
    _como(client, "vendedor")
    response = client.get("/api/document-flow/source-documents?target_type=sales_invoice&company=cacao")
    assert response.status_code == 200
    fuentes = response.get_json()["source_documents"]
    assert any(fuente.get("document_no") == "SO-SECRET-88" for fuente in fuentes)
