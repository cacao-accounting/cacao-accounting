import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture
def accounting_app():

    app = create_app(configuracion)

    app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "DEBUG": True,
            "PRESERVE_CONTEXT_ON_EXCEPTION": True,
            "SQLALCHEMY_ECHO": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    yield app


@pytest.fixture(scope="module", autouse=True)
def setupdb(request):
    if request.config.getoption("--slow") == "True":

        app = create_app(configuracion)

        app.config.update(
            {
                "TESTING": True,
                "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "DEBUG": True,
                "PRESERVE_CONTEXT_ON_EXCEPTION": True,
                "SQLALCHEMY_ECHO": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
            }
        )

        with app.app_context():
            from cacao_accounting.database import database
            from cacao_accounting.database.helpers import inicia_base_de_datos

            database.drop_all()
            inicia_base_de_datos(app=app, user="cacao", passwd="cacao")


def test_set_entity_inactive(accounting_app, request):

    if request.config.getoption("--slow") == "True":

        with accounting_app.app_context():
            from flask_login import current_user

            with accounting_app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_inactive/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_set_entity_active(accounting_app, request):

    if request.config.getoption("--slow") == "True":

        with accounting_app.app_context():
            from flask_login import current_user

            with accounting_app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_active/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_default_entity(accounting_app, request):

    if request.config.getoption("--slow") == "True":

        with accounting_app.app_context():
            from flask_login import current_user

            with accounting_app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/set_default/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)


def test_delete_entity(accounting_app, request):

    if request.config.getoption("--slow") == "True":

        with accounting_app.app_context():
            from flask_login import current_user

            with accounting_app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                client.get("/accounts/entity/delete/01J092PXHEBF4M129A7GZZ48E2", follow_redirects=True)
