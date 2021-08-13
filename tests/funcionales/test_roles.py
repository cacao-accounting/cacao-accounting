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

# pylint: disable=redefined-outer-name
import pytest
from cacao_accounting import create_app as app_factory
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import db
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

MODULOS = ["accounting", "cash", "buying", "inventory", "sales", "admin"]


@pytest.fixture(scope="module", autouse=True)
def app():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
    app.app_context().push()
    yield app


def test_logicos():
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("cacao"))
    assert isinstance(permisos.autorizado, bool)
    assert isinstance(permisos.anular, bool)
    assert isinstance(permisos.actualizar, bool)
    assert isinstance(permisos.autorizar, bool)
    assert isinstance(permisos.bi, bool)
    assert isinstance(permisos.cerrar, bool)
    assert isinstance(permisos.consultar, bool)
    assert isinstance(permisos.crear, bool)
    assert isinstance(permisos.reportes, bool)
    assert isinstance(permisos.validar, bool)
    assert isinstance(permisos.modulo, str)
    assert isinstance(permisos.usuario, str)


def test_permisos_rol_admin():
    for MODULO in MODULOS:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre("cacao"))
        assert permisos.autorizado is True
        assert permisos.anular is True
        assert permisos.actualizar is True
        assert permisos.autorizar is True
        assert permisos.bi is True
        assert permisos.cerrar is True
        assert permisos.consultar is True
        assert permisos.crear is True
        assert permisos.reportes is True
        assert permisos.validar is True
        assert permisos.importar is True
        assert permisos.corregir is True
        assert permisos.listar is True


def test_permisos_no_user():
    for MODULO in MODULOS:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario=obtener_id_usuario_por_nombre(None))
        assert permisos.autorizado is False
        assert permisos.anular is False
        assert permisos.actualizar is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.consultar is False
        assert permisos.crear is False
        assert permisos.reportes is False
        assert permisos.validar is False
        assert permisos.usuario is None
        assert permisos.importar is False
        assert permisos.corregir is False
        assert permisos.listar is False


def test_permisos_user_invalido():
    for MODULO in MODULOS:
        permisos = Permisos(modulo=obtener_id_modulo_por_monbre(MODULO), usuario="hola")
        assert permisos.autorizado is False
        assert permisos.anular is False
        assert permisos.actualizar is False
        assert permisos.autorizar is False
        assert permisos.bi is False
        assert permisos.cerrar is False
        assert permisos.consultar is False
        assert permisos.crear is False
        assert permisos.reportes is False
        assert permisos.validar is False
        assert permisos.importar is False
        assert permisos.corregir is False
        assert permisos.listar is False


def test_permisos_no_modulo():
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre(None), usuario=obtener_id_usuario_por_nombre("cacao"))
    assert permisos.autorizado is False
    assert permisos.anular is False
    assert permisos.actualizar is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.consultar is False
    assert permisos.crear is False
    assert permisos.reportes is False
    assert permisos.validar is False
    assert permisos.importar is False
    assert permisos.corregir is False
    assert permisos.listar is False


def test_permisos_modulo_invalido():
    permisos = Permisos(modulo="hola", usuario=obtener_id_usuario_por_nombre("cacao"))
    assert permisos.autorizado is False
    assert permisos.anular is False
    assert permisos.actualizar is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.consultar is False
    assert permisos.crear is False
    assert permisos.reportes is False
    assert permisos.validar is False
    assert permisos.modulo is None
    assert permisos.importar is False
    assert permisos.corregir is False
    assert permisos.listar is False


def test_permisos_rol_purchase_manager():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("compras")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("compras")
    )
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("compras")
    )
    assert permisos_compras.autorizado is True
    assert permisos_compras.anular is True
    assert permisos_compras.actualizar is True
    assert permisos_compras.autorizar is True
    assert permisos_compras.bi is True
    assert permisos_compras.cerrar is True
    assert permisos_compras.consultar is True
    assert permisos_compras.crear is True
    assert permisos_compras.reportes is True
    assert permisos_compras.validar is True
    assert permisos_compras.importar is True
    assert permisos_compras.corregir is True
    assert permisos_compras.listar is True

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("compras")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("compras"))
    assert permisos_ventas.autorizado is False
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is False
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is False
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is False
    assert permisos_ventas.crear is False
    assert permisos_ventas.reportes is False
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is False


def test_permisos_rol_purchase_auxiliar():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("comprasj")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("comprasj")
    )
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("comprasj")
    )
    assert permisos_compras.autorizado is True
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is True
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is True
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is True
    assert permisos_compras.crear is True
    assert permisos_compras.reportes is True
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is True

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("comprasj")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("comprasj"))
    assert permisos_ventas.autorizado is False
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is False
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is False
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is False
    assert permisos_ventas.crear is False
    assert permisos_ventas.reportes is False
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is False


