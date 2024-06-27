import sys
import os
import pytest

from flask import session

from cacao_accounting.logs import log

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_forms_data import forms


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


def test_fill_all_forms(accounting_app, request):

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

                for form in forms:
                    consulta = client.get(form.ruta)
                    assert consulta.status_code == 200

                    log.warning(form.ruta)

                    if form.file:
                        data = {key: str(value) for key, value in form.data.items()}
                        data[form.file.get("name")] = form.file.get("bytes")
                        consulta = client.post(form.ruta, data=data, follow_redirects=True, content_type="multipart/form-data")
                    else:
                        consulta = client.post(form.ruta, data=form.data, follow_redirects=True)

                    if form.flash:
                        assert session["_flashes"][0][0] == form.flash[1]
                        assert session["_flashes"][0][1] == form.flash[0]

                    client.get("/user/logout")
