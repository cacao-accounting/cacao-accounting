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
# pylint: disable=no-member

from collections import namedtuple
from os import environ
from typing import Dict
from uuid import uuid4
from flask import current_app
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint


database = SQLAlchemy()


DBVERSION = "0.0.0dev"

StatusWeb = namedtuple("StatusWeb", ["color", "leyenda"])

STATUS: Dict[str, StatusWeb] = {
    "abierto": StatusWeb(color="Lime", leyenda="Abierto"),
    "activo": StatusWeb(color="Navy", leyenda="Activo"),
    "actual": StatusWeb(color="DodgerBlue", leyenda="Actual"),
    "atrasado": StatusWeb(color="DodgerBlue", leyenda="Atrasado"),
    "cancelado": StatusWeb(color="DodgerBlue", leyenda="Cancelado"),
    "cerrado": StatusWeb(color="LightSlateGray", leyenda="Cerrado"),
    "inactivo": StatusWeb(color="LightSlateGray", leyenda="Inactivo"),
    "indefinido": StatusWeb(color="LightSlateGray", leyenda="Status no definido"),
    "inhabilitado": StatusWeb(color="LightSlateGray", leyenda="Inhabilitado"),
    "habilitado": StatusWeb(color="LightSlateGray", leyenda="Habilitado"),
    "pagado": StatusWeb(color="LightSlateGray", leyenda="Pagado"),
    "predeterminado": StatusWeb(color="Lime", leyenda="Predeterminado"),
}

# <---------------------------------------------------------------------------------------------> #
# Defición de un tipo de columna para almacenar identificadores tipo UUID según el motor de base
# de datos establecido en la configuración.


def obtiene_texto_unico() -> str:
    """Genera un texto unico en base a una UUID."""
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

    TIPO_UUID = UUID(as_uuid=False)
    COLUMNA_UUID = database.Column(TIPO_UUID, primary_key=True, nullable=False, default=obtiene_texto_unico)

elif DB_URI and (DB_URI.startswith("mysql") or DB_URI.startswith("mariadb")):
    from sqlalchemy.dialects.mysql import VARCHAR

    TIPO_UUID = VARCHAR(length=36)
    COLUMNA_UUID = database.Column(TIPO_UUID, primary_key=True, nullable=False, default=obtiene_texto_unico, index=True)

elif DB_URI and DB_URI.startswith("mssql"):
    from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

    TIPO_UUID = UNIQUEIDENTIFIER()
    COLUMNA_UUID = database.Column(TIPO_UUID, primary_key=True, nullable=False, default=obtiene_texto_unico)

else:
    from sqlalchemy.types import String

    TIPO_UUID = String(36)
    COLUMNA_UUID = database.Column(TIPO_UUID, primary_key=True, nullable=False, index=True, default=obtiene_texto_unico)


# <---------------------------------------------------------------------------------------------> #
# Estas clases contienen campos comunes que se pueden reutilizar en otras tablan que deriven de
# ellas.
class BaseTabla:
    """Columnas estandar para todas las tablas de la base de datos."""

    # Pistas de auditoria comunes a todas las tablas.
    id = COLUMNA_UUID
    status = database.Column(database.String(50), nullable=True)
    creado = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    creado_por = database.Column(database.String(15), nullable=True)
    modificado = database.Column(database.DateTime, default=database.func.now(), onupdate=database.func.now(), nullable=True)
    modificado_por = database.Column(database.String(15), nullable=True)


class BaseTransaccion(BaseTabla):
    """Base para crear transacciones en la entidad."""

    registro = database.Column(database.String(50), nullable=True)
    registro_id = database.Column(database.String(75), nullable=True)
    validado = database.Column(database.DateTime, default=database.func.now(), onupdate=database.func.now(), nullable=True)
    validado_por = database.Column(database.String(15), nullable=True)
    autorizado = database.Column(database.DateTime, default=database.func.now(), onupdate=database.func.now(), nullable=True)
    autorizado_por = database.Column(database.String(15), nullable=True)
    anulado = database.Column(database.DateTime, default=database.func.now(), onupdate=database.func.now(), nullable=True)
    anulado_por = database.Column(database.String(15), nullable=True)
    cerrado = database.Column(database.DateTime, default=database.func.now(), onupdate=database.func.now(), nullable=True)
    cerrado_por = database.Column(database.String(15), nullable=True)


