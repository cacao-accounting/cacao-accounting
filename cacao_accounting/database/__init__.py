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

"""Definicion de base de datos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from collections import namedtuple
from typing import Dict

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from cuid2 import Cuid
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from ulid import ULID

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------

# < --------------------------------------------------------------------------------------------- >
# Se utiliza en idioma ingles para facilitar el acceso a usuarios de herramientas de BI.
# < --------------------------------------------------------------------------------------------- >

# < --------------------------------------------------------------------------------------------- >
# Definición principal de la clase del ORM.
# < --------------------------------------------------------------------------------------------- >
database = SQLAlchemy()


# < --------------------------------------------------------------------------------------------- >
# Definición central de status web.
# < --------------------------------------------------------------------------------------------- >
StatusWeb = namedtuple("StatusWeb", ["color", "leyenda"])

STATUS: Dict[str, StatusWeb] = {
    "open": StatusWeb(color="LimeGreen", leyenda="Abierto"),
    "active": StatusWeb(color="LightSeaGreen", leyenda="Activo"),
    "current": StatusWeb(color="DodgerBlue", leyenda="Actual"),
    "canceled": StatusWeb(color="SlateGray", leyenda="Actual"),
    "overdue": StatusWeb(color="OrangeRed", leyenda="Atrasado"),
    "closed": StatusWeb(color="Silver", leyenda="Cerrado"),
    "inactive": StatusWeb(color="LightSlateGray", leyenda="Inactivo"),
    "indeterminate": StatusWeb(color="WhiteSmoke", leyenda="Status no definido"),
    "disabled": StatusWeb(color="GhostWhite", leyenda="Inhabilitado"),
    "enabled": StatusWeb(color="PaleGreen", leyenda="Habilitado"),
    "paid": StatusWeb(color="SeaGreen", leyenda="Pagado"),
    "default": StatusWeb(color="Goldenrod", leyenda="Predeterminado"),
    "applied": StatusWeb(color="Green", leyenda="Predeterminado"),
}

# <---------------------------------------------------------------------------------------------> #
# Textos unicos
# <---------------------------------------------------------------------------------------------> #


def obtiene_texto_unico() -> str:
    """Genera un texto unico en base a ULID."""
    # Genera un id unico de 26 caracteres
    # Es ID son URL SAFE y se utilizan en los registros principales
    return str(ULID())


def obtiene_texto_unico_cuid2() -> str:
    """Genera un texto unico en base a CUID2."""
    # Genera un id unico de 10 caractes
    # Se utiliza para los registros detalle, principalmente las entradas del mayor general
    GENERATOR: Cuid = Cuid(length=10)

    return str(GENERATOR.generate())


# <---------------------------------------------------------------------------------------------> #
# Estas clases contienen campos comunes que se pueden reutilizar en otras tablan que deriven de
# ellas.
# <---------------------------------------------------------------------------------------------> #
class BaseTabla:
    """Columnas estandar para todas las tablas de la base de datos."""

    # Pistas de auditoria comunes a todas las tablas.
    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    status = database.Column(database.String(50), nullable=True)
    created = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    created_by = database.Column(database.String(15), nullable=True)
    modified = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    modified_by = database.Column(database.String(15), nullable=True)


class BaseTransaccion(BaseTabla):
    """Base para crear transacciones en la entidad."""

    canceled = database.Column(
        database.DateTime,
        nullable=True,
    )
    canceled_by = database.Column(database.String(15), nullable=True)
    applied = database.Column(
        database.DateTime,
        nullable=True,
    )
    applied_por = database.Column(database.String(15), nullable=True)
    canceled = database.Column(
        database.DateTime,
        nullable=True,
    )
    canceled_by = database.Column(database.String(15), nullable=True)
    serie = database.Column(database.String(10), nullable=True)
    sequential = database.Column(database.Integer(), nullable=True)
    sequential_id = database.Column(database.String(10), nullable=True)
    memo = database.Column(database.String(200), nullable=True)


class BaseTercero(BaseTabla):
    """Base para crear terceros en la entidad."""

    # Requerisitos minimos para tener crear el registro.
    name = database.Column(database.String(150), nullable=False)
    comercial_name = database.Column(database.String(150), nullable=False)
    # Individual, Sociedad
    clasification = database.Column(database.String(50), nullable=False)
    group = database.Column(database.String(50), nullable=False)
    enabled = database.Column(database.Boolean(), nullable=True)
    id_ = database.Column(database.String(30), nullable=True)
    tax_id = database.Column(database.String(30), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Administración de monedas, localización, tasas de cambio y otras configuraciones regionales.
class Currency(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Una moneda para los registros de la entidad."""

    code = database.Column(database.String(10), index=True, nullable=False, unique=True)
    name = database.Column(database.String(75), nullable=False)
    decimals = database.Column(database.Integer(), nullable=True)
    active = database.Column(database.Boolean, nullable=True)
    default = database.Column(database.Boolean, nullable=True)


