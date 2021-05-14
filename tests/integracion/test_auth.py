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
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import db
from cacao_accounting.datos.base import base_data
from cacao_accounting.datos.demo import demo_data


configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
configuracion["TESTING"] = True
configuracion["DEBUG"] = True
configuracion["WTF_CSRF_ENABLED"] = False
configuracion["SESSION_PROTECTION "] = None


class TestAutenticacion(TestCase):
    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["LOGIN_DISABLED"] = True
        self.app.app_context().push()
        db.drop_all()
        db.create_all()
        base_data(carga_rapida=True)
        demo_data()

    def tearDown(self):
        pass

    def test_without_login(self):
        response = self.app.test_client().get("/")
        assert response.status_code == 302

    def test_loging(self):
        response = self.app.test_client().get("/login")
        assert response.status_code == 200

    def test_login_valido(self):
        from cacao_accounting.auth import validar_acceso

        correcto = validar_acceso("cacao", "cacao")
        assert correcto == True

    def test_contraseña_erronea(self):
        from cacao_accounting.auth import validar_acceso

        erroneo = validar_acceso("cacao", "hola")
        assert erroneo == False

    def test_usuario_no_existe(self):
        from cacao_accounting.auth import validar_acceso

        erroneo = validar_acceso("hola", "hola")
        assert erroneo == False

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
    db.drop_all()
    db.create_all()
    base_data(carga_rapida=True)
    demo_data()


def test_valida_contraseña():
    from cacao_accounting.auth import validar_acceso

    crear_db()
    assert validar_acceso("cacao", "cacao") == True
    assert validar_acceso("cacao", "prueba") == False


def test_logea_usuario():
    from cacao_accounting.auth import cargar_sesion

    crear_db()
    cargar_sesion("cacao")
