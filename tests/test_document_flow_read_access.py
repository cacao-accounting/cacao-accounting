# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones para la autorización de lectura de documentos fuente."""

from datetime import date
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    SalesOrder,
    SalesOrderItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesRequest,
    SalesRequestItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

FECHA = date(2026, 10, 15)
CONTRASENA = "cafecacao-2026"


def _sembrar_escenario() -> dict[str, str]:
    """Prepara dos compañías, roles funcionales y fuentes con datos privados."""
    database.session.add_all(
        [
            *[Modules(module=module, default=False, enabled=True) for module in ("sales", "cash", "inventory")],
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J0001", currency="NIO", enabled=True),
            Entity(code="cafe", name="Cafe", company_name="Cafe SA", tax_id="J0002", currency="NIO", enabled=True),
            User(id="vendedor", user="vendedor", name="Vendedor", password=proteger_passwd(CONTRASENA), active=True),
            User(id="tesorero", user="tesorero", name="Tesorero", password=proteger_passwd(CONTRASENA), active=True),
            User(id="ventas_solo", user="ventas_solo", name="Ventas solo", password=proteger_passwd(CONTRASENA), active=True),
            User(
                id="inventario_solo",
                user="inventario_solo",
                name="Inventario solo",
                password=proteger_passwd(CONTRASENA),
                active=True,
            ),
            UserCompanyAccess(user_id="vendedor", company_code="cacao"),
            UserCompanyAccess(user_id="tesorero", company_code="cacao"),
            UserCompanyAccess(user_id="ventas_solo", company_code="cacao"),
            UserCompanyAccess(user_id="inventario_solo", company_code="cacao"),
            SalesRequest(company="cacao", posting_date=FECHA, docstatus=1, customer_name="Cliente Cacao"),
            SalesOrder(
                company="cacao", posting_date=FECHA, docstatus=1, document_no="SO-CACAO", customer_name="Cliente Cacao"
            ),
            SalesOrder(
                company="cafe",
                posting_date=FECHA,
                docstatus=1,
                document_no="SO-CONFIDENCIAL",
                customer_name="Cliente Confidencial",
            ),
            SalesInvoice(
                company="cacao",
                posting_date=FECHA,
                docstatus=1,
                document_no="NC-CACAO",
                document_type="sales_credit_note",
                customer_name="Cliente Crédito Cacao",
            ),
            SalesInvoice(
                company="cacao",
                posting_date=FECHA,
                docstatus=1,
                document_no="DEV-CACAO",
                document_type="sales_return",
                customer_name="Cliente Devolución Cacao",
            ),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            UOM(code="Unidad", name="Unidad"),
        ]
    )
    database.session.flush()
    database.session.add(
        Item(code="ITEM-PRIVADO", name="Producto privado", item_type="goods", is_stock_item=False, default_uom="Unidad")
    )
    database.session.commit()
    crea_roles_predeterminados()
    cargar_permisos_predeterminados()
    asigna_rol_a_usuario("vendedor", "sales_auxiliar")
    asigna_rol_a_usuario("vendedor", "inventory_auxiliar")
    asigna_rol_a_usuario("vendedor", "user_of_treasury")
    asigna_rol_a_usuario("tesorero", "user_of_treasury")
    asigna_rol_a_usuario("ventas_solo", "sales_auxiliar")
    asigna_rol_a_usuario("inventario_solo", "inventory_auxiliar")
    database.session.flush()
    pedido = database.session.execute(database.select(SalesRequest)).scalar_one()
    ordenes = database.session.execute(database.select(SalesOrder).order_by(SalesOrder.company)).scalars().all()
    own_order, foreign_order = ordenes
    invoices = {
        invoice.document_type: invoice for invoice in database.session.execute(database.select(SalesInvoice)).scalars().all()
    }
    own_line = SalesRequestItem(
        sales_request_id=pedido.id,
        item_code="ITEM-PRIVADO",
        item_name="Producto propio",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="Unidad",
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add_all(
        [
            own_line,
            SalesOrderItem(
                sales_order_id=own_order.id,
                item_code="ITEM-PRIVADO",
                item_name="Producto propio",
                qty=Decimal("5"),
                qty_in_base_uom=Decimal("5"),
                uom="Unidad",
                rate=Decimal("10"),
                amount=Decimal("50"),
            ),
            SalesOrderItem(
                sales_order_id=foreign_order.id,
                item_code="ITEM-PRIVADO",
                item_name="Producto secreto de Cafe",
                qty=Decimal("9"),
                qty_in_base_uom=Decimal("9"),
                uom="Unidad",
                rate=Decimal("999"),
                amount=Decimal("8991"),
            ),
            *[
                SalesInvoiceItem(
                    sales_invoice_id=invoice.id,
                    item_code="ITEM-PRIVADO",
                    item_name=invoice.document_no,
                    qty=Decimal("2"),
                    qty_in_base_uom=Decimal("2"),
                    uom="Unidad",
                    rate=Decimal("50"),
                    amount=Decimal("100"),
                )
                for invoice in invoices.values()
            ],
        ]
    )
    database.session.commit()
    return {
        "request": pedido.id,
        "own_order": own_order.id,
        "foreign_order": foreign_order.id,
        "credit_note": invoices["sales_credit_note"].id,
        "sales_return": invoices["sales_return"].id,
    }


@pytest.fixture
def document_flow_app():
    """Aplicación cloud aislada con vendedor multi-módulo y usuario de caja."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        ids = _sembrar_escenario()
    yield app, app.test_client(), ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(client, username: str) -> None:
    """Inicia sesión con una cuenta del fixture."""
    response = client.post("/login", data={"usuario": username, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_document_flow_items_denies_foreign_and_mixed_sources(document_flow_app):
    """Las fuentes extranjeras se bloquean incluso si la petición mezcla ids propios."""
    _, client, ids = document_flow_app
    _login(client, "vendedor")

    response = client.get(f"/api/document-flow/items?target_type=sales_invoice&source=sales_order:{ids['foreign_order']}")
    assert response.status_code == 403
    assert b"Producto secreto de Cafe" not in response.data
    assert b"8991" not in response.data

    response = client.get(
        "/api/document-flow/items?target_type=sales_invoice"
        f"&source=sales_request:{ids['request']}&source=sales_order:{ids['foreign_order']}"
    )
    assert response.status_code == 403
    assert response.get_json() is None


def test_document_flow_items_requires_source_module_permission(document_flow_app):
    """El permiso de caja y el acceso a compañía no conceden lectura de ventas."""
    _, client, ids = document_flow_app
    _login(client, "tesorero")
    response = client.get(f"/api/document-flow/items?target_type=sales_invoice&source=sales_order:{ids['own_order']}")
    assert response.status_code == 403
    assert b"Producto propio" not in response.data


@pytest.mark.parametrize("source_type", ("sales_credit_note", "sales_return"))
def test_document_flow_credit_sources_require_sales_permission(document_flow_app, source_type):
    """Las notas de crédito y devoluciones mantienen ACL de ventas para líneas."""
    _, client, ids = document_flow_app
    _login(client, "tesorero")
    source_id = ids["credit_note"] if source_type == "sales_credit_note" else ids["sales_return"]
    response = client.get(f"/api/document-flow/items?target_type=payment_entry&source={source_type}:{source_id}")
    assert response.status_code == 403
    assert b"NC-CACAO" not in response.data
    assert b"DEV-CACAO" not in response.data


def test_document_flow_items_returns_lines_for_authorized_sales_source(document_flow_app):
    """Control positivo: ventas puede consultar las líneas de una fuente propia."""
    _, client, ids = document_flow_app
    _login(client, "vendedor")
    response = client.get(f"/api/document-flow/items?target_type=sales_order&source=sales_request:{ids['request']}")
    assert response.status_code == 200
    rows = response.get_json()["items"]
    assert any(row.get("item_code") == "ITEM-PRIVADO" for row in rows)


def test_source_document_picker_filters_sales_for_cash_only_user(document_flow_app):
    """El selector de fuentes no anuncia órdenes que el rol de caja no puede leer."""
    _, client, _ = document_flow_app
    _login(client, "tesorero")
    response = client.get("/api/document-flow/source-documents?target_document_type=payment_entry&company=cacao")
    assert response.status_code == 200
    source_documents = response.get_json()["source_documents"]
    assert all(row.get("source_type") != "sales_order" for row in source_documents)


def test_source_document_picker_hides_sales_credit_notes_from_cash_only_user(document_flow_app, monkeypatch):
    """El selector aplica ventas/consultar a fuentes de tipo nota de crédito."""
    _, client, _ = document_flow_app
    api_module = import_module("cacao_accounting.api")
    monkeypatch.setattr(
        api_module,
        "list_source_documents",
        lambda **_kwargs: [{"source_type": "sales_credit_note", "company": "cacao", "document_no": "NC-CACAO"}],
    )
    _login(client, "tesorero")
    response = client.get("/api/document-flow/source-documents?target_document_type=payment_entry&company=cacao")
    assert response.status_code == 200
    assert response.get_json()["source_documents"] == []


@pytest.mark.parametrize(
    ("path", "private_value"),
    [
        ("/sales/delivery-note/new?from_order={foreign_order}", "Cliente Confidencial"),
        ("/sales/sales-invoice/new?from_order={foreign_order}", "Cliente Confidencial"),
    ],
)
def test_sales_forms_reject_foreign_source_before_rendering(document_flow_app, path, private_value):
    """Los formularios de ventas no deben renderizar metadatos de una orden ajena."""
    _, client, ids = document_flow_app
    _login(client, "vendedor")
    response = client.get(path.format(**ids))
    assert response.status_code == 403
    assert private_value.encode() not in response.data


def test_source_document_picker_keeps_authorized_sales_sources(document_flow_app):
    """Control positivo: un vendedor con acceso a caja ve la orden propia elegible."""
    _, client, _ = document_flow_app
    _login(client, "vendedor")
    response = client.get("/api/document-flow/source-documents?target_document_type=payment_entry&company=cacao")
    assert response.status_code == 200
    rows = response.get_json()["source_documents"]
    assert any(row.get("source_type") == "sales_order" and row.get("document_no") == "SO-CACAO" for row in rows)


@pytest.mark.parametrize(
    ("username", "target_type", "source_type"),
    [
        ("ventas_solo", "sales_invoice", "delivery_note"),
        ("inventario_solo", "purchase_receipt", "purchase_order"),
    ],
)
def test_source_document_picker_matches_alternative_detail_acl(
    document_flow_app, monkeypatch, username, target_type, source_type
):
    """El selector acepta cada módulo alternativo autorizado para leer la fuente."""
    _, client, _ = document_flow_app
    api_module = import_module("cacao_accounting.api")
    monkeypatch.setattr(
        api_module,
        "list_source_documents",
        lambda **_kwargs: [{"source_type": source_type, "company": "cacao", "document_no": "DOC-AUTORIZADO"}],
    )
    _login(client, username)
    response = client.get(f"/api/document-flow/source-documents?target_document_type={target_type}&company=cacao")
    assert response.status_code == 200
    assert response.get_json()["source_documents"] == [
        {"source_type": source_type, "company": "cacao", "document_no": "DOC-AUTORIZADO"}
    ]


@pytest.mark.parametrize(
    ("username", "source_type", "target_type"),
    [("ventas_solo", "delivery_note", "sales_invoice"), ("inventario_solo", "purchase_order", "purchase_receipt")],
)
def test_pending_lines_accepts_alternative_read_module(document_flow_app, monkeypatch, username, source_type, target_type):
    """El lector de líneas pendientes respeta los módulos alternativos del documento."""
    _, client, _ = document_flow_app
    api_module = import_module("cacao_accounting.api")
    monkeypatch.setattr(api_module, "get_document", lambda *_args: SimpleNamespace(company="cacao"))
    monkeypatch.setattr(api_module, "get_pending_lines", lambda **_kwargs: [{"item_code": "ITEM-AUTORIZADO"}])
    _login(client, username)
    response = client.get(
        "/api/document-flow/pending-lines"
        f"?source_type={source_type}&target_type={target_type}&source_id=id-fuente&company=cacao"
    )
    assert response.status_code == 200
    assert response.get_json()["items"] == [{"item_code": "ITEM-AUTORIZADO"}]


def test_pending_lines_rejects_source_without_verifiable_company(document_flow_app, monkeypatch):
    """Una fuente histórica sin compañía no puede usar la compañía del query como permiso."""
    _, client, _ = document_flow_app
    api_module = import_module("cacao_accounting.api")
    monkeypatch.setattr(api_module, "get_document", lambda *_args: SimpleNamespace(company=None))
    monkeypatch.setattr(api_module, "get_pending_lines", lambda **_kwargs: pytest.fail("No debe leer las líneas"))
    _login(client, "vendedor")
    response = client.get(
        "/api/document-flow/pending-lines"
        "?source_type=sales_order&target_type=sales_invoice&source_id=legacy-id&company=cacao"
    )
    assert response.status_code == 403
    assert b"ITEM" not in response.data


def test_pending_lines_rejects_source_outside_requested_company(document_flow_app, monkeypatch):
    """La ruta aplica ACL a la compañía real de cada fuente antes de consultar líneas."""
    app, client, _ = document_flow_app
    api_module = import_module("cacao_accounting.api")
    monkeypatch.setattr(api_module, "get_document", lambda *_args: SimpleNamespace(company="cafe"))
    monkeypatch.setattr(api_module, "get_pending_lines", lambda **_kwargs: pytest.fail("No debe leer las líneas"))
    with app.app_context():
        database.session.add(UserCompanyAccess(user_id="vendedor", company_code="cafe"))
        database.session.commit()
    _login(client, "vendedor")
    response = client.get(
        "/api/document-flow/pending-lines"
        "?source_type=sales_order&target_type=sales_invoice&source_id=foreign-id&company=cacao"
    )
    assert response.status_code == 409
    assert b"ITEM" not in response.data
