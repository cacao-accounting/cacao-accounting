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

# pylint: disable=too-few-public-methods

from collections import namedtuple
from os import environ
from uuid import uuid4
from flask import current_app
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint


db = SQLAlchemy()
StatusWeb = namedtuple("StatusWeb", ["color", "texto"])

DBVERSION = "0.0.0dev"


# <---------------------------------------------------------------------------------------------> #
# Defición de un tipo de columna para almacenar identificadores tipo UUID según el motor de base
# de datos establecido en la configuración.


def obtiene_texto_unico():
    """
    A partir de un código UUID unico aleatorio devuelve una cadena de texto unica
    que se puede usar como identificador interno.
    """
    return str(uuid4())


if environ.get("CACAO_DB", None):
    DB_URI = environ.get("CACAO_DB")
else:
    try:
        DB_URI = current_app.config.get("SQLALCHEMY_DATABASE_URI", None)
    except RuntimeError:
        DB_URI = None


if DB_URI and DB_URI.startswith("postgresql"):
    from sqlalchemy.dialects.postgresql import UUID

    COLUMNA_UUID = db.Column(UUID(as_uuid=False), primary_key=True, nullable=False, default=obtiene_texto_unico)

elif DB_URI and (DB_URI.startswith("mysql") or DB_URI.startswith("mariadb")):
    from sqlalchemy.dialects.mysql import VARCHAR

    COLUMNA_UUID = db.Column(VARCHAR(length=36), primary_key=True, nullable=False, default=obtiene_texto_unico, index=True)

elif DB_URI and DB_URI.startswith("mssql"):
    from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

    COLUMNA_UUID = db.Column(UNIQUEIDENTIFIER(), primary_key=True, nullable=False, default=obtiene_texto_unico)

else:
    from sqlalchemy.types import String

    COLUMNA_UUID = db.Column(String(36), primary_key=True, nullable=False, index=True, default=obtiene_texto_unico)


# <---------------------------------------------------------------------------------------------> #
# Estas clases contienen campos comunes que se pueden reutilizar en otras tablan que deriven de
# ellas.
class BaseTabla:
    """
    Columnas estandar para todas las tablas de la base de datos.
    """

    # Pistas de auditoria comunes a todas las tablas.
    id = COLUMNA_UUID
    creado = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    creado_por = db.Column(db.String(15), nullable=True)
    modificado = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=True)
    modificado_por = db.Column(db.String(15), nullable=True)


class BaseTransaccion(BaseTabla):
    registro = db.Column(db.String(50), nullable=True)
    registro_id = db.Column(db.String(75), nullable=True)
    validado = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=True)
    validado_por = db.Column(db.String(15), nullable=True)
    autorizado = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=True)
    autorizado_por = db.Column(db.String(15), nullable=True)
    anulado = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=True)
    anulado_por = db.Column(db.String(15), nullable=True)
    cerrado = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=True)
    cerrado_por = db.Column(db.String(15), nullable=True)

class BaseTransaccionDetalle(BaseTabla):
    registro_padre = db.Column(db.String(50), nullable=True)
    registro_padre_id = db.Column(db.String(75), nullable=True)
    referencia = db.Column(db.String(50), nullable=True)
    referencia_id = db.Column(db.String(75), nullable=True)


