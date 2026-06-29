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


def test_purchase_invoice_document_type_helper_prefers_sources_and_explicit_override(request):

    if request.config.getoption("--slow") == "True":

        from cacao_accounting.compras import (
            PURCHASE_CREDIT_NOTE,
            PURCHASE_INVOICE,
            PURCHASE_RETURN,
            _purchase_invoice_document_type,
        )

        source_ids = {"from_receipt_id": "REC-1", "from_invoice_id": None}
        with app.test_request_context("/buying/purchase-invoice/new"):
            assert _purchase_invoice_document_type(source_ids) == PURCHASE_RETURN

        source_ids = {"from_receipt_id": None, "from_invoice_id": "PINV-1"}
        with app.test_request_context("/buying/purchase-invoice/new"):
            assert _purchase_invoice_document_type(source_ids) == PURCHASE_CREDIT_NOTE

        source_ids = {"from_receipt_id": None, "from_invoice_id": None}
        with app.test_request_context("/buying/purchase-invoice/new"):
            assert _purchase_invoice_document_type(source_ids) == PURCHASE_INVOICE

        with app.test_request_context(
            "/buying/purchase-invoice/new",
            method="POST",
            data={"document_type": PURCHASE_CREDIT_NOTE},
        ):
            assert _purchase_invoice_document_type(source_ids) == PURCHASE_CREDIT_NOTE


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


def test_sales_order_initial_source_type_helper_prefers_request_then_quotation(request):

    if request.config.getoption("--slow") == "True":

        from cacao_accounting.ventas import _sales_order_initial_source_type

        assert _sales_order_initial_source_type("SR-1", None) == "sales_request"
        assert _sales_order_initial_source_type(None, "SQ-1") == "sales_quotation"
        assert _sales_order_initial_source_type(None, None) == ""
        assert _sales_order_initial_source_type("SR-1", "SQ-1") == "sales_request"


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


def test_setup_wizard_advances_between_steps(request, monkeypatch):

    if request.config.getoption("--slow") == "True":

        import cacao_accounting.setup as setup_module

        class _DummyField:
            def __init__(self, data):
                self.data = data

        class _DummyLanguageForm:
            idioma = _DummyField("en")

            def validate_on_submit(self):
                return True

        class _DummyRegionalForm:
            pais = _DummyField("NI")
            moneda = _DummyField("NIO")

            def validate_on_submit(self):
                return True

        class _DummyCompanyForm:
            id = _DummyField("C0001")
            razon_social = _DummyField("Cacao Test")
            nombre_comercial = _DummyField("Cacao Test")
            id_fiscal = _DummyField("J0001")
            tipo_entidad = _DummyField("company")
            inicio_anio_fiscal = _DummyField("2026-01-01")
            fin_anio_fiscal = _DummyField("2026-12-31")
            catalogo = _DummyField("en_cero")
            catalogo_origen = _DummyField("")

            def validate_on_submit(self):
                return True

        captured: dict[str, object] = {}

        monkeypatch.setattr(setup_module, "SetupLanguageForm", _DummyLanguageForm)
        monkeypatch.setattr(setup_module, "SetupRegionalForm", _DummyRegionalForm)
        monkeypatch.setattr(setup_module, "SetupCompanyForm", _DummyCompanyForm)
        monkeypatch.setattr(
            setup_module,
            "get_setup_configuration",
            lambda: {"idioma": "es", "pais": "NI", "moneda": "NIO"},
        )
        monkeypatch.setattr(setup_module, "available_currencies", lambda: [("NIO", "Córdoba")])
        monkeypatch.setattr(setup_module, "save_language", lambda language: captured.setdefault("language", language))
        monkeypatch.setattr(
            setup_module,
            "save_regional_settings",
            lambda country, currency: captured.setdefault("regional", (country, currency)),
        )
        monkeypatch.setattr(
            setup_module,
            "finalize_setup",
            lambda company_data, catalogo_tipo, country, idioma, catalogo_archivo: captured.setdefault(
                "finalize",
                {
                    "company_data": company_data,
                    "catalogo_tipo": catalogo_tipo,
                    "country": country,
                    "idioma": idioma,
                    "catalogo_archivo": catalogo_archivo,
                },
            ),
        )

        with app.test_client() as client:
            client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

            with client.session_transaction() as session_:
                session_["setup_step"] = 1

            response = client.post("/setup/", data={"idioma": "en"}, follow_redirects=False)
            assert response.status_code == 302
            with client.session_transaction() as session_:
                assert session_["setup_step"] == 2
            assert captured["language"] == "en"

            with client.session_transaction() as session_:
                session_["setup_step"] = 2

            response = client.post("/setup/", data={"pais": "NI", "moneda": "NIO"}, follow_redirects=False)
            assert response.status_code == 302
            with client.session_transaction() as session_:
                assert session_["setup_step"] == 3
            assert captured["regional"] == ("NI", "NIO")

            with client.session_transaction() as session_:
                session_["setup_step"] = 3

            response = client.post(
                "/setup/",
                data={
                    "id": "C0001",
                    "razon_social": "Cacao Test",
                    "nombre_comercial": "Cacao Test",
                    "id_fiscal": "J0001",
                    "tipo_entidad": "company",
                    "inicio_anio_fiscal": "2026-01-01",
                    "fin_anio_fiscal": "2026-12-31",
                    "catalogo": "en_cero",
                },
                follow_redirects=False,
            )
            assert response.status_code == 302
            with client.session_transaction() as session_:
                assert session_.get("setup_step") is None
            assert captured["finalize"]["catalogo_tipo"] == "en_cero"
            assert captured["finalize"]["country"] == "NI"
            assert captured["finalize"]["idioma"] == "es"


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


