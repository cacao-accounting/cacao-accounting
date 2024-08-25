import sys
import os
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_static_routes import static_rutes
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


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_visit_views(request):
    from cacao_accounting.logs import log

    if request.config.getoption("--slow") == "True" or os.environ.get("CACAO_TEST"):

        with app.app_context():
            from flask_login import current_user

            init_test_db(app)

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