class BaseTercero(BaseTabla):
    """
    Esta es clase contiene campos comunes para terceros, principalmente:
     - Cliente
     - Proveedor
    """

    # Requerisitos minimos para tener crear el registro.
    razon_social = db.Column(db.String(150), nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    # Individual, Sociedad
    tipo = db.Column(db.String(50), nullable=False)
    grupo = db.Column(db.String(50), nullable=False)
    habilitado = db.Column(db.Boolean(), nullable=True)
    identificacion = db.Column(db.String(30), nullable=True)
    id_fiscal = db.Column(db.String(30), nullable=True)


class BaseContacto(BaseTabla):
    tipo = db.Column(db.String(25), nullable=True)
    nombre = db.Column(db.String(50), nullable=True)
    telefono = db.Column(db.String(30), nullable=True)
    celular = db.Column(db.String(30), nullable=True)
    correo_electronico = db.Column(db.String(30), nullable=True)


class BaseDireccion(BaseTabla):
    linea1 = db.Column(db.String(150), nullable=True)
    linea2 = db.Column(db.String(150), nullable=True)
    linea3 = db.Column(db.String(150), nullable=True)
    pais = db.Column(db.String(30), nullable=True)
    estado = db.Column(db.String(50), nullable=True)
    ciudad = db.Column(db.String(50), nullable=True)
    calle = db.Column(db.String(50), nullable=True)
    avenida = db.Column(db.String(50), nullable=True)
    numero = db.Column(db.String(10), nullable=True)
    codigo_postal = db.Column(db.String(30), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Información sobre la instalación actual del sistema.
# https://github.com/python/mypy/issues/8603
class Metadata(db.Model):  # type: ignore[name-defined]
    """
    Informacion basica de la instalacion.
    """

    __table_args__ = (db.UniqueConstraint("cacaoversion", "dbversion", name="rev_unica"),)
    id = COLUMNA_UUID
    cacaoversion = db.Column(db.String(50), nullable=False)
    dbversion = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.now(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de monedas, localización, tasas de cambio y otras configuraciones regionales.
class Moneda(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Una moneda para los registros de la entidad.
    """

    codigo = db.Column(db.String(10), index=True, nullable=False, unique=True)
    nombre = db.Column(db.String(75), nullable=False)
    decimales = db.Column(db.Integer(), nullable=True)
    activa = db.Column(db.Boolean, nullable=True)
    predeterminada = db.Column(db.Boolean, nullable=True)


class TasaDeCambio(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Tasa de conversión entre dos monedas distintas.
    """

    base = db.Column(db.String(10), db.ForeignKey("moneda.codigo"), nullable=False)
    destino = db.Column(db.String(10), db.ForeignKey("moneda.codigo"), nullable=False)
    tasa = db.Column(db.Numeric(), nullable=False)
    fecha = db.Column(db.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de usuario, roles, grupos y permisos.
class Usuario(UserMixin, db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Una entidad con acceso al sistema.
    """

    # Información Básica
    usuario = db.Column(db.String(15), nullable=False)
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


# <---------------------------------------------------------------------------------------------> #
# Administración de módulos del sistema.
class Modulos(db.Model, BaseTabla):  # type: ignore[name-defined]
    """Lista de los modulos del sistema."""

    __table_args__ = (db.UniqueConstraint("id", "modulo", name="modulo_unico"),)
    modulo = db.Column(db.String(25), unique=True, index=True)
    estandar = db.Column(db.Boolean(), nullable=False)
    habilitado = db.Column(db.Boolean(), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Descripción de la estructura funcional de la entidad.
class Entidad(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Una entidad es una unidad de negocios de la que se lleva registros
    en el sistema.
    """

    __table_args__ = (db.UniqueConstraint("id", "razon_social", name="entidad_unica"),)
    # Información legal de la entidad
    entidad = db.Column(db.String(10), unique=True, index=True)
    status = db.Column(db.String(50), nullable=True)
    status_web = {
        "predeterminada": StatusWeb(color="Lime", texto="Entidad Predeterminada"),
        "activa": StatusWeb(color="Navy", texto="Entidad Activa"),
        "inactiva": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }
    razon_social = db.Column(db.String(100), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(50))
    id_fiscal = db.Column(db.String(50), unique=True, nullable=False)
    moneda = db.Column(db.String(10), db.ForeignKey("moneda.codigo"))
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


class Unidad(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Llamese sucursal, oficina o un aréa operativa una entidad puede tener muchas unidades de negocios.
    """

    __table_args__ = (db.UniqueConstraint("id", "nombre", name="unidad_unica"),)
    # Información legal de la entidad
    unidad = db.Column(db.String(10), unique=True, index=True)
    nombre = db.Column(db.String(50), nullable=False)
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.entidad"))
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


class Direcciones(BaseDireccion):
    """
    La entidad y sus diferentes unidades de negocios pueden tener o mas dirección fisicas.
    """


# <---------------------------------------------------------------------------------------------> #
# Bases de la contabilidad
class Cuentas(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    La base de contabilidad es el catalogo de cuentas.
    """

    __table_args__ = (
        db.UniqueConstraint("id"),
        db.UniqueConstraint("entidad", "codigo", name="cta_unica"),
    )
    activa = db.Column(db.Boolean(), index=True)
    # Una cuenta puede estar activa pero deshabilitada temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todas las cuentas deben estan vinculadas a una compañia
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.entidad"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), index=True)
    nombre = db.Column(db.String(100))
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(50), nullable=True)
    moneda = db.Column(db.String(10), db.ForeignKey("moneda.codigo"), nullable=True)
    # Activo, Pasivo, Patrimonio, Ingresos, Gastos
    rubro = db.Column(db.String(15), index=True)
    # Efectivo, Cta. Bancaria, Inventario, Por Cobrar, Por Pagar
    # las cuentas de tipo especial no deberan ser afectadas directamente en registros manuales
    # unicamente desde sus respectivo modulos
    tipo = db.Column(db.String(15))
    status = db.Column(db.String(50), nullable=True)
    status_web = {
        "activa": StatusWeb(color="Lime", texto="Entidad Activa"),
        "inactiva": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }
    UniqueConstraint("entidad", "codigo", name="cta_unica_entidad")


class CentroCosto(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    La mejor forma de llegar los registros de una entidad es por Centros de Costos (CC).
    """

    __table_args__ = (db.UniqueConstraint("entidad", "codigo", name="cc_unico"),)
    activa = db.Column(db.Boolean(), index=True)
    predeterminado = db.Column(db.Boolean())
    # Un CC puede estar activo pero deshabilitado temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.entidad"))
    # Cuenta agrupador o cuenta que recibe movimientos
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(
        db.String(50),
    )
    nombre = db.Column(db.String(100))
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    status_web = {
        "activa": StatusWeb(color="Lime", texto="Entidad Activa"),
        "inactiva": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }
    UniqueConstraint("entidad", "codigo", name="cc_unico_entidad")


class Proyecto(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Similar a un Centro de Costo pero con una vida mas efimera y normalmente con un presupuesto
    definido ademas de fechas de inicio y fin.
    """

    __table_args__ = (db.UniqueConstraint("entidad", "codigo", name="py_unico"),)
    # Un centro_costo puede estar activo pero deshabilitado temporalmente.
    habilitado = db.Column(db.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entidad = db.Column(db.String(10), db.ForeignKey("entidad.entidad"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), unique=True, index=True)
    nombre = db.Column(db.String(100), unique=True)
    fechainicio = db.Column(db.Date())
    fechafin = db.Column(db.Date())
    presupuesto = db.Column(db.Float())
    status = db.Column(db.String(50), nullable=True)
    status_web = {
        "abierto": StatusWeb(color="Lime", texto="Entidad Activa"),
        "inactiva": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }
    UniqueConstraint("entidad", "codigo", name="proyecto_unica_entidad")


class PeriodoContable(db.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Todas las transaciones deben estar vinculadas a un periodo contable.
    """

    entidad = db.Column(db.String(10), db.ForeignKey("entidad.entidad"))
    nombre = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50))
    habilitada = db.Column(db.Boolean(), index=True)
    inicio = db.Column(db.Date(), nullable=False)
    fin = db.Column(db.Date(), nullable=False)
    status_web = {
        "actual": StatusWeb(color="DodgerBlue", texto="Entidad Activa"),
        "abierto": StatusWeb(color="Lime", texto="Entidad Activa"),
        "cerrado": StatusWeb(color="LightSlateGray", texto="Entidad Inactiva"),
    }


# <---------------------------------------------------------------------------------------------> #
# Cuentas por Cobrar
class Cliente(db.Model, BaseTercero):  # type: ignore[name-defined]
    pass


class ClienteDireccion(db.Model, BaseDireccion):  # type: ignore[name-defined]
    pass


class ClienteContacto(db.Model, BaseContacto):  # type: ignore[name-defined]
    pass


# <---------------------------------------------------------------------------------------------> #
# Cuentas por Pagar
class Proveedor(db.Model, BaseTercero):  # type: ignore[name-defined]
    pass


class ProveedorDireccion(db.Model, BaseDireccion):  # type: ignore[name-defined]
    pass


class ProveedorContacto(db.Model, BaseContacto):  # type: ignore[name-defined]
    pass
