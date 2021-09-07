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

# pylint: disable=redefined-outer-name, too-many-lines
import pytest
from cacao_accounting import create_app as app_factory
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import database
from cacao_accounting.database.helpers import obtener_id_modulo_por_monbre, obtener_id_usuario_por_nombre
from cacao_accounting.datos import base_data, dev_data

CONFIG = {
    "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
    "SQLALCHEMY_DATABASE_URI": "sqlite://",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "TESTING": True,
    "WTF_CSRF_ENABLED": False,
    "DEBUG": True,
    "DESKTOPMODE": False,
}

MODULOS = ["accounting", "cash", "purchases", "inventory", "sales", "admin"]


@pytest.fixture(scope="module", autouse=True)
def app():
    app = app_factory(CONFIG)
    with app.app_context():
        database.drop_all()
        database.create_all()
        base_data()
        dev_data()
    app.app_context().push()
    yield app


# Estos test unitarios validan que la logica del sistema de roles este bien implementada,
def test_logicos():
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("cacao"))
    assert isinstance(permisos.autorizado, bool)
    assert isinstance(permisos.actualizar, bool)
    assert isinstance(permisos.anular, bool)
    assert isinstance(permisos.autorizar, bool)
    assert isinstance(permisos.bi, bool)
    assert isinstance(permisos.cerrar, bool)
    assert isinstance(permisos.configurar, bool)
    assert isinstance(permisos.consultar, bool)
    assert isinstance(permisos.corregir, bool)
    assert isinstance(permisos.crear, bool)
    assert isinstance(permisos.editar, bool)
    assert isinstance(permisos.eliminar, bool)
    assert isinstance(permisos.importar, bool)
    assert isinstance(permisos.listar, bool)
    assert isinstance(permisos.reportes, bool)
    assert isinstance(permisos.solicitar, bool)
    assert isinstance(permisos.validar, bool)
    assert isinstance(permisos.validar_solicitud, bool)
    assert isinstance(permisos.roles, list)
    assert isinstance(permisos.administrador, bool)
    assert isinstance(permisos.modulo, str)
    assert isinstance(permisos.permisos_usuario, list)


def test_permisos_rol_admin():
    for MODULO in MODULOS:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre("cacao"))
        assert permisos.autorizado is True
        assert permisos.actualizar is True
        assert permisos.anular is True
        assert permisos.autorizar is True
        assert permisos.bi is True
        assert permisos.cerrar is True
        assert permisos.configurar is True
        assert permisos.consultar is True
        assert permisos.corregir is True
        assert permisos.crear is True
        assert permisos.editar is True
        assert permisos.eliminar is True
        assert permisos.importar is True
        assert permisos.listar is True
        assert permisos.reportes is True
        assert permisos.solicitar is True
        assert permisos.validar is True
        assert permisos.validar_solicitud is True


def test_permisos_no_user():
    for MODULO in MODULOS:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre(None))
        assert permisos.autorizado is False
        assert permisos.actualizar is False
        assert permisos.anular is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.configurar is False
        assert permisos.consultar is False
        assert permisos.corregir is False
        assert permisos.crear is False
        assert permisos.editar is False
        assert permisos.eliminar is False
        assert permisos.importar is False
        assert permisos.listar is False
        assert permisos.reportes is False
        assert permisos.solicitar is False
        assert permisos.validar is False
        assert permisos.validar_solicitud is False


def test_permisos_user_invalido():
    for MODULO in MODULOS:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario="hola")
        assert permisos.autorizado is False
        assert permisos.actualizar is False
        assert permisos.anular is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.configurar is False
        assert permisos.consultar is False
        assert permisos.corregir is False
        assert permisos.crear is False
        assert permisos.editar is False
        assert permisos.eliminar is False
        assert permisos.importar is False
        assert permisos.listar is False
        assert permisos.reportes is False
        assert permisos.solicitar is False
        assert permisos.validar is False
        assert permisos.validar_solicitud is False


def test_permisos_no_modulo():
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre(None), usuario=obtener_id_usuario_por_nombre("cacao"))
    assert permisos.autorizado is False
    assert permisos.actualizar is False
    assert permisos.anular is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.configurar is False
    assert permisos.consultar is False
    assert permisos.corregir is False
    assert permisos.crear is False
    assert permisos.editar is False
    assert permisos.eliminar is False
    assert permisos.importar is False
    assert permisos.listar is False
    assert permisos.reportes is False
    assert permisos.solicitar is False
    assert permisos.validar is False
    assert permisos.validar_solicitud is False


def test_permisos_modulo_invalido():
    permisos = Permisos(modulo="hola", usuario=obtener_id_usuario_por_nombre("cacao"))
    assert permisos.autorizado is False
    assert permisos.actualizar is False
    assert permisos.anular is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.configurar is False
    assert permisos.consultar is False
    assert permisos.corregir is False
    assert permisos.crear is False
    assert permisos.editar is False
    assert permisos.eliminar is False
    assert permisos.importar is False
    assert permisos.listar is False
    assert permisos.reportes is False
    assert permisos.solicitar is False
    assert permisos.validar is False
    assert permisos.validar_solicitud is False


# Estas pruebas unitarias son repetitivas pero para cada rol predeterminado validamos que los permisos
# con correctos para cada modulo predeterminado.


MODULOS_ = ["accounting", "cash", "purchases", "inventory", "sales"]