def test_permisos_rol_accounting_manager():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("contabilidad")
    )
    assert permisos_conta.autorizado is True
    assert permisos_conta.anular is True
    assert permisos_conta.actualizar is True
    assert permisos_conta.autorizar is True
    assert permisos_conta.bi is True
    assert permisos_conta.cerrar is True
    assert permisos_conta.consultar is True
    assert permisos_conta.crear is True
    assert permisos_conta.reportes is True
    assert permisos_conta.validar is True
    assert permisos_conta.importar is True
    assert permisos_conta.corregir is True
    assert permisos_conta.listar is True

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("contabilidad")
    )
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("contabilidad")
    )
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("contabilidad")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(
        modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("contabilidad")
    )
    assert permisos_ventas.autorizado is False
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is False
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is False
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is False
    assert permisos_ventas.crear is False
    assert permisos_ventas.reportes is False
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is False


def test_permisos_rol_accounting_auxiliar():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("contabilidadj")
    )
    assert permisos_conta.autorizado is True
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is True
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is True
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is True
    assert permisos_conta.crear is True
    assert permisos_conta.reportes is True
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is True

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("contabilidadj")
    )
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("contabilidadj")
    )
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("contabilidadj")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(
        modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("contabilidadj")
    )
    assert permisos_ventas.autorizado is False
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is False
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is False
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is False
    assert permisos_ventas.crear is False
    assert permisos_ventas.reportes is False
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is False


def test_permisos_rol_sales_manager():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("ventas")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("ventas"))
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("ventas"))
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("ventas")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("ventas"))
    assert permisos_ventas.autorizado is True
    assert permisos_ventas.anular is True
    assert permisos_ventas.actualizar is True
    assert permisos_ventas.autorizar is True
    assert permisos_ventas.bi is True
    assert permisos_ventas.cerrar is True
    assert permisos_ventas.consultar is True
    assert permisos_ventas.crear is True
    assert permisos_ventas.reportes is True
    assert permisos_ventas.validar is True
    assert permisos_ventas.importar is True
    assert permisos_ventas.corregir is True
    assert permisos_ventas.listar is True


def test_permisos_rol_sales_auxiliar():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("ventasj"))
    assert permisos_ventas.autorizado is True
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is True
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is True
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is True
    assert permisos_ventas.crear is True
    assert permisos_ventas.reportes is True
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is True


def test_permisos_rol_sale_auxiliar():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_tesoreria.autorizado is False
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is False
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is False
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is False
    assert permisos_tesoreria.crear is False
    assert permisos_tesoreria.reportes is False
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is False

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("ventasj")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("ventasj"))
    assert permisos_ventas.autorizado is True
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is True
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is True
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is True
    assert permisos_ventas.crear is True
    assert permisos_ventas.reportes is True
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is True


def test_permisos_rol_head_of_treasury():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("tesoreria")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("tesoreria")
    )
    assert permisos_tesoreria.autorizado is True
    assert permisos_tesoreria.anular is True
    assert permisos_tesoreria.actualizar is True
    assert permisos_tesoreria.autorizar is True
    assert permisos_tesoreria.bi is True
    assert permisos_tesoreria.cerrar is True
    assert permisos_tesoreria.consultar is True
    assert permisos_tesoreria.crear is True
    assert permisos_tesoreria.reportes is True
    assert permisos_tesoreria.validar is True
    assert permisos_tesoreria.importar is True
    assert permisos_tesoreria.corregir is True
    assert permisos_tesoreria.listar is True

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("tesoreria")
    )
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("tesoreria")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(
        modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("tesoreria")
    )
    assert permisos_ventas.autorizado is False
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is False
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is False
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is False
    assert permisos_ventas.crear is False
    assert permisos_ventas.reportes is False
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is False


def test_permisos_rol_auxiliar_of_treasury():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("tesoreriaj")
    )
    assert permisos_conta.autorizado is False
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is False
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is False
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is False
    assert permisos_conta.crear is False
    assert permisos_conta.reportes is False
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is False

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("tesoreriaj")
    )
    assert permisos_tesoreria.autorizado is True
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is True
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is True
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is True
    assert permisos_tesoreria.crear is True
    assert permisos_tesoreria.reportes is True
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is True

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("tesoreriaj")
    )
    assert permisos_compras.autorizado is False
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is False
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is False
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is False
    assert permisos_compras.crear is False
    assert permisos_compras.reportes is False
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is False

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("tesoreriaj")
    )
    assert permisos_almacen.autorizado is False
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is False
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is False
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is False
    assert permisos_almacen.crear is False
    assert permisos_almacen.reportes is False
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is False

    # Modulo Ventas
    permisos_ventas = Permisos(
        modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("tesoreriaj")
    )
    assert permisos_ventas.autorizado is False
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is False
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is False
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is False
    assert permisos_ventas.crear is False
    assert permisos_ventas.reportes is False
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is False


