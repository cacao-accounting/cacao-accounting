import sys
import os
import pytest

from flask import session

from cacao_accounting.logs import log

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_forms_data import forms

from cacao_accounting import create_app
from cacao_accounting.config import DIRECTORIO_PRINCICIPAL


if os.name == "nt":
    SQLITE = "sqlite:///" + str(DIRECTORIO_PRINCICIPAL) + "\\db_test_forms.db"
else:
    SQLITE = "sqlite:///" + str(DIRECTORIO_PRINCICIPAL) + "db_test_forms.db"

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


@pytest.mark.skipif(os.environ.get("CACAO_TEST") is None, reason="Set env to testing.")
def test_fill_all_forms(request):

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

                for form in forms:

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
            database.drop_all()