def test_permisos_rol_comptroller():
    for MODULO in MODULOS_:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre("auditor"))
        assert permisos.autorizado is True
        assert permisos.anular is False
        assert permisos.actualizar is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.consultar is True
        assert permisos.crear is False
        assert permisos.reportes is True
        assert permisos.validar is False
        assert permisos.importar is False
        assert permisos.corregir is False
        assert permisos.listar is True
        assert permisos.solicitar is False
        assert permisos.validar_solicitud is False
        assert permisos.eliminar is False
    # Modulo Administrativo
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre("admin"), usuario=obtener_id_usuario_por_nombre("auditor"))
    assert permisos.autorizado is False
    assert permisos.actualizar is False
    assert permisos.anular is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.configurar is False
    assert permisos.consultar is False
    assert permisos.corregir is False
    assert permisos.crear is False
    assert permisos.editar is False
    assert permisos.eliminar is False
    assert permisos.importar is False
    assert permisos.listar is False
    assert permisos.reportes is False
    assert permisos.solicitar is False
    assert permisos.validar is False
    assert permisos.validar_solicitud is False


def test_permisos_rol_bi():
    for MODULO in MODULOS_:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre("analista"))
        assert permisos.autorizado is True
        assert permisos.anular is False
        assert permisos.actualizar is False
        assert permisos.autorizar is False
        assert permisos.bi is True
        assert permisos.cerrar is False
        assert permisos.consultar is True
        assert permisos.crear is False
        assert permisos.reportes is True
        assert permisos.validar is False
        assert permisos.importar is False
        assert permisos.corregir is False
        assert permisos.listar is True
        assert permisos.solicitar is False
        assert permisos.validar_solicitud is False
        assert permisos.eliminar is False
    # Modulo Administrativo
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre("admin"), usuario=obtener_id_usuario_por_nombre("analista"))
    assert permisos.autorizado is False
    assert permisos.actualizar is False
    assert permisos.anular is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.configurar is False
    assert permisos.consultar is False
    assert permisos.corregir is False
    assert permisos.crear is False
    assert permisos.editar is False
    assert permisos.eliminar is False
    assert permisos.importar is False
    assert permisos.listar is False
    assert permisos.reportes is False
    assert permisos.solicitar is False
    assert permisos.validar is False
    assert permisos.validar_solicitud is False


def test_rol_PURCHASING_MANAGER():
    USUARIO = "compras"
    MODULO = "purchases"
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre(USUARIO))
    assert permisos.autorizado is True
    assert permisos.actualizar is True
    assert permisos.anular is True
    assert permisos.autorizar is True
    assert permisos.bi is True
    assert permisos.cerrar is True
    assert permisos.configurar is True
    assert permisos.consultar is True
    assert permisos.corregir is True
    assert permisos.crear is True
    assert permisos.editar is True
    assert permisos.eliminar is False
    assert permisos.importar is True
    assert permisos.listar is True
    assert permisos.reportes is True
    assert permisos.solicitar is True
    assert permisos.validar is True
    assert permisos.validar_solicitud is True
    for modulo in ("accounting", "cash", "inventory", "sales"):
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(modulo), usuario=obtener_id_usuario_por_nombre(USUARIO))
        assert permisos.autorizado is False
        assert permisos.actualizar is False
        assert permisos.anular is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.configurar is False
        assert permisos.consultar is False
        assert permisos.corregir is False
        assert permisos.crear is False
        assert permisos.editar is False
        assert permisos.eliminar is False
        assert permisos.importar is False
        assert permisos.listar is False
        assert permisos.reportes is False
        assert permisos.solicitar is False
        assert permisos.validar is False
        assert permisos.validar_solicitud is False


def test_rol_PURCHASING_AUXILIAR():
    USUARIO = "comprasj"
    MODULO = "purchases"
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre(USUARIO))
    assert permisos.autorizado is True
    assert permisos.actualizar is True
    assert permisos.anular is False
    assert permisos.autorizar is False
    assert permisos.bi is True
    assert permisos.cerrar is False
    assert permisos.configurar is False
    assert permisos.consultar is True
    assert permisos.corregir is False
    assert permisos.crear is True
    assert permisos.editar is True
    assert permisos.eliminar is False
    assert permisos.importar is False
    assert permisos.listar is True
    assert permisos.reportes is True
    assert permisos.solicitar is True
    assert permisos.validar is False
    assert permisos.validar_solicitud is False
    for modulo in ("accounting", "cash", "inventory", "sales"):
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(modulo), usuario=obtener_id_usuario_por_nombre(USUARIO))
        assert permisos.autorizado is False
        assert permisos.actualizar is False
        assert permisos.anular is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.configurar is False
        assert permisos.consultar is False
        assert permisos.corregir is False
        assert permisos.crear is False
        assert permisos.editar is False
        assert permisos.eliminar is False
        assert permisos.importar is False
        assert permisos.listar is False
        assert permisos.reportes is False
        assert permisos.solicitar is False
        assert permisos.validar is False
        assert permisos.validar_solicitud is False


def test_rol_PURCHASING_USER():
    USUARIO = "usuario"
    for modulo in ("purchases",):
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(modulo), usuario=obtener_id_usuario_por_nombre(USUARIO))
        assert permisos.autorizado is True
        assert permisos.actualizar is False
        assert permisos.anular is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.configurar is False
        assert permisos.consultar is True
        assert permisos.corregir is False
        assert permisos.crear is False
        assert permisos.editar is False
        assert permisos.eliminar is False
        assert permisos.importar is False
        assert permisos.listar is True
        assert permisos.reportes is False
        assert permisos.solicitar is True
        assert permisos.validar is False
        assert permisos.validar_solicitud is False