def test_permisos_rol_mix():
    # Modulo Contabilidad
    permisos_conta = Permisos(
        modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("pasante")
    )
    assert permisos_conta.autorizado is True
    assert permisos_conta.anular is False
    assert permisos_conta.actualizar is True
    assert permisos_conta.autorizar is False
    assert permisos_conta.bi is True
    assert permisos_conta.cerrar is False
    assert permisos_conta.consultar is True
    assert permisos_conta.crear is True
    assert permisos_conta.reportes is True
    assert permisos_conta.validar is False
    assert permisos_conta.importar is False
    assert permisos_conta.corregir is False
    assert permisos_conta.listar is True

    # Modulo Tesoreria
    permisos_tesoreria = Permisos(
        modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("pasante")
    )
    assert permisos_tesoreria.autorizado is True
    assert permisos_tesoreria.anular is False
    assert permisos_tesoreria.actualizar is True
    assert permisos_tesoreria.autorizar is False
    assert permisos_tesoreria.bi is True
    assert permisos_tesoreria.cerrar is False
    assert permisos_tesoreria.consultar is True
    assert permisos_tesoreria.crear is True
    assert permisos_tesoreria.reportes is True
    assert permisos_tesoreria.validar is False
    assert permisos_tesoreria.importar is False
    assert permisos_tesoreria.corregir is False
    assert permisos_tesoreria.listar is True

    # Modulo Compras
    permisos_compras = Permisos(
        modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("pasante")
    )
    assert permisos_compras.autorizado is True
    assert permisos_compras.anular is False
    assert permisos_compras.actualizar is True
    assert permisos_compras.autorizar is False
    assert permisos_compras.bi is True
    assert permisos_compras.cerrar is False
    assert permisos_compras.consultar is True
    assert permisos_compras.crear is True
    assert permisos_compras.reportes is True
    assert permisos_compras.validar is False
    assert permisos_compras.importar is False
    assert permisos_compras.corregir is False
    assert permisos_compras.listar is True

    # Modulo Almacen
    permisos_almacen = Permisos(
        modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("pasante")
    )
    assert permisos_almacen.autorizado is True
    assert permisos_almacen.anular is False
    assert permisos_almacen.actualizar is True
    assert permisos_almacen.autorizar is False
    assert permisos_almacen.bi is True
    assert permisos_almacen.cerrar is False
    assert permisos_almacen.consultar is True
    assert permisos_almacen.crear is True
    assert permisos_almacen.reportes is True
    assert permisos_almacen.validar is False
    assert permisos_almacen.importar is False
    assert permisos_almacen.corregir is False
    assert permisos_almacen.listar is True

    # Modulo Ventas
    permisos_ventas = Permisos(modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("pasante"))
    assert permisos_ventas.autorizado is True
    assert permisos_ventas.anular is False
    assert permisos_ventas.actualizar is True
    assert permisos_ventas.autorizar is False
    assert permisos_ventas.bi is True
    assert permisos_ventas.cerrar is False
    assert permisos_ventas.consultar is True
    assert permisos_ventas.crear is True
    assert permisos_ventas.reportes is True
    assert permisos_ventas.validar is False
    assert permisos_ventas.importar is False
    assert permisos_ventas.corregir is False
    assert permisos_ventas.listar is True


MODULOS_ = ["accounting", "cash", "buying", "inventory", "sales"]


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
    # Modulo Administrativo
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre("admin"), usuario=obtener_id_usuario_por_nombre("auditor"))
    assert permisos.autorizado is False
    assert permisos.anular is False
    assert permisos.actualizar is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.consultar is False
    assert permisos.crear is False
    assert permisos.reportes is False
    assert permisos.validar is False
    assert permisos.importar is False
    assert permisos.corregir is False
    assert permisos.listar is False


def test_permisos_rol_analista():
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
    # Modulo Administrativo
    permisos = Permisos(modulo=obtener_id_modulo_por_monbre("admin"), usuario=obtener_id_usuario_por_nombre("analista"))
    assert permisos.autorizado is False
    assert permisos.anular is False
    assert permisos.actualizar is False
    assert permisos.autorizar is False
    assert permisos.bi is False
    assert permisos.cerrar is False
    assert permisos.consultar is False
    assert permisos.crear is False
    assert permisos.reportes is False
    assert permisos.validar is False
    assert permisos.importar is False
    assert permisos.corregir is False
    assert permisos.listar is False
