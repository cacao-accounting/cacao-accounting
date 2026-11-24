"""El alta de recepción respeta el alcance de compañía del documento origen."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    DocumentRelation,
    Entity,
    FiscalYear,
    Item,
    Modules,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)


@pytest.fixture
def receipt_source_scenario():
    """Build two companies and a warehouse user authorized only for Alpha."""
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
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J-ALPHA",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J-BETA",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="receipt_user",
                    user="receipt_user",
                    name="Bodeguero Alpha",
                    password=proteger_passwd("receipt-user-password"),
                    active=True,
                ),
                User(
                    id="buyer_user",
                    user="buyer_user",
                    name="Compras Alpha",
                    password=proteger_passwd("buyer-user-password"),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id="receipt_user", company_code="alpha"),
                UserCompanyAccess(user_id="buyer_user", company_code="alpha"),
                PurchaseOrder(
                    company="alpha",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-ALPHA",
                    supplier_name="Proveedor Alpha",
                    transaction_currency="NIO",
                    base_currency="NIO",
                ),
                PurchaseOrder(
                    company="beta",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                    transaction_currency="NIO",
                    base_currency="NIO",
                ),
                PurchaseReceipt(
                    company="beta",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PR-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                    transaction_currency="NIO",
                    base_currency="NIO",
                ),
                PurchaseReceipt(
                    company="alpha",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PR-ALPHA",
                    supplier_name="Proveedor Alpha",
                    transaction_currency="NIO",
                    base_currency="NIO",
                ),
                Warehouse(code="ALPHA-WH", name="Bodega Alpha", company="alpha"),
                Warehouse(code="BETA-WH", name="Bodega Confidencial Beta", company="beta"),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("receipt_user", "inventory_auxiliar")
        asigna_rol_a_usuario("buyer_user", "inventory_auxiliar")
        asigna_rol_a_usuario("buyer_user", "purchasing_manager")
        database.session.commit()
        order_alpha_id = database.session.query(PurchaseOrder.id).filter_by(company="alpha").scalar()
        receipt_alpha_id = database.session.query(PurchaseReceipt.id).filter_by(document_no="PR-ALPHA").scalar()
        database.session.add(UOM(code="RECEIPT-UND", name="Unidad de recepción"))
        database.session.flush()
        database.session.add(
            Item(
                code="RECEIPT-ITEM",
                name="Artículo de recepción",
                item_type="goods",
                is_stock_item=True,
                default_uom="RECEIPT-UND",
            )
        )
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order_alpha_id,
                item_code="RECEIPT-ITEM",
                item_name="Artículo de recepción",
                qty=5,
                qty_in_base_uom=5,
                uom="RECEIPT-UND",
                rate=125,
                amount=625,
            )
        )
        database.session.flush()
        order_item_id = database.session.query(PurchaseOrderItem.id).filter_by(purchase_order_id=order_alpha_id).scalar()
        other_receipt = PurchaseReceipt(
            company="alpha",
            posting_date=date(2026, 10, 20),
            docstatus=1,
            document_no="PR-ALPHA-OTHER",
            supplier_name="Proveedor Alpha",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(other_receipt)
        database.session.flush()
        other_receipt_item = PurchaseReceiptItem(
            purchase_receipt_id=other_receipt.id,
            item_code="RECEIPT-ITEM",
            item_name="Artículo de recepción",
            qty=2,
            qty_in_base_uom=2,
            uom="RECEIPT-UND",
            rate=999,
            amount=1998,
            warehouse="ALPHA-WH",
        )
        database.session.add(other_receipt_item)
        database.session.flush()
        receipt_item = PurchaseReceiptItem(
            purchase_receipt_id=receipt_alpha_id,
            item_code="RECEIPT-ITEM",
            item_name="Artículo de recepción",
            qty=2,
            qty_in_base_uom=2,
            uom="RECEIPT-UND",
            rate=75,
            amount=150,
            warehouse="ALPHA-WH",
        )
        database.session.add(receipt_item)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_receipt",
                source_id=receipt_alpha_id,
                target_type="purchase_order",
                target_id=order_alpha_id,
                company="alpha",
                qty=1,
                relation_type="purchase_receipt",
            )
        )
        database.session.commit()
        ids = {
            "order_alpha": order_alpha_id,
            "order_alpha_item": order_item_id,
            "receipt_alpha_item": receipt_item.id,
            "other_receipt": other_receipt.id,
            "other_receipt_item": other_receipt_item.id,
            "order_beta": database.session.query(PurchaseOrder.id).filter_by(company="beta").scalar(),
            "receipt_alpha": receipt_alpha_id,
            "receipt_beta": database.session.query(PurchaseReceipt.id).filter_by(company="beta").scalar(),
        }
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, username="receipt_user"):
    """Return an authenticated client for an Alpha-only workflow user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = username
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(("source_key", "query_field"), [("order_beta", "from_order"), ("receipt_beta", "from_receipt")])
def test_recepcion_no_expone_origen_de_otra_compania(receipt_source_scenario, source_key, query_field):
    """Foreign source IDs cannot reveal supplier or company data in the new form."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app).get(f"/buying/purchase-receipt/new?{query_field}={ids[source_key]}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "Proveedor Confidencial Beta" not in body
    assert "PO-BETA" not in body
    assert "PR-BETA" not in body


def test_recepcion_precarga_origen_de_compania_autorizada(receipt_source_scenario):
    """An authorized source remains available to the receipt workflow."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app).get(f"/buying/purchase-receipt/new?from_order={ids['order_alpha']}")

    assert response.status_code == 200
    assert "Proveedor Alpha" in response.get_data(as_text=True)


