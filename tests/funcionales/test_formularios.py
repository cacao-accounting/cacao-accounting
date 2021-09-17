# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes

# pylint: disable=redefined-outer-name
import pytest
from cacao_accounting import create_app as app_factory
from cacao_accounting.database import database
from cacao_accounting.datos import base_data, dev_data


@pytest.fixture(scope="module", autouse=True)
def app():
    from cacao_accounting.config import SQLITE

    app = app_factory(
        {
            "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
            "SQLALCHEMY_DATABASE_URI": SQLITE,
            # "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DEBUG": True,
            "DESKTOPMODE": False,
        }
    )
    with app.app_context():
        database.drop_all()
        database.create_all()
        base_data()
        dev_data()
    app.app_context().push()
    yield app


@pytest.fixture
def elimina_variable_entorno(app):
    import os

    if os.environ.get("CACAO_TEST"):
        os.environ.pop("CACAO_TEST")
        app.config["ENV"] = "production"
    else:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self):
        return self._client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

    def logout(self):
        return self._client.get("/salir")


@pytest.fixture
def auth(client):
    return AuthActions(client)


def test_formulario_nueva_entidad(client, auth):
    from cacao_accounting.database import Entidad

    auth.login()
    response = client.get("/accounts/entity/new")
    assert b"Crear Nueva Entidad." in response.data
    entidad = Entidad.query.filter_by(entidad="Test Form").first()
    assert entidad is None
    post = client.post(
        "/accounts/entity/new",
        data={
            "nombre_comercial": "Test Form",
            "razon_social": "Test Form",
            "id_fiscal": "Test Form",
            "id": "Test Form",
            "moneda": "NIO",
            "tipo_entidad": "Asociación",
            "correo_electronico": "test@cacao.io",
            "web": "https://cacao.io",
            "telefono1": "+505 8771 0980",
            "telefono2": "+505 8661 2108",
            "fax": "+505 2273 0754",
        },
        follow_redirects=True,
    )
    entidad = Entidad.query.filter_by(entidad="Test Form").first()
    assert entidad is not None
    assert entidad.moneda == "NIO"
    assert entidad.entidad == "Test Form"


def test_formulario_nueva_unidad(client, auth):
    from cacao_accounting.database import Unidad

    auth.login()
    response = client.get("/accounts/unit/new")
    assert b"Crear Nueva Unidad de Negocios." in response.data
    unidad = Unidad.query.filter_by(unidad="Test Form").first()
    assert unidad is None
    post = client.post(
        "/accounts/unit/new",
        data={
            "id": "test",
            "nombre": "Test Form",
            "entidad": "cacao",
            "correo_electronico": "test@cacao.io",
            "web": "https://cacao.io",
            "telefono1": "+505 8771 0980",
            "telefono2": "+505 8661 2108",
            "fax": "+505 2273 0754",
        },
    )
    unidad = Unidad.query.filter_by(unidad="test").first()
    assert unidad is not None
    assert unidad.entidad == "cacao"
    assert unidad.unidad == "test"
