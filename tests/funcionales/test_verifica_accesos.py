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
from os import environ
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


# <-------------------------------------------------------------------------> #
# Prueba vistas sin seción iniciada
@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_ANONIMO(client):
    vista = client.get("/permisos_usuario")
    pass


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


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_ADMINISTRADOR(client, administrador):
    administrador.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> administrador@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de jefe de contabilidad
@pytest.fixture
def contador(client):
    return AuthActions(client, "contabilidad", "contabilidad")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_CONTABILIDAD(client, contador):
    contador.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> contabilidad@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auxiliar de contabilidad
@pytest.fixture
def contadorj(client):
    return AuthActions(client, "contabilidadj", "contabilidadj")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_CONTABILIDADJUNIOR(client, contadorj):
    contadorj.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> contabilidadj@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de jefe de compras.
@pytest.fixture
def compras(client):
    return AuthActions(client, "compras", "compras")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_COMPRAS(client, compras):
    compras.login()
    vista = client.get("/permisos_usuario")
    assert b"compras@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auxiliar de compras.
@pytest.fixture
def comprasj(client):
    return AuthActions(client, "comprasj", "comprasj")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_COMPRASJUNIOR(client, comprasj):
    comprasj.login()
    vista = client.get("/permisos_usuario")
    assert b"comprasj@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de jefe de ventas.
@pytest.fixture
def ventas(client):
    return AuthActions(client, "ventas", "ventas")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_VENTAS(client, ventas):
    ventas.login()
    vista = client.get("/permisos_usuario")
    assert b"ventas@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auxiliar de ventas.
@pytest.fixture
def ventasj(client):
    return AuthActions(client, "ventasj", "ventasj")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_VENTASJUNIOR(client, ventasj):
    ventasj.login()
    vista = client.get("/permisos_usuario")
    assert b"ventasj@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de jefe de almacen.
@pytest.fixture
def almacen(client):
    return AuthActions(client, "inventario", "inventario")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_ALMACEN(client, almacen):
    almacen.login()
    vista = client.get("/permisos_usuario")
    assert b"inventario@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auxiliar de almacen.
@pytest.fixture
def almacenj(client):
    return AuthActions(client, "inventarioj", "inventarioj")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_ALMACENJUNIOR(client, almacenj):
    almacenj.login()
    vista = client.get("/permisos_usuario")
    assert b"inventarioj@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de jefe de tesoreria.
@pytest.fixture
def tesoreria(client):
    return AuthActions(client, "tesoreria", "tesoreria")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_TESORERIA(client, tesoreria):
    tesoreria.login()
    vista = client.get("/permisos_usuario")
    assert b"tesoreria@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auxiliar de tesoreria.
@pytest.fixture
def tesoreriaj(client):
    return AuthActions(client, "tesoreriaj", "tesoreriaj")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_TESORERIAJUNIOR(client, tesoreriaj):
    tesoreriaj.login()
    vista = client.get("/permisos_usuario")
    assert b"tesoreriaj@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de auditoria interna.
@pytest.fixture
def auditoria(client):
    return AuthActions(client, "auditor", "auditor")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_AUDITOR(client, auditoria):
    auditoria.login()
    vista = client.get("/permisos_usuario")
    assert b"auditor@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de analista.
@pytest.fixture
def analista(client):
    return AuthActions(client, "analista", "analista")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_ANALISTA(client, analista):
    analista.login()
    vista = client.get("/permisos_usuario")
    assert b"analista@cacao_accounting.io" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de pasante
@pytest.fixture
def pasante(client):
    return AuthActions(client, "pasante", "pasante")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_PASANTE(client, pasante):
    pasante.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> pasante@cacao_accounting.io</li>" in vista.data


# <-------------------------------------------------------------------------> #
# Prueba vistas con el rol de usuario
@pytest.fixture
def usuario(client):
    return AuthActions(client, "usuario", "usuario")


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable CACAO_TEST_SLOW no definida")
def test_permisos_usuario_USUARIO(client, usuario):
    usuario.login()
    vista = client.get("/permisos_usuario")
    assert b"<li><strong>Correo Electronico:</strong> usuario@cacao_accounting.io</li>" in vista.data