def test_buying_sales_and_cash_lists_support_search_filters(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            from cacao_accounting.database import (
                ComprobanteContable,
                PaymentEntry,
                PurchaseOrder,
                RecurringJournalTemplate,
                SalesOrder,
                database,
            )

            purchase_orders = [
                PurchaseOrder(
                    document_no=f"FILTER-PO-{index:02d}",
                    supplier_name="Proveedor Filtro",
                    company="cacao",
                    posting_date=date(2026, 6, 27),
                    docstatus=0,
                    grand_total=10,
                )
                for index in range(11)
            ]
            purchase_order_other = PurchaseOrder(
                document_no="OTHER-PO",
                supplier_name="Proveedor No Coincide",
                company="cacao",
                posting_date=date(2026, 6, 27),
                docstatus=1,
                grand_total=20,
            )
            sales_order = SalesOrder(
                document_no="FILTER-SO-01",
                customer_name="Cliente Filtro",
                company="cacao",
                posting_date=date(2026, 6, 27),
                docstatus=1,
                grand_total=30,
            )
            payment = PaymentEntry(
                document_no="FILTER-PAY-01",
                payment_type="receive",
                party_name="Cliente Filtro",
                company="cacao",
                posting_date=date(2026, 6, 27),
                docstatus=1,
                paid_amount=30,
            )
            journal = ComprobanteContable(
                document_no="FILTER-JE-01",
                entity="cacao",
                date=date(2026, 6, 27),
                reference="Referencia Filtro",
                status="draft",
            )
            recurring_journal = RecurringJournalTemplate(
                code="FILTER-REC-01",
                company="cacao",
                name="Plantilla Filtro",
                description="Descripcion Filtro",
                start_date=date(2026, 6, 27),
                end_date=date(2026, 12, 31),
                frequency="monthly",
                status="draft",
                docstatus=0,
            )
            database.session.add_all(
                [*purchase_orders, purchase_order_other, sales_order, payment, journal, recurring_journal]
            )
            database.session.commit()

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/buying/purchase-order/list?search=Proveedor+Filtro&status=draft")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert "Proveedor Filtro" in html
                assert "Proveedor No Coincide" not in html
                assert "search=Proveedor+Filtro" in html
                assert "status=draft" in html

                response = client.get("/sales/sales-order/list?search=Cliente+Filtro&status=submitted")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert "Cliente Filtro" in html
                assert "FILTER-SO-01" not in html

                response = client.get("/cash_management/payment/list?search=Cliente+Filtro&status=submitted")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert "Cliente Filtro" in html
                assert "receive" in html

                response = client.get("/accounting/journal/list?search=FILTER-JE&status=draft")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert "Buscar por documento" in html
                assert "FILTER-JE-01" in html
                assert "Referencia Filtro" in html
                assert 'value="FILTER-JE"' in html
                assert 'value="draft" selected' in html

                response = client.get("/accounting/journal/recurring?search=FILTER-REC")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert "Buscar por código" in html
                assert "FILTER-REC-01" in html
                assert "Plantilla Filtro" in html
                assert 'value="FILTER-REC"' in html

                response = client.get("/accounting/exchange-revaluation?search=cacao")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert "Buscar por número" in html
                assert 'value="cacao"' in html


def test_modules_and_imports_are_settings_links_not_primary_sidebar_items(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/settings")
                html = response.get_data(as_text=True)
                assert response.status_code == 200
                assert 'href="/settings/modules"' in html
                assert 'href="/imports/"' in html

                response = client.get("/accounting/")
                html = response.get_data(as_text=True)
                sidebar = html.split('<main class="ca-content">', maxsplit=1)[0]
                assert response.status_code == 200
                assert 'href="/settings/modules"' not in sidebar
                assert 'href="/imports/"' not in sidebar


def test_accounting_module_badges_are_semantic_for_admin(request):

    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                response = client.get("/accounting/")
                html = response.get_data(as_text=True)
                exchange_rates_row = html.split("Tasas de Cambio", maxsplit=1)[1].split("</li>", maxsplit=1)[0]
                assert response.status_code == 200
                assert 'data-status="ok"' in exchange_rates_row
                assert "ca-status-warning" not in exchange_rates_row
