# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Las acciones del detalle O2C respetan los permisos de escritura del rol."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import g
from flask_login import current_user, login_user

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import (
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.ventas import routes as sales_routes

FECHA = date(2026, 9, 15)


def _crear_lector(app) -> str:
    """Crea un usuario de ventas con lectura y sin permisos de escritura."""
    suffix = uuid4().hex
    with app.app_context():
        module_id = obtener_id_modulo_por_nombre("sales")
        role = Roles(name=f"sales-reader-{suffix}", note="Solo lectura de ventas")
        user = User(
            user=f"sales-reader-{suffix}",
            name="Lector de ventas",
            password=proteger_passwd("sales-reader-test"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add_all([role, user])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=module_id,
                    access=True,
                    view=True,
                    create=False,
                    edit=False,
                    approve=False,
                    set_null=False,
                ),
                RolesUser(user_id=user.id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user.id, company_code="cacao"),
            ]
        )
        database.session.commit()
        permissions = Permisos(modulo=module_id, usuario=user.id)
        assert not permissions.administrador
        assert permissions.consultar
        assert not any((permissions.crear, permissions.editar, permissions.autorizar, permissions.anular))
        user_id = str(user.id)
    return user_id


def _ver_detalle(app, user_id: str, detail_path: str, document_id: str):
    """Renderiza el endpoint con una solicitud nueva y una identidad controlada."""
    view = sales_routes.ventas_factura_venta if detail_path.endswith("sales-invoice") else sales_routes.ventas_orden_venta
    id_parameter = "invoice_id" if detail_path.endswith("sales-invoice") else "order_id"
    with app.test_request_context(f"{detail_path}/{document_id}"):
        user = database.session.get(User, user_id)
        login_user(user)
        try:
            result = view(**{id_parameter: document_id})
            return result if isinstance(result, str) else result.get_data(as_text=True)
        finally:
            g.pop("_login_user", None)


def _observar_permisos_de_ruta(monkeypatch):
    """Captura identidad y permisos que la ruta entrega a la plantilla."""
    captured = {}
    original = sales_routes._sales_detail_permissions

    def capture():
        permissions = original()
        captured["user_id"] = str(current_user.id)
        captured["classification"] = current_user.classification
        captured["permissions"] = permissions
        return permissions

    monkeypatch.setattr(sales_routes, "_sales_detail_permissions", capture)
    return captured


def _sembrar_documento(app, tipo: str, estado: int) -> tuple[str, str]:
    """Crea una factura u orden mínima para comprobar sus acciones visibles."""
    document_id = uuid4().hex
    with app.app_context():
        if tipo == "factura":
            document = SalesInvoice(
                company="cacao",
                posting_date=FECHA,
                docstatus=estado,
                document_no=f"INV-{document_id}",
                document_type="sales_invoice",
                customer_name="Cliente de prueba",
                transaction_currency="NIO",
            )
            database.session.add(document)
            database.session.flush()
            database.session.add(
                SalesInvoiceItem(
                    sales_invoice_id=document.id,
                    item_code="ART01",
                    item_name="Artículo",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("50"),
                    amount=Decimal("50"),
                )
            )
            detail_path = "/sales/sales-invoice"
        else:
            document = SalesOrder(
                company="cacao",
                posting_date=FECHA,
                docstatus=estado,
                document_no=f"ORD-{document_id}",
                customer_name="Cliente de prueba",
                transaction_currency="NIO",
            )
            database.session.add(document)
            database.session.flush()
            database.session.add(
                SalesOrderItem(
                    sales_order_id=document.id,
                    item_code="ART01",
                    item_name="Artículo",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("50"),
                    amount=Decimal("50"),
                )
            )
            detail_path = "/sales/sales-order"
        database.session.commit()
        return detail_path, str(document.id)


@pytest.mark.parametrize("tipo", ["factura", "orden"])
def test_lector_ve_detalle_sin_acciones_de_escritura(app, entorno_contable, monkeypatch, tipo):
    """Un lector ve el detalle pero no los enlaces o formularios que escriben."""
    user_id = _crear_lector(app)
    detail_path, document_id = _sembrar_documento(app, tipo, estado=0)
    observed = _observar_permisos_de_ruta(monkeypatch)
    response = _ver_detalle(app, user_id, detail_path, document_id)

    assert observed["user_id"] == user_id, observed
    assert all(not value for value in observed["permissions"].values())
    html = response
    assert f"{detail_path}/{document_id}/edit" not in html
    assert f"{detail_path}/{document_id}/duplicate" not in html
    assert f"{detail_path}/{document_id}/submit" not in html
    assert f"/api/attachments/{'sales_invoice' if tipo == 'factura' else 'sales_order'}/{document_id}/upload" not in html
    assert "Subir adjunto" not in html


@pytest.mark.parametrize("tipo", ["factura", "orden"])
def test_lector_no_ve_anulacion_de_documento_contabilizado(app, entorno_contable, monkeypatch, tipo):
    """Un lector tampoco puede iniciar la anulación de un documento aprobado."""
    user_id = _crear_lector(app)
    detail_path, document_id = _sembrar_documento(app, tipo, estado=1)
    observed = _observar_permisos_de_ruta(monkeypatch)
    response = _ver_detalle(app, user_id, detail_path, document_id)

    assert observed["user_id"] == user_id, observed
    assert all(not value for value in observed["permissions"].values())
    html = response
    assert f"{detail_path}/{document_id}/cancel" not in html
    assert f"{detail_path}/{document_id}/edit" not in html
