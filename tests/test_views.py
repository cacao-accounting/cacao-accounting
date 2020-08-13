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
from flask_login import LoginManager, logout_user, login_user
from cacao_accounting import create_app as create
from cacao_accounting.database import db, Usuario
from cacao_accounting.datos import base_data, demo_data
from cacao_accounting.conf import configuracion

app = create(configuracion)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
app.config["TESTING"] = True
app.config["DEBUG"] = True
# Ver: https://flask-sqlalchemy.palletsprojects.com/en/2.x/contexts/
app.app_context().push()


@pytest.fixture
def cliente_pruebas():
    with app.test_client() as pruebas:
        with app.app_context():
            db.create_all()
            base_data()
            demo_data()
        yield pruebas


# para actualizar el lista.
# from wsgi import app
# for rule in app.url_map.iter_rules(): print(rule)

_rutas = [
    "/accounts/entities",
    "/accounts/accounts",
    "/accounts/projects",
    "/accounts/exchange",
    "/accounts/ccenter",
    "/accounts/units",
    "/administracion",
    "/configuracion",
    "/contabilidad",
    "/inventario",
    "/tesoreria",
    "/inventory",
    "/settings",
    "/accounts",
    "/ajustes",
    "/compras",
    "/bancos",
    "/buying",
    "/logout" "/ventas",
    "/admin",
    "/conta",
    "/index",
    "/login",
    "/sales",
    "/cash",
    "/caja",
    "/home",
    "/app",
    "/",
]


def test_vista(cliente_pruebas):
    for rutas in _rutas:
        cliente_pruebas.get(rutas)
