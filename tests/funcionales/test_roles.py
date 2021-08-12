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
from unittest import TestCase
from os import environ
import pytest
from cacao_accounting import create_app as app_factory
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import db
from cacao_accounting.database.helpers import obtener_id_modulo_por_monbre, obtener_id_usuario_por_nombre
from cacao_accounting.datos import base_data, dev_data

CONFIG = {
    "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
    "SQLALCHEMY_DATABASE_URI": "sqlite://",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "TESTING": True,
    "WTF_CSRF_ENABLED": False,
    "DEBUG": True,
    "DESKTOPMODE": False,
}


@pytest.fixture(scope="module", autouse=True)
def app():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
    app.app_context().push()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AdminLogin:
    def __init__(self, client):
        self._client = client

    def login(self):
        return self._client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

    def logout(self):
        return self._client.get("/salir")


@pytest.fixture
def admin(client):
    return AdminLogin(client)


def test_login(client, admin):
    admin.login()
    response = client.get("/test_roles")
    assert b"cacao" in response.data


def test_permisos_rol_purchase_manager():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
        permisos_compras = Permisos(
            modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("compras")
        )
        from cacao_accounting.database import Modulos, Usuario

        MODULO = Modulos.query.filter_by(modulo="buying").first()
        USUARIO = Usuario.query.filter_by(usuario="compras").first()
        assert permisos_compras.usuario == USUARIO.id
        assert permisos_compras.modulo == MODULO.id
        assert permisos_compras.administrador is False
        assert permisos_compras.roles is not None
        assert isinstance(permisos_compras.roles, list)
        assert permisos_compras.usuario_autorizado() is True
        permisos_conta = Permisos(
            modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("compras")
        )
        assert permisos_conta.usuario_autorizado() is False
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("compras")
        )
        assert permisos_ventas.usuario_autorizado() is False
