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

# pylint: disable=redefined-outer-name,
from unittest import TestCase
import pytest
from os import environ
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database
from cacao_accounting.datos import base_data, dev_data


configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
configuracion["TESTING"] = True
configuracion["DEBUG"] = True
configuracion["WTF_CSRF_ENABLED"] = False
configuracion["SESSION_PROTECTION "] = None


@pytest.mark.skipif(environ.get("CACAO_TEST_SLOW", None) is None, reason="Variable de entorno CACAO_TEST_SLOW no definida")
class TestAuth(TestCase):
    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["LOGIN_DISABLED"] = True
        self.app.app_context().push()
        database.drop_all()
        database.create_all()
        base_data(carga_rapida=True)
        dev_data()

    def tearDown(self):
        pass

    @pytest.mark.slow
    def test_without_login(self):
        response = self.app.test_client().get("/")
        assert response.status_code == 302

    @pytest.mark.slow
    def test_loging(self):
        response = self.app.test_client().get("/login")
        assert response.status_code == 200

    @pytest.mark.slow
    def test_login_valido(self):
        from cacao_accounting.auth import validar_acceso

        correcto = validar_acceso("cacao", "cacao")
        assert correcto == True

    @pytest.mark.slow
    def test_contraseña_erronea(self):
        from cacao_accounting.auth import validar_acceso

        erroneo = validar_acceso("cacao", "hola")
        assert erroneo == False

    @pytest.mark.slow
    def test_usuario_no_existe(self):
        from cacao_accounting.auth import validar_acceso

        erroneo = validar_acceso("hola", "hola")
        assert erroneo == False

    @pytest.mark.slow
    def test_sesion_nula(self):
        from cacao_accounting.auth import cargar_sesion

        resultado = cargar_sesion(None)
        assert resultado == None


def crear_db():

    app = create_app(configuracion)
    app.app_context().push()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    database.drop_all()
    database.create_all()
    base_data(carga_rapida=True)
    dev_data()


@pytest.mark.slow
def test_valida_contraseña():
    from cacao_accounting.auth import validar_acceso

    crear_db()
    assert validar_acceso("cacao", "cacao") == True
    assert validar_acceso("cacao", "prueba") == False


@pytest.mark.slow
def test_logea_usuario():
    from cacao_accounting.auth import cargar_sesion

    crear_db()
    cargar_sesion("cacao")
