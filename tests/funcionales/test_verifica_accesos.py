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
        database.drop_all()
        database.create_all()
        base_data()
        dev_data()
    app.app_context().push()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


class AuthActions:
    def __init__(self, client, usuario, passwd):
        self._client = client
        self.usuario = usuario
        self.passwd = passwd

    def login(self):
        return self._client.post("/login", data={"usuario": self.usuario, "acceso": self.passwd})

    def logout(self):
        return self._client.get("/salir")


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de adminstrador
@pytest.fixture
def administrador(client):
    return AuthActions(client, "administrador", "administrador")


def test_permisos_usuario_ADMINISTRADOR(client, administrador):
    administrador.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> administrador@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de jefe de contabilidad
@pytest.fixture
def contador(client):
    return AuthActions(client, "contabilidad", "contabilidad")


def test_permisos_usuario_CONTABILIDAD(client, contador):
    contador.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> contabilidad@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auxiliar de contabilidad
@pytest.fixture
def contadorj(client):
    return AuthActions(client, "contabilidadj", "contabilidadj")


def test_permisos_usuario_CONTABILIDADJUNIOR(client, contadorj):
    contadorj.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> contabilidadj@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de pasante
@pytest.fixture
def pasante(client):
    return AuthActions(client, "pasante", "pasante")


def test_permisos_usuario_PASANTE(client, pasante):
    pasante.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> pasante@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de usuario
@pytest.fixture
def usuario(client):
    return AuthActions(client, "usuario", "usuario")


def test_permisos_usuario_USUARIO(client, usuario):
    usuario.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> usuario@cacao_accounting.io</li>" in vista.data