class ExchangeRate(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Tasa de conversión entre dos monedas distintas."""

    origin = database.Column(database.String(10), database.ForeignKey("currency.code"), nullable=False)
    destination = database.Column(database.String(10), database.ForeignKey("currency.code"), nullable=False)
    rate = database.Column(database.Numeric(), nullable=False)
    date = database.Column(database.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de usuario, roles, grupos y permisos.
class User(UserMixin, database.Model, BaseTabla):  # type: ignore[name-defined]
    """Una entidad con acceso al sistema."""

    # Información Básica
    user = database.Column(database.String(15), nullable=False)
    name = database.Column(database.String(80))
    name2 = database.Column(database.String(80))
    last_name = database.Column(database.String(80))
    last_name2 = database.Column(database.String(80))
    e_mail = database.Column(database.String(150), unique=True, nullable=True)
    password = database.Column(database.LargeBinary(), nullable=False)
    classification = database.Column(database.String(15))
    active = database.Column(database.Boolean())
    # Información Complementaria
    genre = database.Column(database.String(10))
    birthday = database.Column(database.Date())
    phone = database.Column(database.String(50))
    # Api rest auth
    token = None


class Roles(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles para las administración de permisos de usuario."""

    name = database.Column(database.String(50), nullable=False, unique=True)
    note = database.Column(database.String(100), nullable=False, unique=True)


class RolesAccess(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Los roles definen una cantidad de permisos."""

    rol_id = database.Column(database.String(26), database.ForeignKey("roles.id"))
    module_id = database.Column(database.String(26), database.ForeignKey("modules.id"))
    # Usuario tiene acceso al múdulo
    access = database.Column(database.Boolean, nullable=False, default=False)
    # Usuario puede realizar determinadas acciones en el modulogit
    update = database.Column(database.Boolean, nullable=False, default=False)
    set_null = database.Column(database.Boolean, nullable=False, default=False)
    approve = database.Column(database.Boolean, nullable=False, default=False)
    bi = database.Column(database.Boolean, nullable=False, default=False)
    close = database.Column(database.Boolean, nullable=False, default=False)
    setup = database.Column(database.Boolean, nullable=False, default=False)
    view = database.Column(database.Boolean, nullable=False, default=False)
    update = database.Column(database.Boolean, nullable=False, default=False)
    create = database.Column(database.Boolean, nullable=False, default=False)
    edit = database.Column(database.Boolean, nullable=False, default=False)
    delete = database.Column(database.Boolean, nullable=False, default=False)
    import_ = database.Column(database.Boolean, nullable=False, default=False)
    report = database.Column(database.Boolean, nullable=False, default=False)
    request = database.Column(database.Boolean, nullable=False, default=False)
    validate = database.Column(database.Boolean, nullable=False, default=False)


class RolesUser(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles dan permisos a los usuarios del sistema."""

    user_id = database.Column(database.String(26), database.ForeignKey("user.id"))
    role_id = database.Column(database.String(26), database.ForeignKey("roles.id"))
    active = database.Column(database.Boolean, nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Administración de módulos del sistema.
class Modules(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Lista de los modulos del sistema."""

    __table_args__ = (database.UniqueConstraint("module", name="modulo_unico"),)
    module = database.Column(database.String(50), unique=True, index=True)
    default = database.Column(database.Boolean(), nullable=False)
    enabled = database.Column(database.Boolean(), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Descripción de la estructura funcional de la entidad.
class Entity(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Todas las transacciones se deben grabar a una entidad."""

    __table_args__ = (database.UniqueConstraint("id", "company_name", name="entidad_unica"),)
    # Información legal de la entidad
    code = database.Column(database.String(10), unique=True, index=True)
    status = database.Column(database.String(50), nullable=True)
    company_name = database.Column(database.String(100), unique=True, nullable=False)
    name = database.Column(database.String(50))
    tax_id = database.Column(database.String(50), unique=True, nullable=False)
    currency = database.Column(database.String(10), database.ForeignKey("currency.code"))
    # Individual, Sociedad, Sin Fines de Lucro
    entity_type = database.Column(database.String(50))
    tipo_entidad_lista = [
        "Asociación",
        "Compañia Limitada",
        "Cooperativa",
        "Sociedad Anonima",
        "Organización sin Fines de Lucro",
        "Persona Natural",
    ]
    # Información de contacto
    e_mail = database.Column(database.String(50))
    web = database.Column(database.String(50))
    phone1 = database.Column(database.String(50))
    phone2 = database.Column(database.String(50))
    fax = database.Column(database.String(50))
    enabled = database.Column(database.Boolean())
    default = database.Column(database.Boolean())


class Unit(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Llamese sucursal, oficina o un aréa operativa una entidad puede tener muchas unidades de negocios."""

    __table_args__ = (database.UniqueConstraint("id", "name", name="unidad_unica"),)
    # Información legal de la entidad
    code = database.Column(database.String(10), unique=True, index=True)
    name = database.Column(database.String(50), nullable=False)
    entity = database.Column(database.String(10), database.ForeignKey("entity.code"))


# <---------------------------------------------------------------------------------------------> #
# Bases de la contabilidad
class Accounts(database.Model, BaseTabla):  # type: ignore[name-defined]
    """La base de contabilidad es el catalogo de cuentas."""

    __table_args__ = (database.UniqueConstraint("entity", "code", name="cta_unica"),)
    active = database.Column(database.Boolean(), index=True)
    # Una cuenta puede estar activa pero deshabilitada temporalmente.
    enabled = database.Column(database.Boolean(), index=True)
    # Todas las cuentas deben estan vinculadas a una compañia
    entity = database.Column(database.String(10), database.ForeignKey("entity.code"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    code = database.Column(database.String(50), index=True)
    name = database.Column(database.String(100))
    # Cuenta agrupador o cuenta que recibe movimientos
    group = database.Column(database.Boolean())
    parent = database.Column(database.String(50), nullable=True)
    currency = database.Column(database.String(10), database.ForeignKey("currency.code"), nullable=True)
    # Activo, Pasivo, Patrimonio, Ingresos, Gastos
    clasification = database.Column(database.String(15), index=True)
    # Efectivo, Cta. Bancaria, Inventario, Por Cobrar, Por Pagar
    type_ = database.Column(database.String(50))
    UniqueConstraint("entity", "code", name="cta_unica_entidad")


class CostCenter(database.Model, BaseTabla):  # type: ignore[name-defined]
    """La mejor forma de llegar los registros de una entidad es por Centros de Costos (CC)."""

    __table_args__ = (database.UniqueConstraint("entity", "code", name="cc_unico"),)
    active = database.Column(database.Boolean(), index=True)
    default = database.Column(database.Boolean())
    # Un CC puede estar activo pero deshabilitado temporalmente.
    enabled = database.Column(database.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entity = database.Column(database.String(10), database.ForeignKey("entity.code"))
    code = database.Column(
        database.String(10),
    )
    name = database.Column(database.String(100))
    group = database.Column(database.Boolean())
    parent = database.Column(database.String(100), nullable=True)
    UniqueConstraint("entity", "code", name="cc_unico_entidad")


class Project(database.Model, BaseTabla):  # type: ignore[name-defined]
    """
    Clase para la adminstración de proyectos.

    Similar a un Centro de Costo pero con una vida mas efimera y normalmente con un presupuesto
    definido ademas de fechas de inicio y fin.
    """

    __table_args__ = (database.UniqueConstraint("entity", "code", name="py_unico"),)
    # Un centro_costo puede estar activo pero deshabilitado temporalmente.
    enabled = database.Column(database.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
    entity = database.Column(database.String(10), database.ForeignKey("entity.code"))
    code = database.Column(database.String(10), unique=True, index=True)
    name = database.Column(database.String(100))
    start = database.Column(database.Date())
    end = database.Column(database.Date())
    budget = database.Column(database.Float())
    UniqueConstraint("entity", "code", name="proyecto_unica_entidad")


class AccountingPeriod(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Todas las transaciones deben estar vinculadas a un periodo contable."""

    entity = database.Column(database.String(10), database.ForeignKey("entity.code"))
    name = database.Column(database.String(50), nullable=False)
    status = database.Column(database.String(50))
    enabled = database.Column(database.Boolean(), index=True)
    start = database.Column(database.Date(), nullable=False)
    end = database.Column(database.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Un mismo documento puede tener varias series para numerarlos


class Serie(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Serie para numerar nuevas transacciones."""

    entity = database.Column(database.String(10), database.ForeignKey("entity.code"))
    doc = database.Column(database.String(25))
    enabled = database.Column(database.Boolean())
    serie = database.Column(database.String(15))
    current_value = database.Column(database.Integer(), default=0)
    default = database.Column(database.Boolean())


# <---------------------------------------------------------------------------------------------> #
# Todos los registros que afecten el general ledger deben utilizar estar columnas como base.
class GLBase:
    """General Ledger Base."""

    id = database.Column(
        database.String(10),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico_cuid2,
    )
    # Afectación contable
    entity = database.Column(database.String(10), index=True)
    account = database.Column(database.String(50), index=True)
    cost_center = database.Column(database.String(50), index=True)
    unit = database.Column(database.String(10), index=True)
    project = database.Column(database.String(50), index=True)
    # Fecha de registro
    date = database.Column(database.Date)
    # Referencia Cruzada
    type_ = database.Column(database.String(50))
    id_ = database.Column(database.String(75))
    # Orden de los registros
    order = database.Column(database.Integer(), nullable=True)
    # Valor moneda Predeterminada
    value = database.Column(database.DECIMAL())
    # Registro en multimoneda
    currency_id = database.Column(database.String(200))
    exchange_rate = database.Column(database.DECIMAL())
    value_default = database.Column(database.DECIMAL())
    # Informacion ingresada por el usuario
    # Global
    meno = database.Column(database.String(100))
    reference = database.Column(database.String(50))
    # Detalle
    line_meno = database.Column(database.String(50))
    reference1 = database.Column(database.String(50))
    reference2 = database.Column(database.String(50))
    # Terceras partes
    third_type = database.Column(database.String(26))
    third_code = database.Column(database.String(26))


class ComprobanteContable(BaseTransaccion):
    """Comprobante contable manual."""


class ComprobanteContableDetalle(GLBase):
    """Comprobante contable manual detalle."""


# <---------------------------------------------------------------------------------------------> #
# Libro Mayor
class GLEntry(database.Model, GLBase):  # type: ignore[name-defined]
    """Todos los registros que afecten estados financieros vienen de esta tabla."""
