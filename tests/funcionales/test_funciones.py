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
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data


@pytest.fixture(scope="module", autouse=True)
def app():
    app = app_factory(
        {
            "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DEBUG": True,
            "DESKTOPMODE": False,
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        demo_data()
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


def test_establece_entidad_como_predeterminada(client, auth):
    auth.login()
    from cacao_accounting.database import Entidad

    cacao = Entidad.query.filter_by(entidad="cacao").first()
    assert cacao.status == "predeterminado"
    cafe = Entidad.query.filter_by(entidad="cafe").first()

    response = client.get("/accounts/entity/set_default/" + cafe.id)
    assert "302 FOUND" == response.status
    check = Entidad.query.filter_by(entidad="cafe").first()
    assert check.status == "predeterminado"
    # El estatus de la entidad cacao debe cambiar a "activo"
    check1 = Entidad.query.filter_by(entidad="cacao").first()
    assert check1.status == "activo"
    dulce = Entidad.query.filter_by(entidad="dulce").first()
    response1 = client.get("/accounts/entity/set_default/" + dulce.id)
    assert "302 FOUND" == response1.status


def test_establece_entidad_como_inabilitada(client, auth):
    auth.login()
    from cacao_accounting.database import Entidad

    cafe = Entidad.query.filter_by(entidad="cafe").first()
    assert cafe.status == "activo"
    response = client.get("/accounts/entity/set_inactive/" + cafe.id)
    check = Entidad.query.filter_by(entidad="cafe").first()
    assert check.status == "inactivo"
