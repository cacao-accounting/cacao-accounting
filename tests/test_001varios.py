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


def crear_db():
    from cacao_accounting import create_app
    from cacao_accounting.conf import configuracion
    from cacao_accounting.database import db
    from cacao_accounting.datos.base import base_data
    from cacao_accounting.datos.demo import demo_data

    app = create_app(configuracion)
    app.app_context().push()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    db.drop_all()
    db.create_all()
    base_data()
    demo_data()


def test_db():
    crear_db()


def test_valida_contraseña():
    from cacao_accounting.auth import validar_acceso

    assert True == validar_acceso("cacao", "cacao")
    assert False == validar_acceso("cacao", "prueba")


def test_logea_usuario():
    from cacao_accounting.auth import cargar_sesion

    cargar_sesion("cacao")


def test_run():
    import subprocess
    from sys import executable
    from cacao_accounting.__main__ import app, run

    subprocess.Popen(
        [executable, "-m", "cacao_accounting"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )


def test_cli():
    import subprocess
    from cacao_accounting import cli

    subprocess.Popen(
        ["cacaoctl"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )


def test_run():
    from cacao_accounting.__main__ import run

    run()
    run()


def test_main():
    import subprocess
    from sys import executable

    subprocess.Popen(
        [executable, "cacao_accounting"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )


class TestBasicos(TestCase):
    def setUp(self):
        from cacao_accounting import create_app

        self.app = create_app()
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    def test_flaskapp(self):
        from flask import Flask

        self.assertIsInstance(self.app, Flask)

    def test_dbinstance(self):
        from flask_sqlalchemy import SQLAlchemy
        from cacao_accounting.database import db

        self.assertIsInstance(db, SQLAlchemy)
