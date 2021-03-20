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

"""
Definicion de base de datos.
El objetivo es que el sistema contable pueda ser desplegado sin tener que depender
de una base de datos especifica, la prioridad en soportar Postresql como base de datos
primaria para entornos multiusuarios y Sqlite como base de datos para entornos de un
solo usuario.
Mysql en su versión comunitaria es una opción secundaria, Mariadb no es un opción debido
a que por el momento no soportan el tipo de datos JSON.
Referencia:
 - https://mariadb.com/kb/en/json-data-type/
"""

from collections import namedtuple
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from cacao_accounting.loggin import log

db = SQLAlchemy()
StatusWeb = namedtuple("StatusWeb", ["color", "texto"])
# pylint: disable=too-few-public-methods
DBVERSION = "0.0.0dev"


class BaseTabla:
    """
    Columnas estandar para todas las tablas de la base de datos.
    """

    # Pistas de auditoria comunes a todas las tablas.
    _fecha_creacion = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    _creado_por = db.Column(db.String(15), nullable=True)
    _fecha_modicacion = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=False)
    _modificado_por = db.Column(db.String(15), nullable=True)


class Metadata(db.Model):
    """
    Informacion basica de la instalacion.
    """

    cacaoversion = db.Column(db.String(50), primary_key=True, nullable=False)
    dbversion = db.Column(db.String(50), primary_key=True, nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.now(), nullable=False, primary_key=True)


class Moneda(db.Model, BaseTabla):
    """
    Una moneda para los registros de la entidad.
    """

    id = db.Column(db.String(5), primary_key=True, nullable=False)
    nombre = db.Column(db.String(75), nullable=False)
    codigo = db.Column(db.Integer(), nullable=True)
    decimales = db.Column(db.Integer(), nullable=True)
    activa = db.Column(db.Boolean, nullable=True)
    predeterminada = db.Column(db.Boolean, nullable=True)


class TasaDeCambio(db.Model, BaseTabla):
    """
    Tasa de conversión entre dos monedas distintas.
    """

    __tablename__ = "tc"
    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(5), db.ForeignKey("moneda.id"), nullable=False)
    destino = db.Column(db.String(5), db.ForeignKey("moneda.id"), nullable=False)
    tasa = db.Column(db.Numeric(), nullable=False)
    fecha = db.Column(db.Date(), nullable=False)


class Usuario(UserMixin, db.Model, BaseTabla):
    """
    Una entidad con acceso al sistema.
    """

    # Información Básica
    id = db.Column(db.String(15), primary_key=True, nullable=False)
    p_nombre = db.Column(db.String(80))
    s_nombre = db.Column(db.String(80))
    p_apellido = db.Column(db.String(80))
    s_apellido = db.Column(db.String(80))
    correo_e = db.Column(db.String(150), unique=True, nullable=True)
    clave_acceso = db.Column(db.LargeBinary(), nullable=False)
    tipo = db.Column(db.String(15))
    activo = db.Column(db.Boolean())
    # Información Complementaria
    genero = db.Column(db.String(10))
    nacimiento = db.Column(db.Date())
    telefono = db.Column(db.String(50))
    # Roles y Permisos
    admin = db.Column(db.Boolean())
    # Si esta columna es tipo JSON, así que debemos seguir el soporte de bases de datos a este
    # tipo de datos
    # Referencia: https://docs.sqlalchemy.org/en/13/core/type_basics.html#sqlalchemy.types.JSON
    # JSON is provided as a facade for vendor-specific JSON types. Since it supports JSON SQL operations,
    # it only works on backends that have an actual JSON type, currently:
    #  - PostgreSQL
    #  - MySQL as of version 5.7 (MariaDB as of the 10.2 series does not)
    #  - SQLite as of version 3.9
    roles = db.Column(db.JSON())


class Modulos(db.Model, BaseTabla):
    """Lista de los modulos del sistema."""

    __table_args__ = (db.UniqueConstraint("id", "modulo", name="modulo_unico"),)
    id = db.Column(db.Integer(), primary_key=True, unique=True, nullable=False)
    modulo = db.Column(db.String(25), unique=True, index=True)
    estandar = db.Column(db.Boolean(), nullable=False)
    habilitado = db.Column(db.Boolean(), nullable=True)


class Entidad(db.Model):
    """
    Una entidad es una unidad de negocios de la que se lleva registros
    en el sistema.
    """

    __table_args__ = (db.UniqueConstraint("id", "razon_social", name="entidad_unica"),)
    # Información legal de la entidad
    id = db.Column(db.String(10), primary_key=True, unique=True, index=True)
    status = db.Column(db.String(50), nullable=True)
    status_web = {
        "predeterminada": StatusWeb(color="Lime", texto="Entidad Predeterminada"),
        "activa": StatusWeb(color="Navy", texto="Entidad Activa"),
        "inactiva": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }
    razon_social = db.Column(db.String(100), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(50))
    id_fiscal = db.Column(db.String(50), unique=True, nullable=False)
    moneda = db.Column(db.String(5), db.ForeignKey("moneda.id"))
    # Individual, Sociedad, Sin Fines de Lucro
    tipo_entidad = db.Column(db.String(50))
    tipo_entidad_lista = [
        "Asociación",
        "Compañia Limitada",
        "Cooperativa",
        "Sociedad Anonima",
        "Organización sin Fines de Lucro",
        "Persona Natural",
    ]
    # Información de contacto
    correo_electronico = db.Column(db.String(50))
    web = db.Column(db.String(50))
    telefono1 = db.Column(db.String(50))
    telefono2 = db.Column(db.String(50))
    fax = db.Column(db.String(50))
    habilitada = db.Column(db.Boolean())
    predeterminada = db.Column(db.Boolean())


