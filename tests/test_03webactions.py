import pytest
import os
import sys

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
                assert "Nueva Solicitud de Compra" in response.get_data(as_text=True)

                response = client.get("/buying/supplier-quotation/list")
                assert response.status_code == 200
                assert "Listado de Cotizaciones de Proveedor" in response.get_data(as_text=True)

                response = client.get("/buying/supplier-quotation/new")
                assert response.status_code == 200
                assert "Nueva Cotización de Proveedor" in response.get_data(as_text=True)

                response = client.get("/buying/request-for-quotation/comparison")
                assert response.status_code == 200
                assert "Comparativo de Ofertas" in response.get_data(as_text=True)


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

                response = client.get("/sales/request-for-quotation/new")
                assert response.status_code == 200
                assert "Nueva Cotización" in response.get_data(as_text=True)