class BaseTransaccionDetalle(BaseTabla):
    """Base para crear transacciones en la entidad."""

    registro_padre = database.Column(database.String(50), nullable=True)
    registro_padre_id = database.Column(database.String(75), nullable=True)
    referencia = database.Column(database.String(50), nullable=True)
    referencia_id = database.Column(database.String(75), nullable=True)


class BaseTercero(BaseTabla):
    """Base para crear terceros en la entidad."""

    # Requerisitos minimos para tener crear el registro.
    razon_social = database.Column(database.String(150), nullable=False)
    nombre = database.Column(database.String(150), nullable=False)
    # Individual, Sociedad
    tipo = database.Column(database.String(50), nullable=False)
    grupo = database.Column(database.String(50), nullable=False)
    habilitado = database.Column(database.Boolean(), nullable=True)
    identificacion = database.Column(database.String(30), nullable=True)
    id_fiscal = database.Column(database.String(30), nullable=True)


class BaseContacto(BaseTabla):
    """Clase base para la creación de contactos."""

    tipo = database.Column(database.String(25), nullable=True)
    nombre = database.Column(database.String(50), nullable=True)
    telefono = database.Column(database.String(30), nullable=True)
    celular = database.Column(database.String(30), nullable=True)
    correo_electronico = database.Column(database.String(30), nullable=True)


