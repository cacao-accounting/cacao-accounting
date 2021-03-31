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


import pytest
import requests
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
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        demo_data()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions(object):
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


def test_listado_monedas(client, auth):
    auth.login()
    responde = client.get("/currencies")



try:
    # Ejecute python tests/server.py en una terminal distinta para ejecutar estas pruebas unitarias
    import time

    time.sleep(3)
    with requests.Session() as session:
        login = session.post("http://localhost:7563/login", data={"usuario": "cacao", "acceso": "cacao"})

        def test_inicio():
            r = requests.get("http://localhost:7563/login")
            assert "Cacao Accounting" in r.text
            assert "/static/css/signin.css" in r.text
            assert "Inicio de Sesión" in r.text

        def test_development():
            from cacao_accounting.metadata import DEVELOPMENT
            from os import environ

            r = requests.get("http://localhost:7563/development")
            if DEVELOPMENT or "CACAO_TEST" in environ:
                assert "desarrolladores" in r.text
            else:
                pass

        # <-------------------------------------------------------------------------------------------------------------> #
        # Aplicacion Principal
        def test_app():
            r = session.get("http://localhost:7563/app")
            assert "Aplicacion Contable para Micro Pequeñas y Medianas Empresas." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Modulo Contabilidad
        def test_contabilidad():
            r = session.get("http://localhost:7563/accounts")
            assert "Módulo Contabilidad." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Entidades
        def test_entidades():
            r = session.get("http://localhost:7563/accounts/entities")
            assert "Listado de Entidades." in r.text

        def test_entidad():
            r = session.get("http://localhost:7563/accounts/entity/cacao")
            assert "Entidad." in r.text
            assert "Información General" in r.text

        def tes_entidad_nueva():
            r = session.get("http://localhost:7563/accounts/entities/new")
            assert "Crear Nueva Entidad." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Unidades
        def test_unidades():
            r = session.get("http://localhost:7563/accounts/units")
            assert "Listado de Unidades de Negocio." in r.text

        def test_unidad():
            r = session.get("http://localhost:7563/accounts/unit/masaya")
            assert "Masaya" in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Catalogo de Cuentas
        def text_catalogo():
            r = session.get("http://localhost:7563/accounts/accounts")
            assert "Catálogo de Cuentas Contables." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Centros de Costos
        def test_centros_de_costos():
            r = session.get("http://localhost:7563/accounts/ccenter")
            assert "Listado de Centros de Costos." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Proyectos
        def test_proyectos():
            r = session.get("http://localhost:7563/accounts/projects")
            assert "Listado de Proyectos." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Monedas
        def test_monedas():
            r = session.get("http://localhost:7563/currencies")
            assert "Listado de Monedas." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Tasas de Cambio
        def test_tasas_de_cambio():
            r = session.get("http://localhost:7563/accounts/exchange")
            assert "Listado de Tasas de Cambio." in r.text


except requests.exceptions.ConnectionError:
    pass
