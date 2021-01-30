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
from unittest import TestCase
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import db, Usuario
from cacao_accounting.datos.base import base_data
from cacao_accounting.datos.demo import demo_data


configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
configuracion["TESTING"] = True
configuracion["DEBUG"] = True
configuracion["WTF_CSRF_ENABLED"] = False
app = create_app(configuracion)
app.login_manager.session_protection = None
app.login_manager.init_app(app)
app.app_context().push()


def test_inicio():
    response = app.test_client().get("/login")
    assert response.status_code == 200
    assert b"Cacao Accounting" in response.data


VISTAS_PROTEGIDAS = [
    "/app",
    "/accounts",
    "/cash",
    "/buying",
    "/inventory",
    "/sales",
    "/settings",
]


def test_vista():
    for url in VISTAS_PROTEGIDAS:
        print(url)
        response = app.test_client().get(url)
        assert response.status_code == 302


class TestVistas(TestCase):
    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["LOGIN_DISABLED"] = True
        self.app.app_context().push()
        db.drop_all()
        db.create_all()
        base_data(carga_rapida=True)
        demo_data()
