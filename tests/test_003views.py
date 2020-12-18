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
from cacao_accounting import create_app
from cacao_accounting.conf import configuracion
from cacao_accounting.database import db, Usuario
from cacao_accounting.datos.base import base_data
from cacao_accounting.datos.demo import demo_data


configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
configuracion["TESTING"] = True
configuracion["DEBUG"] = True
configuracion["WTF_CSRF_ENABLED"] = False
configuracion["SESSION_PROTECTION "] = None
app = create_app(configuracion)
app.login_manager.session_protection = None
app.login_manager.init_app(app)
app.app_context().push()
cliente = app.test_client()


@pytest.fixture
def client():
    with app.test_client() as client:
        try:
            db.drop_all()
        except:
            pass
        db.create_all()
        base_data()
        demo_data()
        yield client


def test_inicio(client):
    response = app.test_client().get("/login")
    assert response.status_code == 200
    assert b"Cacao Accounting" in response.data


def test_render_inicio(client):
    response = app.test_client().get("/login")
    assert b"Cacao Accounting" in response.data


def test_app(client):
    response = app.test_client().get("/app")
    assert response.status_code == 302


def test_logout(client):
    response = app.test_client().get("/logout")
    assert response.status_code == 302


def test_contabilidad(client):
    response = app.test_client().get("/accounts")
    assert response.status_code == 302
