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


def test_permisos_rol_admin():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
        # Modulo Contabilidad
        permisos_conta = Permisos(
            modulo=obtener_id_modulo_por_monbre("accounting"), usuario=obtener_id_usuario_por_nombre("cacao")
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

        # Modulo Tesoreria
        permisos_tesoreria = Permisos(
            modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("cacao")
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

        # Modulo Compras
        permisos_compras = Permisos(
            modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("cacao")
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

        # Modulo Almacen
        permisos_almacen = Permisos(
            modulo=obtener_id_modulo_por_monbre("inventory"), usuario=obtener_id_usuario_por_nombre("cacao")
        )
        assert permisos_almacen.autorizado is True
        assert permisos_almacen.anular is True
        assert permisos_almacen.actualizar is True
        assert permisos_almacen.autorizar is True
        assert permisos_almacen.bi is True
        assert permisos_almacen.cerrar is True
        assert permisos_almacen.consultar is True
        assert permisos_almacen.crear is True
        assert permisos_almacen.reportes is True
        assert permisos_almacen.validar is True

        # Modulo Ventas
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("cacao")
        )
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


def test_permisos_rol_purchase_manager():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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
        # Modulo Ventas
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("compras")
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


def test_permisos_rol_purchase_auxiliar():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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

        # Modulo Ventas
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("comprasj")
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


def test_permisos_rol_accounting_manager():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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


def test_permisos_rol_accounting_auxiliar():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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


def test_permisos_rol_sales_manager():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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

        # Modulo Tesoreria
        permisos_tesoreria = Permisos(
            modulo=obtener_id_modulo_por_monbre("cash"), usuario=obtener_id_usuario_por_nombre("ventas")
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

        # Modulo Compras
        permisos_compras = Permisos(
            modulo=obtener_id_modulo_por_monbre("buying"), usuario=obtener_id_usuario_por_nombre("ventas")
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

        # Modulo Ventas
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("ventas")
        )
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


def test_permisos_rol_sales_auxiliar():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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

        # Modulo Ventas
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("ventasj")
        )
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


def test_permisos_rol_sale_auxiliar():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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

        # Modulo Ventas
        permisos_ventas = Permisos(
            modulo=obtener_id_modulo_por_monbre("sales"), usuario=obtener_id_usuario_por_nombre("ventasj")
        )
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


def test_permisos_rol_head_of_treasury():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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


def test_permisos_rol_auxiliar_of_treasury():
    app = app_factory(CONFIG)
    with app.app_context():
        db.drop_all()
        db.create_all()
        base_data()
        dev_data()
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
