import pytest
import os, sys

from cacao_accounting.datos.dev import data

sys.path.append(os.path.join(os.path.dirname(__file__)))

from cacao_accounting import create_app
from cacao_accounting.config import DIRECTORIO_PRINCICIPAL

if os.name == "nt":
    SQLITE = "sqlite:///" + str(DIRECTORIO_PRINCICIPAL) + "\\db_test_acciones.db"
else:
    SQLITE = "sqlite:///" + str(DIRECTORIO_PRINCICIPAL) + "/db_test_acciones.db"


app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }
)


@pytest.fixture(scope="module", autouse=True)
def setupdb(request):
    if request.config.getoption("--slow") == "True":

        with app.app_context():
            from cacao_accounting.database import database
            from cacao_accounting.database.helpers import inicia_base_de_datos

            database.drop_all()
            inicia_base_de_datos(app=app, user="cacao", passwd="cacao", with_examples=True)


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_set_entity_inactive(request):

    if request.config.getoption("--slow") == "True" or os.environ.get("CACAO_TEST"):

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_inactive/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_set_entity_active(request):

    if request.config.getoption("--slow") == "True" or os.environ.get("CACAO_TEST"):

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_active/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_default_entity(request):

    if request.config.getoption("--slow") == "True" or os.environ.get("CACAO_TEST"):

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_default/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_delete_entity(request):

    if request.config.getoption("--slow") == "True" or os.environ.get("CACAO_TEST"):

        with app.app_context():
            from flask_login import current_user

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/delete/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)
