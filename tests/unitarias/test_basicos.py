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


def test_info_desarrollo():
    from cacao_accounting.app import dev_info

    assert dev_info() is not None


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


def test_run():
    import subprocess
    from sys import executable

    subprocess.Popen(
        [executable, "-m", "cacao_accounting"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    subprocess.Popen(
        [executable, "cacao_accounting/cli.py"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    subprocess.Popen(
        [executable, "cacao_accounting/__main__.py"],
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


class TestBasicos(TestCase):
    def setUp(self):
        from cacao_accounting import create_app

        self.app = create_app()
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.app_context().push()

    def test_cli(self):
        self.app.test_cli_runner()

    def test_directorio_archivos(self):
        from cacao_accounting.tools import DIRECTORIO_ARCHIVOS

        assert self.app.static_folder == DIRECTORIO_ARCHIVOS

    def test_directorio_plantillas(self):
        from cacao_accounting.tools import DIRECTORIO_PLANTILLAS

        assert self.app.template_folder == DIRECTORIO_PLANTILLAS

    def test_directorio_principal(self):
        from cacao_accounting.tools import DIRECTORIO_APP

        assert self.app.root_path == DIRECTORIO_APP

    def test_import_name(self):
        assert self.app.import_name == "cacao_accounting"

    def test_config(self):
        from cacao_accounting.config import configuracion

        assert configuracion is not None


def test_validar_conexion_db():
    from cacao_accounting.config import valida_direccion_base_datos, MSSQL, MYSQL, POSTGRESQL, SQLITE

    assert valida_direccion_base_datos(MSSQL) == True
    assert valida_direccion_base_datos(MYSQL) == True
    assert valida_direccion_base_datos(POSTGRESQL) == True
    assert valida_direccion_base_datos(SQLITE) == True
    assert valida_direccion_base_datos("hola") == False


def test_valida_clave_secreta():
    from cacao_accounting.config import valida_llave_secreta

    assert valida_llave_secreta("gw(5g6qd$fM|MZJ{") == True
    assert valida_llave_secreta("d6VJxbVJBjQ3Z4yW") == True


class TestInstanciasDeClasesCorrectas(TestCase):
    def setUp(self):
        from cacao_accounting import create_app

        self.app = create_app()
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.app_context().push()

    def test_Flask(self):
        from flask import Flask

        self.assertIsInstance(self.app, Flask)

    def test_SQLAlchemy(self):
        from flask_sqlalchemy import SQLAlchemy
        from cacao_accounting.database import db

        self.assertIsInstance(db, SQLAlchemy)

    def test_Alembic(self):
        from flask_alembic import Alembic
        from cacao_accounting import alembic

        self.assertIsInstance(alembic, Alembic)

    def test_Talisman(self):
        from flask_talisman import Talisman
        from cacao_accounting import talisman

        self.assertIsInstance(talisman, Talisman)

    def test_Blueprints(self):
        from flask.blueprints import Blueprint
        from cacao_accounting.contabilidad import contabilidad

        self.assertIsInstance(contabilidad, Blueprint)
        from cacao_accounting.app import cacao_app

        self.assertIsInstance(cacao_app, Blueprint)
        from cacao_accounting.compras import compras

        self.assertIsInstance(compras, Blueprint)
        from cacao_accounting.bancos import bancos

        self.assertIsInstance(bancos, Blueprint)
        from cacao_accounting.ventas import ventas

        self.assertIsInstance(ventas, Blueprint)
        from cacao_accounting.inventario import inventario

        self.assertIsInstance(inventario, Blueprint)


class TestClasesHeredades(TestCase):
    def setUp(self):
        from cacao_accounting import create_app

        self.app = create_app()
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.app_context().push()

    def test_Form(self):
        from flask_wtf import FlaskForm
        from cacao_accounting.contabilidad.forms import FormularioEntidad

        self.assertTrue(issubclass(FormularioEntidad, FlaskForm))
        from cacao_accounting.contabilidad.forms import FormularioUnidad

        self.assertTrue(issubclass(FormularioUnidad, FlaskForm))

    def test_Registro(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.contabilidad.registros.ccosto import RegistroCentroCosto

        self.assertTrue(issubclass(RegistroCentroCosto, Registro))


def test_comprueba_lista_validaciones():
    from cacao_accounting import create_app
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo
    from cacao_accounting.registro import comprueba_lista_validaciones

    lista_funciones = [create_app, obtener_catalogo]
    lista_nofunciones = ["hola"]
    tuple_funciones = (create_app, obtener_catalogo)
    assert comprueba_lista_validaciones(lista_a_validar=lista_funciones) is True
    assert comprueba_lista_validaciones(lista_a_validar=tuple_funciones) is False
    assert comprueba_lista_validaciones(lista_a_validar=lista_nofunciones) is False
    assert comprueba_lista_validaciones(lista_a_validar=None) is False
    assert comprueba_lista_validaciones(lista_a_validar={}) is False


class TestExection(TestCase):
    def test_querry_vacio(self):
        from cacao_accounting.exception import DataError
        from cacao_accounting.database import paginar_consulta

        with pytest.raises(DataError):
            paginar_consulta(tabla=None, elementos=None)
