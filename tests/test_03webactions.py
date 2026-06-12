import pytest
import os
import sys
from datetime import date
from html import unescape

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_func import init_test_db

from cacao_accounting import create_app

app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)


@pytest.fixture(scope="module", autouse=True)
def setupdb(request):
    if request.config.getoption("--slow") == "True":

        with app.app_context():

            init_test_db(app)


def test_check_passwd(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from cacao_accounting.auth import validar_acceso

            assert validar_acceso(usuario="cacao", clave="cacao") is True
            assert validar_acceso(usuario="cacao", clave="holis") is False
            assert validar_acceso(usuario="holis", clave="cacao") is False
            assert validar_acceso(usuario="holis", clave="holis") is False


def test_login_redirects_to_setup_on_initial_setup(request):

    if request.config.getoption("--slow") == "True":

        from cacao_accounting.database import CacaoConfig as Config, database

        with app.app_context():
            existing = database.session.execute(database.select(Config).filter_by(key="SETUP_COMPLETE")).first()
            original_value = None
            config = None
            if existing:
                config = existing[0]
                original_value = config.value
                config.value = "False"
            else:
                config = Config(key="SETUP_COMPLETE", value="False")
                database.session.add(config)
            database.session.commit()

            with app.test_client() as client:
                response = client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert response.status_code == 302
                assert response.headers["Location"].endswith("/setup") or response.headers["Location"].endswith("/setup/")

            if original_value is None:
                database.session.delete(config)
            else:
                config.value = original_value
            database.session.commit()


def test_setup_wizard_flow(request):

    if request.config.getoption("--slow") == "True":

        from cacao_accounting.database import CacaoConfig as Config, database

        with app.app_context():
            existing = database.session.execute(database.select(Config).filter_by(key="SETUP_COMPLETE")).first()
            original_value = None
            config = None
            if existing:
                config = existing[0]
                original_value = config.value
                config.value = "False"
            else:
                config = Config(key="SETUP_COMPLETE", value="False")
                database.session.add(config)
            database.session.commit()

            with app.test_client() as client:
                response = client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert response.status_code == 302
                assert response.headers["Location"].endswith("/setup") or response.headers["Location"].endswith("/setup/")

                get_response = client.get("/setup/")
                assert get_response.status_code == 200
                assert b"Idioma predeterminado" in get_response.data

            if original_value is None:
                database.session.delete(config)
            else:
                config.value = original_value
            database.session.commit()


def test_set_entity_inactive(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_inactive/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_set_entity_active(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_active/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_default_entity(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_default/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_delete_entity(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/delete/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_purchase_credit_note_list_route(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/buying/purchase-invoice/credit-note/list")
                assert response.status_code == 200
                assert "Listado de Notas de Crédito de Compra" in response.get_data(as_text=True)


def test_purchase_return_list_route(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/buying/purchase-invoice/return/list")
                assert response.status_code == 200
                assert "Listado de Devoluciones de Compra" in response.get_data(as_text=True)


def test_purchase_debit_note_list_route(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/buying/purchase-invoice/debit-note/list")
                assert response.status_code == 200
                assert "Listado de Notas de Débito de Compra" in response.get_data(as_text=True)


def test_sales_credit_note_list_route(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/sales/sales-invoice/return/list")
                assert response.status_code == 200
                assert "Listado de Notas de Crédito de Venta" in response.get_data(as_text=True)

                response = client.get("/sales/sales-invoice/debit-note/list")
                assert response.status_code == 200
                assert "Listado de Notas de Débito de Venta" in response.get_data(as_text=True)


def test_sales_request_routes(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/sales/sales-request/list")
                assert response.status_code == 200
                assert "Listado de Pedidos de Venta" in response.get_data(as_text=True)

                response = client.get("/sales/sales-request/new")
                assert response.status_code == 200
                assert "Nuevo Pedido de Venta" in response.get_data(as_text=True)


def test_purchase_quotation_routes(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/buying/request-for-quotation/list")
                assert response.status_code == 200
                assert "Listado de Solicitudes de Cotización" in response.get_data(as_text=True)

                response = client.get("/buying/request-for-quotation/new")
                assert response.status_code == 200
                assert "Nueva Solicitud de Cotización" in response.get_data(as_text=True)

                response = client.get("/buying/request-for-quotation/comparison")
                assert response.status_code == 200
                assert "Comparativo de Ofertas" in response.get_data(as_text=True)
                assert "Nueva Solicitud de Cotización" in response.get_data(as_text=True)


def test_purchase_request_and_supplier_quotation_routes(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/buying/purchase-request/list")
                assert response.status_code == 200
                assert "Listado de Solicitudes de Compra" in response.get_data(as_text=True)

                response = client.get("/buying/purchase-request/new")
                assert response.status_code == 200
                html = response.get_data(as_text=True)
                assert "Nueva Solicitud de Compra" in html
                assert 'x-if="activeIndex !== null && modalLine !== null"' in html
                assert "loadOnFilterChange: true" in html
                assert 'id="transaction_entity_type"' in html
                assert '"entity_type": {"selector": "#transaction_entity_type"}' in html
                assert 'requiredFilters: ["company", "entity_type"]' in html
                assert 'filters: { company: { selector: "#company" } }' in html
                assert 'requiredFilters: ["company"]' in html
                assert '@change="$dispatch' not in html
                assert "initialValue: modalLine.account" in html
                assert "initialValue: modalLine.cost_center" in html
                assert "initialValue: modalLine.unit" in html
                assert "initialValue: modalLine.project" in html

                from cacao_accounting.database import PurchaseRequest, database

                draft_request = PurchaseRequest(
                    document_no="TEST-PREQ-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                submitted_request = PurchaseRequest(
                    document_no="TEST-PREQ-SUBMITTED",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=1,
                    grand_total=0,
                )
                database.session.add_all([draft_request, submitted_request])
                database.session.commit()

                response = client.get(f"/buying/purchase-request/{draft_request.id}")
                assert response.status_code == 200
                html = response.get_data(as_text=True)
                assert "TEST-PREQ-DRAFT" in html
                assert "Solicitud de Compra" in html
                assert "Editar" in html
                assert "Duplicar" in html
                assert "Aprobar" in html
                assert "Listado" in html
                assert "Nuevo" in html
                assert "Crear" not in html

                response = client.get(f"/buying/purchase-request/{submitted_request.id}")
                assert response.status_code == 200
                html = response.get_data(as_text=True)
                assert "TEST-PREQ-SUBMITTED" in html
                assert "Crear" in html
                assert "Solicitud de Cotización" in html
                assert "Orden de Compra" in html
                assert "Anular" in html

                response = client.get("/buying/supplier-quotation/list")
                assert response.status_code == 200
                assert "Listado de Cotizaciones de Proveedor" in response.get_data(as_text=True)

                response = client.get("/buying/supplier-quotation/new")
                assert response.status_code == 200
                assert "Nueva Cotización de Proveedor" in response.get_data(as_text=True)

                response = client.get("/buying/request-for-quotation/comparison")
                assert response.status_code == 200
                assert "Comparativo de Ofertas" in response.get_data(as_text=True)


def test_transaccional_edit_duplicate_actions_routes(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            from cacao_accounting.database import (
                DeliveryNote,
                PurchaseInvoice,
                PurchaseOrder,
                PurchaseQuotation,
                PurchaseReceipt,
                SalesInvoice,
                SalesOrder,
                SalesQuotation,
                StockEntry,
                SupplierQuotation,
                database,
            )

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                purchase_quotation = PurchaseQuotation(
                    document_no="TEST-RFQ-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                supplier_quotation = SupplierQuotation(
                    document_no="TEST-SQ-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                purchase_order = PurchaseOrder(
                    document_no="TEST-PO-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                purchase_receipt = PurchaseReceipt(
                    document_no="TEST-PR-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                purchase_invoice = PurchaseInvoice(
                    document_no="TEST-PI-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    document_type="purchase_invoice",
                    docstatus=0,
                    grand_total=0,
                    outstanding_amount=0,
                )
                sales_quotation = SalesQuotation(
                    document_no="TEST-SQTN-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                sales_order = SalesOrder(
                    document_no="TEST-SO-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                delivery_note = DeliveryNote(
                    document_no="TEST-DN-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                sales_invoice = SalesInvoice(
                    document_no="TEST-SI-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    document_type="sales_invoice",
                    docstatus=0,
                    grand_total=0,
                    outstanding_amount=0,
                )
                stock_entry = StockEntry(
                    document_no="TEST-SE-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    purpose="material_receipt",
                    docstatus=0,
                    total_amount=0,
                )
                database.session.add_all(
                    [
                        purchase_quotation,
                        supplier_quotation,
                        purchase_order,
                        purchase_receipt,
                        purchase_invoice,
                        sales_quotation,
                        sales_order,
                        delivery_note,
                        sales_invoice,
                        stock_entry,
                    ]
                )
                database.session.commit()

                checks = [
                    (f"/buying/request-for-quotation/{purchase_quotation.id}", "Editar", "Duplicar"),
                    (f"/buying/supplier-quotation/{supplier_quotation.id}", "Editar", "Duplicar"),
                    (f"/buying/purchase-order/{purchase_order.id}", "Editar", "Duplicar"),
                    (f"/buying/purchase-receipt/{purchase_receipt.id}", "Editar", "Duplicar"),
                    (f"/buying/purchase-invoice/{purchase_invoice.id}", "Editar", "Duplicar"),
                    (f"/sales/quotation/{sales_quotation.id}", "Editar", "Duplicar"),
                    (f"/sales/sales-order/{sales_order.id}", "Editar", "Duplicar"),
                    (f"/sales/delivery-note/{delivery_note.id}", "Editar", "Duplicar"),
                    (f"/sales/sales-invoice/{sales_invoice.id}", "Editar", "Duplicar"),
                    (f"/inventory/stock-entry/{stock_entry.id}", "Editar", "Duplicar"),
                ]
                for url, expected_edit, expected_duplicate in checks:
                    response = client.get(url)
                    html = response.get_data(as_text=True)
                    assert response.status_code == 200
                    assert expected_edit in html
                    assert expected_duplicate in html

                edit_routes = [
                    f"/buying/request-for-quotation/{purchase_quotation.id}/edit",
                    f"/buying/supplier-quotation/{supplier_quotation.id}/edit",
                    f"/buying/purchase-order/{purchase_order.id}/edit",
                    f"/buying/purchase-receipt/{purchase_receipt.id}/edit",
                    f"/buying/purchase-invoice/{purchase_invoice.id}/edit",
                    f"/sales/sales-quotation/{sales_quotation.id}/edit",
                    f"/sales/sales-order/{sales_order.id}/edit",
                    f"/sales/delivery-note/{delivery_note.id}/edit",
                    f"/sales/sales-invoice/{sales_invoice.id}/edit",
                    f"/inventory/stock-entry/{stock_entry.id}/edit",
                ]
                for url in edit_routes:
                    response = client.get(url)
                    assert response.status_code == 200, url


def test_transaccional_full_transition_routes_get_post(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            from cacao_accounting.database import (
                DeliveryNote,
                PurchaseInvoice,
                PurchaseOrder,
                PurchaseQuotation,
                PurchaseReceipt,
                SalesInvoice,
                SalesOrder,
                SalesQuotation,
                SalesRequest,
                StockEntry,
                SupplierQuotation,
                database,
            )

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                purchase_quotation = PurchaseQuotation(
                    document_no="TEST2-RFQ-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                supplier_quotation = SupplierQuotation(
                    document_no="TEST2-SQ-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                purchase_order = PurchaseOrder(
                    document_no="TEST2-PO-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                purchase_receipt = PurchaseReceipt(
                    document_no="TEST2-PR-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                purchase_invoice = PurchaseInvoice(
                    document_no="TEST2-PI-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    document_type="purchase_invoice",
                    docstatus=0,
                    grand_total=0,
                    outstanding_amount=0,
                )
                sales_request = SalesRequest(
                    document_no="TEST2-SR-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                sales_quotation = SalesQuotation(
                    document_no="TEST2-SQTN-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                sales_order = SalesOrder(
                    document_no="TEST2-SO-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                delivery_note = DeliveryNote(
                    document_no="TEST2-DN-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    docstatus=0,
                    grand_total=0,
                )
                sales_invoice = SalesInvoice(
                    document_no="TEST2-SI-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    document_type="sales_invoice",
                    docstatus=0,
                    grand_total=0,
                    outstanding_amount=0,
                )
                stock_entry = StockEntry(
                    document_no="TEST2-SE-DRAFT",
                    company="cacao",
                    posting_date=date(2026, 5, 16),
                    purpose="material_receipt",
                    docstatus=0,
                    total_amount=0,
                )
                database.session.add_all(
                    [
                        purchase_quotation,
                        supplier_quotation,
                        purchase_order,
                        purchase_receipt,
                        purchase_invoice,
                        sales_request,
                        sales_quotation,
                        sales_order,
                        delivery_note,
                        sales_invoice,
                        stock_entry,
                    ]
                )
                database.session.commit()

                get_routes = [
                    f"/buying/request-for-quotation/{purchase_quotation.id}/edit",
                    f"/buying/supplier-quotation/{supplier_quotation.id}/edit",
                    f"/buying/purchase-order/{purchase_order.id}/edit",
                    f"/buying/purchase-receipt/{purchase_receipt.id}/edit",
                    f"/buying/purchase-invoice/{purchase_invoice.id}/edit",
                    f"/sales/sales-request/{sales_request.id}/edit",
                    f"/sales/sales-quotation/{sales_quotation.id}/edit",
                    f"/sales/sales-order/{sales_order.id}/edit",
                    f"/sales/delivery-note/{delivery_note.id}/edit",
                    f"/sales/sales-invoice/{sales_invoice.id}/edit",
                    f"/inventory/stock-entry/{stock_entry.id}/edit",
                ]
                for url in get_routes:
                    response = client.get(url)
                    assert response.status_code == 200, url

                edit_posts = [
                    (
                        f"/buying/request-for-quotation/{purchase_quotation.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/buying/supplier-quotation/{supplier_quotation.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/buying/purchase-order/{purchase_order.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/buying/purchase-receipt/{purchase_receipt.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/buying/purchase-invoice/{purchase_invoice.id}/edit",
                        {
                            "company": "cacao",
                            "posting_date": "2026-05-16",
                            "remarks": "edit",
                            "supplier_invoice_no": "SUP-001",
                        },
                    ),
                    (
                        f"/sales/sales-request/{sales_request.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/sales/sales-quotation/{sales_quotation.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/sales/sales-order/{sales_order.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/sales/delivery-note/{delivery_note.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/sales/sales-invoice/{sales_invoice.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "remarks": "edit"},
                    ),
                    (
                        f"/inventory/stock-entry/{stock_entry.id}/edit",
                        {"company": "cacao", "posting_date": "2026-05-16", "purpose": "material_receipt", "remarks": "edit"},
                    ),
                ]
                for url, payload in edit_posts:
                    response = client.post(url, data=payload)
                    assert response.status_code in (302, 303), url

                duplicate_posts = [
                    f"/buying/request-for-quotation/{purchase_quotation.id}/duplicate",
                    f"/buying/supplier-quotation/{supplier_quotation.id}/duplicate",
                    f"/buying/purchase-order/{purchase_order.id}/duplicate",
                    f"/buying/purchase-receipt/{purchase_receipt.id}/duplicate",
                    f"/buying/purchase-invoice/{purchase_invoice.id}/duplicate",
                    f"/sales/sales-request/{sales_request.id}/duplicate",
                    f"/sales/sales-quotation/{sales_quotation.id}/duplicate",
                    f"/sales/sales-order/{sales_order.id}/duplicate",
                    f"/sales/delivery-note/{delivery_note.id}/duplicate",
                    f"/sales/sales-invoice/{sales_invoice.id}/duplicate",
                    f"/inventory/stock-entry/{stock_entry.id}/duplicate",
                ]
                for url in duplicate_posts:
                    response = client.post(url, data={})
                    assert response.status_code in (302, 303), url

                strict_transition_docs = [
                    (
                        purchase_quotation,
                        f"/buying/request-for-quotation/{purchase_quotation.id}/submit",
                        f"/buying/request-for-quotation/{purchase_quotation.id}/cancel",
                    ),
                    (
                        supplier_quotation,
                        f"/buying/supplier-quotation/{supplier_quotation.id}/submit",
                        f"/buying/supplier-quotation/{supplier_quotation.id}/cancel",
                    ),
                    (
                        purchase_order,
                        f"/buying/purchase-order/{purchase_order.id}/submit",
                        f"/buying/purchase-order/{purchase_order.id}/cancel",
                    ),
                    (
                        sales_request,
                        f"/sales/sales-request/{sales_request.id}/submit",
                        f"/sales/sales-request/{sales_request.id}/cancel",
                    ),
                    (
                        sales_quotation,
                        f"/sales/sales-quotation/{sales_quotation.id}/submit",
                        f"/sales/sales-quotation/{sales_quotation.id}/cancel",
                    ),
                    (
                        sales_order,
                        f"/sales/sales-order/{sales_order.id}/submit",
                        f"/sales/sales-order/{sales_order.id}/cancel",
                    ),
                ]
                for model, submit_url, cancel_url in strict_transition_docs:
                    response = client.post(submit_url, data={})
                    assert response.status_code in (302, 303), submit_url
                    database.session.refresh(model)
                    assert model.docstatus == 1, submit_url

                    response = client.post(cancel_url, data={})
                    assert response.status_code in (302, 303), cancel_url
                    database.session.refresh(model)
                    assert model.docstatus == 2, cancel_url

                posting_transition_docs = [
                    (
                        purchase_receipt,
                        f"/buying/purchase-receipt/{purchase_receipt.id}/submit",
                        f"/buying/purchase-receipt/{purchase_receipt.id}/cancel",
                    ),
                    (
                        purchase_invoice,
                        f"/buying/purchase-invoice/{purchase_invoice.id}/submit",
                        f"/buying/purchase-invoice/{purchase_invoice.id}/cancel",
                    ),
                    (
                        delivery_note,
                        f"/sales/delivery-note/{delivery_note.id}/submit",
                        f"/sales/delivery-note/{delivery_note.id}/cancel",
                    ),
                    (
                        sales_invoice,
                        f"/sales/sales-invoice/{sales_invoice.id}/submit",
                        f"/sales/sales-invoice/{sales_invoice.id}/cancel",
                    ),
                    (
                        stock_entry,
                        f"/inventory/stock-entry/{stock_entry.id}/submit",
                        f"/inventory/stock-entry/{stock_entry.id}/cancel",
                    ),
                ]
                for model, submit_url, cancel_url in posting_transition_docs:
                    response = client.post(submit_url, data={})
                    assert response.status_code in (302, 303), submit_url
                    database.session.refresh(model)
                    assert model.docstatus in (0, 1), submit_url

                    if model.docstatus == 1:
                        response = client.post(cancel_url, data={})
                        assert response.status_code in (302, 303), cancel_url
                        database.session.refresh(model)
                        assert model.docstatus in (1, 2), cancel_url


def test_inventory_stock_entry_routes(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/inventory/stock-entry/material-receipt/list")
                assert response.status_code == 200
                assert "Listado de Recepciones de Material" in response.get_data(as_text=True)

                response = client.get("/inventory/stock-entry/material-issue/list")
                assert response.status_code == 200
                assert "Listado de Salidas de Material" in response.get_data(as_text=True)

                response = client.get("/inventory/stock-entry/material-transfer/list")
                assert response.status_code == 200
                assert "Listado de Transferencias de Material" in response.get_data(as_text=True)

                response = client.get("/inventory/stock-entry/new?purpose=material_issue")
                assert response.status_code == 200
                assert "Nueva Entrada de Almacén" in response.get_data(as_text=True)
                assert "Salidas de Material" not in response.get_data(as_text=True)

                response = client.get("/inventory/stock-entry/material-receipt/new")
                assert response.status_code == 200
                assert "Nueva Recepción de Material" in response.get_data(as_text=True)

                response = client.get("/buying/purchase-receipt/REC-DEMO-0000001")
                assert response.status_code == 200
                assert "Entrada de Almacén" in response.get_data(as_text=True)


def test_sales_quotation_routes(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/sales/quotation/list")
                assert response.status_code == 200
                assert "Listado de Cotizaciones de Venta" in response.get_data(as_text=True)

                response = client.get("/sales/request-for-quotation/list")
                assert response.status_code == 200
                assert "Listado de Cotizaciones de Venta" in response.get_data(as_text=True)

                response = client.get("/sales/quotation/new")
                assert response.status_code == 200
                assert "Nueva Cotización" in response.get_data(as_text=True)


def test_transaction_forms_render_unified_grid_and_detail_text(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                for url in [
                    "/buying/request-for-quotation/new",
                    "/buying/supplier-quotation/new",
                    "/buying/purchase-order/new",
                    "/buying/purchase-receipt/new",
                    "/buying/purchase-invoice/new",
                    "/sales/quotation/new",
                    "/sales/sales-order/new",
                    "/sales/delivery-note/new",
                    "/sales/sales-invoice/new",
                    "/inventory/stock-entry/new",
                ]:
                    response = client.get(url)
                    html = unescape(response.get_data(as_text=True))

                    assert response.status_code == 200
                    assert "column.field === 'item_code'" in html
                    assert "column.field === 'item_name'" in html
                    assert "column.field === 'uom'" in html
                    assert "column.field === 'rate'" in html
                    assert "column.field === 'amount'" in html
                    assert "Detalle de línea" in html

                for url in [
                    "/buying/purchase-order/POR-DEMO-0000001",
                    "/sales/sales-order/SOV-DEMO-0000001",
                    "/sales/delivery-note/ENT-DEMO-0000001",
                ]:
                    response = client.get(url)
                    html = response.get_data(as_text=True)

                    assert response.status_code == 200
                    assert "Detalle de línea seleccionada" in html
                    assert "Ver detalle" in html

                response = client.get("/sales/request-for-quotation/new")
                assert response.status_code == 200
                assert "Nueva Cotización" in response.get_data(as_text=True)
