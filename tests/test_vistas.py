import sys
import os
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_app import app
from z_static_routes import static_rutes


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_visit_views(request):
    from cacao_accounting.logs import log

    if request.config.getoption("--slow") == "True" or os.environ.get("CACAO_TEST"):

        from cacao_accounting.database import database
        from cacao_accounting.database.helpers import inicia_base_de_datos

        with app.app_context():
            from flask_login import current_user

            database.drop_all()
            inicia_base_de_datos(app=app, user="cacao", passwd="cacao", with_examples=True)

            with app.test_client() as client:
                # Keep the session alive until the with clausule closes

                client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
                assert current_user.is_authenticated

                for ruta in static_rutes:
                    log.warning(ruta.url)
                    consulta = client.get(ruta.url)

                    assert consulta.status_code == 200
                    if ruta.text:
                        for text in ruta.text:
                            assert text in consulta.data

            client.get("/user/logout")