def _receipt_form_config(response) -> dict:
    """Extract the serialized Alpine configuration from a receipt form."""
    body = response.get_data(as_text=True)
    start = body.index("transactionForm(") + len("transactionForm(")
    return json.loads(body[start : body.index(")'", start)])


def _create_receipt_accounting_period(app) -> None:
    """Create the open Alpha accounting period used by receipt POST scenarios."""
    with app.app_context():
        database.session.add(
            FiscalYear(
                id="FY-ALPHA-2026",
                entity="alpha",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity="alpha",
                fiscal_year_id="FY-ALPHA-2026",
                name="Octubre 2026",
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
                enabled=True,
                is_closed=False,
            )
        )
        database.session.commit()


def test_recepcion_de_orden_oculta_precios_al_perfil_de_inventario(receipt_source_scenario):
    """The receipt form hides order prices from inventory-only users."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app).get(f"/buying/purchase-receipt/new?from_order={ids['order_alpha']}")

    assert response.status_code == 200
    assert _receipt_form_config(response)["showPricing"] is False


def test_devolucion_recepcion_oculta_precios_al_perfil_de_inventario(receipt_source_scenario):
    """The return form also hides the original receipt pricing from Inventory-only users."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app).get(f"/buying/purchase-receipt/new?from_receipt={ids['receipt_alpha']}")

    assert response.status_code == 200
    config = _receipt_form_config(response)
    assert config["showPricing"] is False
    assert "purchase_receipt" in config["hidePricingForSourceTypes"]


