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
from base_test import BaseTest


def crear_db():
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion
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
    base_data(carga_rapida=True)
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


def test_main():
    import subprocess
    from sys import executable

    proceso1 = subprocess.Popen(
        [executable, "cacao_accounting"],
    )
    proceso2 = subprocess.Popen(
        [executable, "cacao_accounting"],
    )
    proceso1.terminate()
    proceso2.terminate()


def test_cli():
    import subprocess

    proceso = subprocess.Popen(
        ["cacaoctl"],
    )
    proceso.terminate()


class TestBasicos(TestCase):
    def setUp(self):
        from cacao_accounting import create_app

        self.app = create_app()
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.app_context().push()

    def test_flaskapp(self):
        from flask import Flask

        self.assertIsInstance(self.app, Flask)

    def test_dbinstance(self):
        from flask_sqlalchemy import SQLAlchemy
        from cacao_accounting.database import db

        self.assertIsInstance(db, SQLAlchemy)


ENTIDAD1 = {
    "id": "cacao1",
    "razon_social": "Choco Sonrisas Sociedad Anonima",
    "nombre_comercial": "Choco Sonrisas",
    "id_fiscal": "J0310000000000",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": True,
}

ENTIDAD2 = {
    "id": "cacao2",
    "razon_social": "Choco Sonrisas 2 Sociedad Anonima",
    "nombre_comercial": "Choco Sonrisas 2",
    "id_fiscal": "J0310000000001",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": True,
}


ENTIDAD3 = {
    "id": "cacao2",
    "razon_social": "Choco Sonrisas 2 Sociedad Anonima",
    "nombre_comercial": "Choco Sonrisas 2",
    "id_fiscal": "J0310000000001",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": True,
}


class TestInstancias(TestCase, BaseTest):
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from sqlalchemy.exc import IntegrityError
    from cacao_accounting.database import db, Entidad

    instancia_entidad = RegistroEntidad()

    def test_crearentidad(self):
        self.db.drop_all()
        self.db.create_all()
        self.instancia_entidad.crear(ENTIDAD1)
        self.instancia_entidad.crear(ENTIDAD2)

    def test_entidadescreadas(self):
        assert self.db.session.query(self.Entidad).count(), 2

    def test_noduplicarid(self):

        with self.assertRaises(self.IntegrityError):
            self.instancia_entidad.crear(ENTIDAD3)
