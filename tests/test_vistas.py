import sys
import os
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__)))

import cacao_accounting
from z_static_routes import static_rutes


@pytest.fixture
def accounting_app():
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion

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


def test_visit_views(accounting_app, request):

    if request.config.getoption("--slow") == "True":

        from cacao_accounting.database import database
        from cacao_accounting.database.helpers import inicia_base_de_datos

        with accounting_app.app_context():
            from flask_login import current_user

            database.drop_all()
            inicia_base_de_datos(app=accounting_app, user="cacao", passwd="cacao")

            with accounting_app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                for ruta in static_rutes:
                    consulta = client.get(ruta.url)
                    assert consulta.status_code == 200
                    if ruta.text:
                        for text in ruta.text:
                            assert text in consulta.data

            client.get("/user/logout")