def test_recepcion_de_orden_conserva_precios_para_compras(receipt_source_scenario):
    """A purchaser with company access retains pricing in the receipt form."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app, "buyer_user").get(f"/buying/purchase-receipt/new?from_order={ids['order_alpha']}")

    assert response.status_code == 200
    assert _receipt_form_config(response)["showPricing"] is True


def test_recepcion_manual_permite_precios_y_configura_ocultamiento_al_seleccionar_orden(receipt_source_scenario):
    """Manual pricing remains available; selecting a PO hides it for Inventory-only users."""
    app, _ = receipt_source_scenario
    response = _authenticated_client(app).get("/buying/purchase-receipt/new?company=alpha")

    assert response.status_code == 200
    config = _receipt_form_config(response)
    assert config["showPricing"] is True
    assert config["showPricingForManual"] is True
    assert config["hidePricingForSourceTypes"] == ["purchase_order", "purchase_receipt"]
    assert config["sourcePricingFromApi"] is True


def test_edicion_de_recepcion_manual_conserva_su_valoracion(receipt_source_scenario):
    """An unlinked manual draft retains its editable, user-entered pricing."""
    app, _ = receipt_source_scenario
    with app.app_context():
        receipt = PurchaseReceipt(
            company="alpha",
            posting_date=date(2026, 10, 20),
            docstatus=0,
            document_no="PR-MANUAL-DRAFT",
            supplier_name="Proveedor Alpha",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(receipt)
        database.session.flush()
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code="RECEIPT-ITEM",
                item_name="Artículo de recepción",
                qty=2,
                qty_in_base_uom=2,
                uom="RECEIPT-UND",
                rate=45,
                amount=90,
                warehouse="ALPHA-WH",
            )
        )
        database.session.commit()
        receipt_id = receipt.id

    response = _authenticated_client(app).get(f"/buying/purchase-receipt/{receipt_id}/edit")

    assert response.status_code == 200
    config = _receipt_form_config(response)
    assert config["showPricing"] is True
    assert Decimal(config["initialLines"][0]["rate"]) == Decimal("45")
    assert Decimal(config["initialLines"][0]["amount"]) == Decimal("90")


def test_edicion_de_recepcion_del_selector_oculta_y_resuelve_tarifa(receipt_source_scenario):
    """A relation-only PO receipt stays private and keeps its PO rate on edit."""
    app, ids = receipt_source_scenario
    with app.app_context():
        receipt = PurchaseReceipt(
            company="alpha",
            posting_date=date(2026, 10, 20),
            docstatus=0,
            document_no="PR-SELECTOR-DRAFT",
            supplier_name="Proveedor Alpha",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(receipt)
        database.session.flush()
        receipt_line = PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="RECEIPT-ITEM",
            item_name="Artículo de recepción",
            qty=2,
            qty_in_base_uom=2,
            uom="RECEIPT-UND",
            rate=125,
            amount=250,
            warehouse="ALPHA-WH",
        )
        database.session.add(receipt_line)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_order",
                source_id=ids["order_alpha"],
                source_item_id=ids["order_alpha_item"],
                target_type="purchase_receipt",
                target_id=receipt.id,
                target_item_id=receipt_line.id,
                company="alpha",
                qty=2,
                qty_in_base_uom=2,
                uom="RECEIPT-UND",
                rate=125,
                amount=250,
                relation_type="receipt",
            )
        )
        database.session.commit()
        receipt_id = receipt.id

    client = _authenticated_client(app)
    response = client.get(f"/buying/purchase-receipt/{receipt_id}/edit")

    assert response.status_code == 200
    config = _receipt_form_config(response)
    assert config["showPricing"] is False
    line = config["initialLines"][0]
    assert "rate" not in line
    assert "amount" not in line
    assert line["source_id"] == ids["order_alpha"]

    edit_response = client.post(
        f"/buying/purchase-receipt/{receipt_id}/edit",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "item_code_0": "RECEIPT-ITEM",
            "item_name_0": "Artículo de recepción",
            "qty_0": "2",
            "uom_0": "RECEIPT-UND",
            "rate_0": "0",
            "amount_0": "0",
            "source_type_0": "purchase_order",
            "source_id_0": ids["order_alpha"],
            "source_item_id_0": ids["order_alpha_item"],
        },
    )

    assert edit_response.status_code == 302
    with app.app_context():
        active_line = database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id, is_superseded=False)
        ).scalar_one()
        assert active_line.rate == 125
        assert active_line.amount == 250


def test_recepcion_no_carga_catalogo_de_compania_no_autorizada(receipt_source_scenario):
    """An explicit foreign company cannot expose its warehouse catalog without a source."""
    app, _ = receipt_source_scenario
    response = _authenticated_client(app).get("/buying/purchase-receipt/new?company=beta")

    assert response.status_code == 403
    assert "Bodega Confidencial Beta" not in response.get_data(as_text=True)


def test_recepcion_carga_lineas_con_permiso_de_inventario(receipt_source_scenario):
    """Inventory-only users can request pending lines of a purchase order (#1332)."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)

    response = client.get(
        "/api/document-flow/pending-lines",
        query_string={
            "source_type": "purchase_order",
            "target_type": "purchase_receipt",
            "source_document_ids[]": ids["order_alpha"],
            "company": "alpha",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["target_type"] == "purchase_receipt"
    assert response.get_json()["pricing_redacted"] is True
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["item_code"] == "RECEIPT-ITEM"
    assert items[0]["pending_qty"] == "5.000000000"
    assert "rate" not in items[0]
    assert "amount" not in items[0]


def test_recepcion_mantiene_precios_en_api_para_usuario_de_compras(receipt_source_scenario):
    """A purchase reader receives the original pricing fields."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app, "buyer_user")

    response = client.get(
        "/api/document-flow/pending-lines",
        query_string={
            "source_type": "purchase_order",
            "target_type": "purchase_receipt",
            "source_document_ids[]": ids["order_alpha"],
            "company": "alpha",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["pricing_redacted"] is False
    item = response.get_json()["items"][0]
    assert Decimal(item["rate"]) == Decimal("125")
    assert Decimal(item["amount"]) == Decimal("625")


def test_devolucion_carga_lineas_sin_precios_para_inventario(receipt_source_scenario):
    """Inventory can load return lines without receiving source prices."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)

    response = client.get(
        "/api/document-flow/pending-lines",
        query_string={
            "source_type": "purchase_receipt",
            "target_type": "purchase_receipt",
            "source_document_ids[]": ids["receipt_alpha"],
            "company": "alpha",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["pricing_redacted"] is True
    item = response.get_json()["items"][0]
    assert item["source_item_id"] == ids["receipt_alpha_item"]
    assert item["pending_qty"] == "2.000000000"
    assert "rate" not in item
    assert "amount" not in item


def test_devolucion_conserva_precios_en_api_para_usuario_de_compras(receipt_source_scenario):
    """Purchase readers still receive full source data for return workflow."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app, "buyer_user")

    response = client.get(
        "/api/document-flow/pending-lines",
        query_string={
            "source_type": "purchase_receipt",
            "target_type": "purchase_receipt",
            "source_document_ids[]": ids["receipt_alpha"],
            "company": "alpha",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["pricing_redacted"] is False
    item = response.get_json()["items"][0]
    assert Decimal(item["rate"]) == Decimal("75")
    assert Decimal(item["amount"]) == Decimal("150")


def test_recepcion_rechaza_lineas_de_orden_ajena(receipt_source_scenario):
    """The same endpoint keeps denying a foreign source document."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)

    response = client.get(
        "/api/document-flow/pending-lines",
        query_string={
            "source_type": "purchase_order",
            "target_type": "purchase_receipt",
            "source_document_ids[]": ids["order_beta"],
            "company": "beta",
        },
    )

    assert response.status_code == 403


def test_recepcion_post_usa_el_permiso_de_inventario(receipt_source_scenario):
    """The receipt POST does not demand purchases.create from an inventory user (#1332)."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)

    response = client.post(
        "/buying/purchase-receipt/new",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "from_order": ids["order_alpha"],
        },
    )

    assert response.status_code == 200


def test_recepcion_desde_orden_resuelve_tarifa_en_servidor(receipt_source_scenario):
    """A hidden or tampered form rate cannot change the linked PO valuation."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)
    _create_receipt_accounting_period(app)
    response = client.post(
        "/buying/purchase-receipt/new",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "from_order": ids["order_alpha"],
            "to_warehouse": "ALPHA-WH",
            "item_code_0": "RECEIPT-ITEM",
            "item_name_0": "Artículo de recepción",
            "qty_0": "2",
            "uom_0": "RECEIPT-UND",
            "rate_0": "0",
            "amount_0": "0",
            "source_type_0": "purchase_order",
            "source_id_0": ids["order_alpha"],
            "source_item_id_0": ids["order_alpha_item"],
        },
    )

    assert response.status_code == 302
    with app.app_context():
        receipt = database.session.query(PurchaseReceipt).filter_by(purchase_order_id=ids["order_alpha"]).one()
        line = database.session.query(PurchaseOrderItem).filter_by(id=ids["order_alpha_item"]).one()
        receipt_line = database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id)
        ).scalar_one()
        assert receipt_line.rate == line.rate == 125
        assert receipt_line.amount == 250
        receipt_id = receipt.id

    edit_response = client.get(f"/buying/purchase-receipt/{receipt_id}/edit")
    assert edit_response.status_code == 200
    edit_line = _receipt_form_config(edit_response)["initialLines"][0]
    assert "rate" not in edit_line
    assert "amount" not in edit_line
    assert edit_line["source_id"] == ids["order_alpha"]


def test_devolucion_desde_recepcion_resuelve_tarifa_en_servidor(receipt_source_scenario):
    """A hidden or tampered return rate is resolved from its original receipt line."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)
    _create_receipt_accounting_period(app)

    response = client.post(
        "/buying/purchase-receipt/new",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "from_receipt": ids["receipt_alpha"],
            "to_warehouse": "ALPHA-WH",
            "item_code_0": "RECEIPT-ITEM",
            "item_name_0": "Artículo de recepción",
            "qty_0": "1",
            "uom_0": "RECEIPT-UND",
            "rate_0": "0",
            "amount_0": "0",
            "source_type_0": "purchase_receipt",
            "source_id_0": ids["receipt_alpha"],
            "source_item_id_0": ids["receipt_alpha_item"],
        },
    )

    assert response.status_code == 302
    with app.app_context():
        receipt = database.session.query(PurchaseReceipt).filter_by(reversal_of=ids["receipt_alpha"]).one()
        receipt_line = database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id)
        ).scalar_one()
        assert receipt_line.rate == 75
        assert receipt_line.amount == 75
        receipt_id = receipt.id
        original_line_id = receipt_line.id

    edit_response = client.get(f"/buying/purchase-receipt/{receipt_id}/edit")
    assert edit_response.status_code == 200
    edit_config = _receipt_form_config(edit_response)
    assert edit_config["showPricing"] is False
    edit_line = edit_config["initialLines"][0]
    assert "rate" not in edit_line
    assert "amount" not in edit_line
    assert edit_line["source_type"] == "purchase_receipt"
    assert edit_line["source_id"] == ids["receipt_alpha"]
    assert edit_line["source_item_id"] == ids["receipt_alpha_item"]

    edit_post = client.post(
        f"/buying/purchase-receipt/{receipt_id}/edit",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "to_warehouse": "ALPHA-WH",
            "item_code_0": "RECEIPT-ITEM",
            "item_name_0": "Artículo de recepción",
            "qty_0": "1",
            "uom_0": "RECEIPT-UND",
            "rate_0": "0",
            "amount_0": "0",
            "source_type_0": "purchase_receipt",
            "source_id_0": ids["receipt_alpha"],
            "source_item_id_0": ids["receipt_alpha_item"],
        },
    )
    assert edit_post.status_code == 302
    with app.app_context():
        original_line = database.session.get(PurchaseReceiptItem, original_line_id)
        edited_line = database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id, is_superseded=False)
        ).scalar_one()
        assert original_line.is_superseded is True
        assert edited_line.rate == 75
        assert edited_line.amount == 75


@pytest.mark.parametrize(
    ("source_type", "source_id_key", "source_item_key"),
    [
        ("purchase_receipt", "other_receipt", "other_receipt_item"),
        ("purchase_order", "order_alpha", "order_alpha_item"),
    ],
)
def test_devolucion_rechaza_origen_que_no_es_la_recepcion_original(
    receipt_source_scenario, source_type, source_id_key, source_item_key
):
    """A return cannot take its rate from any source except its original receipt."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)
    _create_receipt_accounting_period(app)

    response = client.post(
        "/buying/purchase-receipt/new",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "from_receipt": ids["receipt_alpha"],
            "to_warehouse": "ALPHA-WH",
            "item_code_0": "RECEIPT-ITEM",
            "item_name_0": "Artículo de recepción",
            "qty_0": "1",
            "uom_0": "RECEIPT-UND",
            "rate_0": "999",
            "amount_0": "999",
            "source_type_0": source_type,
            "source_id_0": ids[source_id_key],
            "source_item_id_0": ids[source_item_key],
        },
    )

    assert response.status_code == 200
    with app.app_context():
        assert database.session.query(PurchaseReceipt).filter_by(reversal_of=ids["receipt_alpha"]).count() == 0


def test_lista_relacionada_respeta_el_acceso_de_inventario(receipt_source_scenario):
    """A warehouse user sees related purchase orders despite lacking Purchases (#1411)."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)

    response = client.get(
        "/document-flow/list/purchase_order",
        query_string={
            "doctype": "purchase_order",
            "related_doctype": "purchase_receipt",
            "related_id": ids["receipt_alpha"],
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "PO-ALPHA" in body
    assert "PO-BETA" not in body
    assert "PR-BETA" not in body


def test_recepcion_rechaza_orden_y_recepcion_incompatibles(receipt_source_scenario):
    """No se mezcla una orden distinta con la recepción de origen (#2148)."""
    app, ids = receipt_source_scenario
    with app.app_context():
        order_alt = PurchaseOrder(
            company="alpha",
            posting_date=date(2026, 10, 20),
            docstatus=1,
            document_no="PO-ALPHA-ALT",
            supplier_name="Proveedor Alpha",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(order_alt)
        database.session.commit()
        order_alt_id = order_alt.id

    response = _authenticated_client(app).get(
        f"/buying/purchase-receipt/new?from_order={order_alt_id}&from_receipt={ids['receipt_alpha']}"
    )

    assert response.status_code == 400


def test_post_recepcion_rechaza_fuentes_incompatibles_sin_persistir(receipt_source_scenario):
    """Reject an incompatible return source pair before creating a draft (#2148)."""
    app, ids = receipt_source_scenario
    client = _authenticated_client(app)
    with app.app_context():
        before_count = database.session.query(PurchaseReceipt).count()

    response = client.post(
        "/buying/purchase-receipt/new",
        data={
            "company": "alpha",
            "posting_date": "2026-10-20",
            "from_order": ids["order_alpha"],
            "from_receipt": ids["receipt_alpha"],
            "to_warehouse": "ALPHA-WH",
            "item_code_0": "RECEIPT-ITEM",
            "item_name_0": "Artículo de recepción",
            "qty_0": "1",
            "uom_0": "RECEIPT-UND",
            "rate_0": "1",
            "amount_0": "1",
        },
    )

    assert response.status_code == 400
    with app.app_context():
        assert database.session.query(PurchaseReceipt).count() == before_count


def test_recepcion_usa_una_sola_fuente_cuando_orden_y_recepcion_coinciden(receipt_source_scenario):
    """La devolución precarga desde la recepción, no desde la orden (#2148)."""
    app, ids = receipt_source_scenario
    with app.app_context():
        receipt = database.session.get(PurchaseReceipt, ids["receipt_alpha"])
        receipt.purchase_order_id = ids["order_alpha"]
        database.session.commit()

    response = _authenticated_client(app).get(
        f"/buying/purchase-receipt/new?from_order={ids['order_alpha']}&from_receipt={ids['receipt_alpha']}"
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="from_order"' not in html
    assert 'name="from_receipt"' in html
    assert 'name="is_return"' in html
    assert "source_type=purchase_order" not in html
