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

from unittest import TestCase
import pytest
from cacao_accounting import create_app
from cacao_accounting.conf import configuracion
from cacao_accounting.database import db, Usuario
from cacao_accounting.datos.base import base_data
from cacao_accounting.datos.demo import demo_data


configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
configuracion["TESTING"] = True
configuracion["DEBUG"] = True
configuracion["WTF_CSRF_ENABLED"] = False
configuracion["SESSION_PROTECTION "] = None


class FlaskrTestCase(TestCase):
    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["LOGIN_DISABLED"] = True
        db.create_all()
        base_data()
        demo_data()

    def tearDown(self):
        db.drop_all()

    def test_without_login(self):
        response = self.app.test_client().get("/")
        assert response.status_code == 302

    def test_loging(self):
        response = self.app.test_client().get("/login")
        assert response.status_code == 200

    def test_cash(self):
        response = self.app.test_client().get("/cash")
        assert response.status_code == 200
        assert b"Caja y Bancos" in response.data