class Unidad(db.Model):
    """
    Llamese sucursal, oficina o un aréa operativa una entidad puede tener muchas unidades de negocios.
    """

    __table_args__ = (db.UniqueConstraint("id", "nombre", name="unidad_unica"),)
    # Información legal de la entidad
    id = db.Column(db.String(10), primary_key=True, unique=True, index=True)
    nombre = db.Column(db.String(50), nullable=False)
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.id"))
    correo_electronico = db.Column(db.String(50))
    web = db.Column(db.String(50))
    telefono1 = db.Column(db.String(50))
    telefono2 = db.Column(db.String(50))
    fax = db.Column(db.String(50))
    status = db.Column(db.String(50), nullable=True)
    status_web = {
        "activa": StatusWeb(color="Navy", texto="Entidad Activa"),
        "inactiva": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }


# Bases de la contabilidad
class Cuentas(db.Model):
    """
    La base de contabilidad es el catalogo de cuentas.
    """

    __table_args__ = (db.UniqueConstraint("id", "codigo", name="cta_unica"),)
    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    activa = db.Column(db.Boolean(), index=True)
    # Una cuenta puede estar activa pero deshabilitada temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todas las cuentas deben estan vinculadas a una compañia
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.id"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), unique=True)
    nombre = db.Column(db.String(100))
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(50), db.ForeignKey("cuentas.codigo"), nullable=True)
    # moneda = db.Column(db.String(5), db.ForeignKey("moneda.id"))
    # Activo, Pasivo, Patrimonio, Ingresos, Gastos
    rubro = db.Column(db.String(15), index=True)
    # Efectivo, Cta. Bancaria, Inventario, Por Cobrar, Por Pagar
    # las cuentas de tipo especial no deberan ser afectadas directamente en registros manuales
    # unicamente desde sus respectivo modulos
    tipo = db.Column(db.String(15))


class CentroCosto(db.Model):
    """
    La mejor forma de llegar los registros de una entidad es por Centros de Costos (CC).
    """

    __tablename__ = "cc"
    __table_args__ = (db.UniqueConstraint("id", "nombre", name="cc_unico"),)
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    id = db.Column(
        db.String(50),
        unique=True,
        index=True,
        primary_key=True,
    )
    activa = db.Column(db.Boolean(), index=True)
    predeterminado = db.Column(db.Boolean())
    # Un CC puede estar activo pero deshabilitado temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.id"))
    nombre = db.Column(db.String(100), unique=True)
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(100), db.ForeignKey("cc.nombre"))
    db.UniqueConstraint("nombre")


class Proyecto(db.Model):
    """
    Similar a un Centro de Costo pero con una vida mas efimera y normalmente con un presupuesto
    definido ademas de fechas de inicio y fin.
    """

    __table_args__ = (db.UniqueConstraint("id", "nombre", name="proyecto_unico"),)
    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    activo = db.Column(db.Boolean(), index=True)
    # Un CC puede estar activo pero deshabilitado temporalmente.
    habilitado = db.Column(db.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.id"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), unique=True, index=True)
    nombre = db.Column(db.String(100), unique=True)
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(100), db.ForeignKey("cc.nombre"))
    inicio = db.Column(db.Date())
    fin = db.Column(db.Date())
    finalizado = db.Column(db.Boolean())
    fecha_fin = db.Column(db.Date())
    presupuesto = db.Column(db.Float())
    ejecutado = db.Column(db.Float())


class PeriodoContable(db.Model):
    """
    Todas las transaciones deben estar vinculadas a un periodo contable.
    """

    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.id"))
    nombre = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50))
    habilitada = db.Column(db.Boolean(), index=True)
    inicio = db.Column(db.Date(), nullable=False)
    fin = db.Column(db.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Herramientas auxiliares para verificar la ejecución de la base de datos.
def requiere_migracion_db(app):
    """
    Utilidad para realizar migraciones en la base de datos.
    """
    from cacao_accounting.version import VERSION

    with app.app_context():
        meta = Metadata.query.all()

    migrardb = False
    while migrardb == False:  # noqa: E712
        for i in meta:
            if (i.dbversion == DBVERSION) and (i.cacaoversion == VERSION):
                pass
            else:
                log.info("Se requiere actualizar esquema de base de datos.")
                migrardb = True
        break
    return migrardb


def verifica_coneccion_db(app):
    """
    Verifica si es posible conentarse a la base de datos.
    """
    import time

    with app.app_context():
        __inicio = time.time()
        while (time.time() - __inicio) < 30:
            log.info("Verificando conexión a la base de datos.")
            try:
                Metadata.query.all()
                DB_CONN = True
                log.info("Conexión a la base de datos exitosa.")
                break
            except:  # noqa: E722
                DB_CONN = False
                log.warning("No se pudo establecer conexion a la base de datos.")
            time.sleep(1)
            log.info("Reintentando conectar a la base de datos.")
    return DB_CONN


def inicia_base_de_datos(app):
    """
    Inicia esquema de base datos.
    """
    from cacao_accounting.datos import base_data, demo_data
    from cacao_accounting.metadata import DEVELOPMENT

    with app.app_context():
        log.info("Intentando inicializar base de datos.")
        try:
            db.create_all()
            if DEVELOPMENT:
                base_data(carga_rapida=True)
                demo_data()
                DB_ESQUEMA = True
            else:
                base_data(carga_rapida=False)
                DB_ESQUEMA = True
        except:  # noqa: E722
            log.error("No se pudo iniciliazar esquema de base de datos.")
            DB_ESQUEMA = False
    return DB_ESQUEMA
