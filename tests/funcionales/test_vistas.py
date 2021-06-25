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


def test_config(app):
    assert app.config["DEBUG"] == True


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


def test_login(client):
    response = client.get("/login")
    assert b"Cacao" in response.data


def test_app(client, auth):
    auth.login()
    response = client.get("/app")
    assert b"Aplicacion Contable" in response.data


def test_contabilidad(client, auth):
    auth.login()
    response = client.get("/accounts")
    assert b"Contabilidad." in response.data


def test_listado_entidades(client, auth):
    auth.login()
    response = client.get("/accounts/entities")
    assert b"Listado de Entidades." in response.data


def test_nueva_entidad(client, auth):
    auth.login()
    response = client.get("/accounts/entities/new")
    assert b"Crear Nueva Entidad." in response.data


def test_entidad(client, auth):
    auth.login()
    response = client.get("/accounts/entity/cacao")
    assert b"Datos Generales:" in response.data
    assert b"Choco Sonrisas Sociedad Anonima" in response.data
    response = client.get("/accounts/entity/dulce")
    assert b"Mundo Sabor Sociedad Anonima" in response.data


def test_listado_unidades(client, auth):
    auth.login()
    response = client.get("/accounts/units")
    assert b"Listado de Unidades de Negocio." in response.data


def test_unidad(client, auth):
    auth.login()
    response = client.get("/accounts/unit/masaya")
    assert b"Masaya" in response.data
    response = client.get("/accounts/unit/matriz")
    assert b"Matriz" in response.data


def test_catalogoctas(client, auth):
    auth.login()
    response = client.get("/accounts/accounts")
    assert b"Catalogo de Cuentas Contables." in response.data


def test_catalogoctasent(client, auth):
    auth.login()
    response = client.get("/accounts/accounts?entidad=cafe")
    assert b"Catalogo de Cuentas Contables." in response.data


def test_listado_monedas(client, auth):
    auth.login()
    responde = client.get("/currencies")


def test_cambiar_status_entidad(client, auth):
    auth.login()
    response = client.get("/accounts/entities/set_inactive/cacao")
    response = client.get("/accounts/entities/set_default/cacao")


def test_cambio_status(client, auth):
    auth.login()
    response = client.get("/accounts/entities/set_inactive/cafe")
    response = client.get("/accounts/entities/set_default/cafe")
    responde = client.get("/accounts/entities/delete/cafe")


def test_eliminar_entidad(client, auth):
    auth.login()
    responde = client.get("/accounts/units/delete/masaya")


def test_ctacontable(client, auth):
    auth.login()
    responde = client.get("/accounts/accounts")
    responde = client.get("/accounts/accounts/11")
    responde = client.get("/accounts/accounts/21")
    responde = client.get("/accounts/accounts/3")


def test_centrocostos(client, auth):
    auth.login()
    responde = client.get("/accounts/costs_center")
    responde = client.get("/accounts/costs_center?entidad=cafe")
    responde = client.get("/accounts/costs_center/A00000")
    responde = client.get("/accounts/costs_center/B00000")
    responde = client.get("/accounts/costs_center/B00001")


def test_proyectos(client, auth):
    auth.login()
    responde = client.get("/accounts/projects")


def test_monedas(client, auth):
    auth.login()
    responde = client.get("/currencies")


def test_tasascambio(client, auth):
    auth.login()
    responde = client.get("/accounts/exchange")


def test_development(client, auth):
    auth.login()
    responde = client.get("/development")


def test_periodo_contable(client, auth):
    auth.login()
    responde = client.get("/accounts/accounting_period")


# Dejar este test al final porque modifica los estatus de los modulos en la base de datos.
def test_modulos_inactivos(client, auth):
    from cacao_accounting.database import Modulos

    for modulo in ["accounting", "cash", "buying", "inventory", "sales"]:
        modulo = Modulos.query.filter_by(modulo=modulo).first()
        modulo.habilitado = False
        db.session.add(modulo)
        db.session.commit()

    auth.login()
    responde = client.get("/app")
    responde = client.get("/accounts")
    responde = client.get("/cash")
    responde = client.get("/buying")
    responde = client.get("/inventory")
    responde = client.get("/sales")


def test_no_autorizado(client):
    from flask import current_app
    from cacao_accounting.auth import no_autorizado

    with current_app.test_request_context():
        with current_app.app_context():
            no_autorizado()


def test_devpage_false(client, elimina_variable_entorno):
    r = client.get("/info")
