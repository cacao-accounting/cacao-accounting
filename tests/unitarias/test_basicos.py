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


def test_verifica_coneccion_db():
    from flask import Flask
    from cacao_accounting.database import verifica_coneccion_db

    app = Flask(__name__)
    assert verifica_coneccion_db(app) == False


def test_db():
    crear_db()


def test_valida_contraseña():
    from cacao_accounting.auth import validar_acceso

    crear_db()
    assert validar_acceso("cacao", "cacao") == True
    assert validar_acceso("cacao", "prueba") == False


def test_logea_usuario():
    from cacao_accounting.auth import cargar_sesion

    crear_db()
    cargar_sesion("cacao")


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


def test_cli():
    import subprocess

    subprocess.Popen(
        ["cacaoctl"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )


def test__main__():
    import subprocess
    from sys import executable

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

    def test_flaskapp(self):
        from flask import Flask

        self.assertIsInstance(self.app, Flask)

    def test_cli(self):
        self.app.test_cli_runner()

    def test_dbinstance(self):
        from flask_sqlalchemy import SQLAlchemy
        from cacao_accounting.database import db

        self.assertIsInstance(db, SQLAlchemy)

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


class TestExection(TestCase):
    def test_no_data(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.exception import OperationalError

        r = Registro()
        with pytest.raises(OperationalError):
            r.crear(datos=None)

    def test_no_tabla(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.exception import OperationalError

        r = Registro()
        with pytest.raises(OperationalError):
            r.crear(datos={})

    def test_registro_vacio(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.exception import OperationalError

        r = Registro()
        with pytest.raises(OperationalError):
            r.crear_registro(datos=None, entidad_madre="hola")

    def test_entidad_vacias(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.exception import OperationalError

        r = Registro()
        with pytest.raises(OperationalError):
            r.crear_registro(datos={}, entidad_madre=None)

    def test_sin_tabla(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.exception import OperationalError

        r = Registro()
        with pytest.raises(OperationalError):
            r.crear_registro(datos={}, entidad_madre="hola")

    def test_eliminar_sintabla(self):
        from cacao_accounting.registro import Registro
        from cacao_accounting.exception import OperationalError

        r = Registro()
        with pytest.raises(OperationalError):
            r.eliminar(identificador="hola")

    def test_querry_vacio(self):
        from cacao_accounting.exception import DataError
        from cacao_accounting.consultas import paginar_consulta

        with pytest.raises(DataError):
            paginar_consulta(tabla=None, elementos=None)
