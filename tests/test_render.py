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

import requests
from flask_testing import LiveServerTestCase
from cacao_accounting import create_app as create
from cacao_accounting.conf import configuracion
from cacao_accounting.database import db


class TestRenderTemplates(LiveServerTestCase):
    def create_app(self):
        app = create(configuracion)
        app.config["TESTING"] = True
        app.config["LIVESERVER_PORT"] = 0
        return app

    def setUp(self):
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