class BaseDireccion(BaseTabla):
    """Clase base para la creación de direcciones."""

    linea1 = database.Column(database.String(150), nullable=True)
    linea2 = database.Column(database.String(150), nullable=True)
    linea3 = database.Column(database.String(150), nullable=True)
    pais = database.Column(database.String(30), nullable=True)
    estado = database.Column(database.String(50), nullable=True)
    ciudad = database.Column(database.String(50), nullable=True)
    calle = database.Column(database.String(50), nullable=True)
    avenida = database.Column(database.String(50), nullable=True)
    numero = database.Column(database.String(10), nullable=True)
    codigo_postal = database.Column(database.String(30), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Información sobre la instalación actual del sistema.
# https://github.com/python/mypy/issues/8603
class Metadata(database.Model):  # type: ignore[name-defined]
    """Informacion basica de la instalacion."""

    __table_args__ = (database.UniqueConstraint("cacaoversion", "dbversion", name="rev_unica"),)
    id = COLUMNA_UUID
    cacaoversion = database.Column(database.String(50), nullable=False)
    dbversion = database.Column(database.String(50), nullable=False)
    fecha = database.Column(database.DateTime, default=database.func.now(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de monedas, localización, tasas de cambio y otras configuraciones regionales.
class Moneda(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Una moneda para los registros de la entidad."""

    codigo = database.Column(database.String(10), index=True, nullable=False, unique=True)
    nombre = database.Column(database.String(75), nullable=False)
    decimales = database.Column(database.Integer(), nullable=True)
    activa = database.Column(database.Boolean, nullable=True)
    predeterminada = database.Column(database.Boolean, nullable=True)


class TasaDeCambio(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Tasa de conversión entre dos monedas distintas."""

    base = database.Column(database.String(10), database.ForeignKey("moneda.codigo"), nullable=False)
    destino = database.Column(database.String(10), database.ForeignKey("moneda.codigo"), nullable=False)
    tasa = database.Column(database.Numeric(), nullable=False)
    fecha = database.Column(database.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de usuario, roles, grupos y permisos.
class Usuario(UserMixin, database.Model, BaseTabla):  # type: ignore[name-defined]
    """Una entidad con acceso al sistema."""

    # Información Básica
    usuario = database.Column(database.String(15), nullable=False)
    p_nombre = database.Column(database.String(80))
    s_nombre = database.Column(database.String(80))
    p_apellido = database.Column(database.String(80))
    s_apellido = database.Column(database.String(80))
    correo_e = database.Column(database.String(150), unique=True, nullable=True)
    clave_acceso = database.Column(database.LargeBinary(), nullable=False)
    tipo = database.Column(database.String(15))
    activo = database.Column(database.Boolean())
    # Información Complementaria
    genero = database.Column(database.String(10))
    nacimiento = database.Column(database.Date())
    telefono = database.Column(database.String(50))


class Roles(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles para las administración de permisos de usuario."""

    name = database.Column(database.String(50), nullable=False, unique=True)
    detalle = database.Column(database.String(100), nullable=False, unique=True)


class RolesPermisos(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Los roles definen una cantidad de permisos."""

    rol_id = database.Column(TIPO_UUID, database.ForeignKey("roles.id"))
    modulo_id = database.Column(TIPO_UUID, database.ForeignKey("modulos.id"))
    # Usuario tiene acceso al múdulo
    acceso = database.Column(database.Boolean, nullable=False, default=False)
    # Usuario puede realizar determinadas acciones en el modulogit
    actualizar = database.Column(database.Boolean, nullable=False, default=False)
    anular = database.Column(database.Boolean, nullable=False, default=False)
    autorizar = database.Column(database.Boolean, nullable=False, default=False)
    bi = database.Column(database.Boolean, nullable=False, default=False)
    cerrar = database.Column(database.Boolean, nullable=False, default=False)
    configurar = database.Column(database.Boolean, nullable=False, default=False)
    consultar = database.Column(database.Boolean, nullable=False, default=False)
    corregir = database.Column(database.Boolean, nullable=False, default=False)
    crear = database.Column(database.Boolean, nullable=False, default=False)
    editar = database.Column(database.Boolean, nullable=False, default=False)
    eliminar = database.Column(database.Boolean, nullable=False, default=False)
    importar = database.Column(database.Boolean, nullable=False, default=False)
    listar = database.Column(database.Boolean, nullable=False, default=False)
    reportes = database.Column(database.Boolean, nullable=False, default=False)
    solicitar = database.Column(database.Boolean, nullable=False, default=False)
    validar = database.Column(database.Boolean, nullable=False, default=False)
    validar_solicitud = database.Column(database.Boolean, nullable=False, default=False)


class RolesUsuario(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles dan permisos a los usuarios del sistema."""

    user_id = database.Column(TIPO_UUID, database.ForeignKey("usuario.id"))
    role_id = database.Column(TIPO_UUID, database.ForeignKey("roles.id"))
    activo = database.Column(database.Boolean, nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Administración de módulos del sistema.
class Modulos(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Lista de los modulos del sistema."""

    __table_args__ = (database.UniqueConstraint("modulo", name="modulo_unico"),)
    modulo = database.Column(database.String(50), unique=True, index=True)
    estandar = database.Column(database.Boolean(), nullable=False)
    habilitado = database.Column(database.Boolean(), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Descripción de la estructura funcional de la entidad.
class Entidad(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Todas las transacciones se deben grabar a una entidad."""

    __table_args__ = (database.UniqueConstraint("id", "razon_social", name="entidad_unica"),)
    # Información legal de la entidad
    entidad = database.Column(database.String(10), unique=True, index=True)
    status = database.Column(database.String(50), nullable=True)
    razon_social = database.Column(database.String(100), unique=True, nullable=False)
    nombre_comercial = database.Column(database.String(50))
    id_fiscal = database.Column(database.String(50), unique=True, nullable=False)
    moneda = database.Column(database.String(10), database.ForeignKey("moneda.codigo"))
    # Individual, Sociedad, Sin Fines de Lucro
    tipo_entidad = database.Column(database.String(50))
    tipo_entidad_lista = [
        "Asociación",
        "Compañia Limitada",
        "Cooperativa",
        "Sociedad Anonima",
        "Organización sin Fines de Lucro",
        "Persona Natural",
    ]
    # Información de contacto
    correo_electronico = database.Column(database.String(50))
    web = database.Column(database.String(50))
    telefono1 = database.Column(database.String(50))
    telefono2 = database.Column(database.String(50))
    fax = database.Column(database.String(50))
    habilitada = database.Column(database.Boolean())
    predeterminada = database.Column(database.Boolean())


class Unidad(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Llamese sucursal, oficina o un aréa operativa una entidad puede tener muchas unidades de negocios."""

    __table_args__ = (database.UniqueConstraint("id", "nombre", name="unidad_unica"),)
    # Información legal de la entidad
    unidad = database.Column(database.String(10), unique=True, index=True)
    nombre = database.Column(database.String(50), nullable=False)
    entidad = database.Column(database.String(10), database.ForeignKey("entidad.entidad"))
    correo_electronico = database.Column(database.String(50))
    web = database.Column(database.String(50))
    telefono1 = database.Column(database.String(50))
    telefono2 = database.Column(database.String(50))
    fax = database.Column(database.String(50))


class Direcciones(BaseDireccion):
    """La entidad y sus diferentes unidades de negocios pueden tener o mas dirección fisicas."""


# <---------------------------------------------------------------------------------------------> #
# Bases de la contabilidad
class Cuentas(database.Model, BaseTabla):  # type: ignore[name-defined]
    """La base de contabilidad es el catalogo de cuentas."""

    __table_args__ = (
        database.UniqueConstraint("id"),
        database.UniqueConstraint("entidad", "codigo", name="cta_unica"),
    )
    activa = database.Column(database.Boolean(), index=True)
    # Una cuenta puede estar activa pero deshabilitada temporalmente.
    habilitada = database.Column(database.Boolean(), index=True)
    # Todas las cuentas deben estan vinculadas a una compañia
    entidad = database.Column(database.String(10), database.ForeignKey("entidad.entidad"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = database.Column(database.String(50), index=True)
    nombre = database.Column(database.String(100))
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = database.Column(database.Boolean())
    padre = database.Column(database.String(50), nullable=True)
    moneda = database.Column(database.String(10), database.ForeignKey("moneda.codigo"), nullable=True)
    # Activo, Pasivo, Patrimonio, Ingresos, Gastos
    rubro = database.Column(database.String(15), index=True)
    # Efectivo, Cta. Bancaria, Inventario, Por Cobrar, Por Pagar
    tipo = database.Column(database.String(50))
    alternativo_codigo = database.Column(database.String(10), index=True)
    alternativo = database.Column(database.String(50), index=True)
    fiscal_codigo = database.Column(database.String(50), index=True)
    fiscal = database.Column(database.String(100))
    UniqueConstraint("entidad", "codigo", name="cta_unica_entidad")


class CentroCosto(database.Model, BaseTabla):  # type: ignore[name-defined]
    """La mejor forma de llegar los registros de una entidad es por Centros de Costos (CC)."""

    __table_args__ = (database.UniqueConstraint("entidad", "codigo", name="cc_unico"),)
    activa = database.Column(database.Boolean(), index=True)
    predeterminado = database.Column(database.Boolean())
    # Un CC puede estar activo pero deshabilitado temporalmente.
    habilitada = database.Column(database.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entidad = database.Column(database.String(10), database.ForeignKey("entidad.entidad"))
    # Cuenta agrupador o cuenta que recibe movimientos
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = database.Column(
        database.String(50),
    )
    nombre = database.Column(database.String(100))
    grupo = database.Column(database.Boolean())
    padre = database.Column(database.String(100), nullable=True)
    UniqueConstraint("entidad", "codigo", name="cc_unico_entidad")


class Proyecto(database.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Clase para la adminstración de proyectos.

    Similar a un Centro de Costo pero con una vida mas efimera y normalmente con un presupuesto
    definido ademas de fechas de inicio y fin.
    """

    __table_args__ = (database.UniqueConstraint("entidad", "codigo", name="py_unico"),)
    # Un centro_costo puede estar activo pero deshabilitado temporalmente.
    habilitado = database.Column(database.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entidad = database.Column(database.String(10), database.ForeignKey("entidad.entidad"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = database.Column(database.String(50), unique=True, index=True)
    nombre = database.Column(database.String(100), unique=True)
    fechainicio = database.Column(database.Date())
    fechafin = database.Column(database.Date())
    presupuesto = database.Column(database.Float())
    UniqueConstraint("entidad", "codigo", name="proyecto_unica_entidad")


class PeriodoContable(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Todas las transaciones deben estar vinculadas a un periodo contable."""

    entidad = database.Column(database.String(10), database.ForeignKey("entidad.entidad"))
    nombre = database.Column(database.String(50), nullable=False)
    status = database.Column(database.String(50))
    habilitada = database.Column(database.Boolean(), index=True)
    inicio = database.Column(database.Date(), nullable=False)
    fin = database.Column(database.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Cuentas por Cobrar
class Cliente(database.Model, BaseTercero):  # type: ignore[name-defined]
    """Clase base para la administración de clientes."""


class ClienteDireccion(database.Model, BaseDireccion):  # type: ignore[name-defined]
    """Un cliente puede tener varias direcciones."""


class ClienteContacto(database.Model, BaseContacto):  # type: ignore[name-defined]
    """Un cliente puede tener varios contactos."""


# <---------------------------------------------------------------------------------------------> #
# Cuentas por Pagar
class Proveedor(database.Model, BaseTercero):  # type: ignore[name-defined]
    """Clase base para la administración de proveedores."""


class ProveedorDireccion(database.Model, BaseDireccion):  # type: ignore[name-defined]
    """Un proveedor puede tener varias direcciones."""


class ProveedorContacto(database.Model, BaseContacto):  # type: ignore[name-defined]
    """Un proveedor puede tener varios contactos."""
