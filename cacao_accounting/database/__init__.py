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
# Definición principal de la clase del ORM.
# < --------------------------------------------------------------------------------------------- >
database = SQLAlchemy()


# < --------------------------------------------------------------------------------------------- >
# Deficinición central de status web.
# < --------------------------------------------------------------------------------------------- >
StatusWeb = namedtuple("StatusWeb", ["color", "leyenda"])

STATUS: Dict[str, StatusWeb] = {
    "abierto": StatusWeb(color="LimeGreen", leyenda="Abierto"),
    "activo": StatusWeb(color="LightSeaGreen", leyenda="Activo"),
    "actual": StatusWeb(color="DodgerBlue", leyenda="Actual"),
    "anulado": StatusWeb(color="SlateGray", leyenda="Actual"),
    "atrasado": StatusWeb(color="OrangeRed", leyenda="Atrasado"),
    "cancelado": StatusWeb(color="Gainsboro", leyenda="Cancelado"),
    "cerrado": StatusWeb(color="Silver", leyenda="Cerrado"),
    "inactivo": StatusWeb(color="LightSlateGray", leyenda="Inactivo"),
    "indefinido": StatusWeb(color="WhiteSmoke", leyenda="Status no definido"),
    "inhabilitado": StatusWeb(color="GhostWhite", leyenda="Inhabilitado"),
    "habilitado": StatusWeb(color="PaleGreen", leyenda="Habilitado"),
    "pagado": StatusWeb(color="SeaGreen", leyenda="Pagado"),
    "predeterminado": StatusWeb(color="Goldenrod", leyenda="Predeterminado"),
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
    creado = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    creado_por = database.Column(database.String(15), nullable=True)
    modificado = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    modificado_por = database.Column(database.String(15), nullable=True)


class BaseTransaccion(BaseTabla):
    """Base para crear transacciones en la entidad."""

    anulado = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    anulado_por = database.Column(database.String(15), nullable=True)
    autorizado = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    autorizado_por = database.Column(database.String(15), nullable=True)
    cancelado = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    cancelado_por = database.Column(database.String(15), nullable=True)
    cerrado = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    cerrado_por = database.Column(database.String(15), nullable=True)
    validado = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    validado_por = database.Column(database.String(15), nullable=True)
    serie = database.Column(database.String(15), nullable=True)
    concec = database.Column(database.Integer(), nullable=True)
    registro_id = database.Column(database.String(75), nullable=True)
    comentario = database.Column(database.String(200), nullable=True)


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
    # Api rest auth
    token = None


class Roles(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles para las administración de permisos de usuario."""

    name = database.Column(database.String(50), nullable=False, unique=True)
    detalle = database.Column(database.String(100), nullable=False, unique=True)


class RolesPermisos(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Los roles definen una cantidad de permisos."""

    rol_id = database.Column(database.String(26), database.ForeignKey("roles.id"))
    modulo_id = database.Column(database.String(26), database.ForeignKey("modulos.id"))
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

    user_id = database.Column(database.String(26), database.ForeignKey("usuario.id"))
    role_id = database.Column(database.String(26), database.ForeignKey("roles.id"))
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


class Direcciones(BaseDireccion):
    """La entidad y sus diferentes unidades de negocios pueden tener o mas dirección fisicas."""


# <---------------------------------------------------------------------------------------------> #
# Bases de la contabilidad
class Cuentas(database.Model, BaseTabla):  # type: ignore[name-defined]
    """La base de contabilidad es el catalogo de cuentas."""

    __table_args__ = (database.UniqueConstraint("entidad", "codigo", name="cta_unica"),)
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
    nombre = database.Column(database.String(100))
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
# Un mismo documento puede tener varias series para numerarlos


class Serie(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Serie para numerar nuevas transacciones."""

    id = database.Column(database.Integer, primary_key=True, autoincrement=True)
    entidad = database.Column(database.String(10), database.ForeignKey("entidad.entidad"))
    documento = database.Column(database.String(25))
    habilitada = database.Column(database.Boolean())
    serie = database.Column(database.String(15), database.ForeignKey("entidad.entidad"))
    ultimo_valor = database.Column(database.Integer(), default=0)
    predeterminada = database.Column(database.Boolean())


# <---------------------------------------------------------------------------------------------> #
# Todos los registros que afecten el general ledger deben utilizar estar columnas como base.
class GLBase:
    """General Ledger Base."""

    id = database.Column(database.String(10), primary_key=True, nullable=False, index=True, default=obtiene_texto_unico_cuid2)
    # Afectación contable
    entidad = database.Column(database.String(10), index=True)
    cta = database.Column(database.String(50), index=True)
    cc = database.Column(database.String(50), index=True)
    unidad = database.Column(database.String(10), index=True)
    proyecto = database.Column(database.String(50), index=True)
    # Fecha de registro
    fecha = database.Column(database.Date)
    # Referencia Cruzada
    tipo = database.Column(database.String(50))
    registro_id = database.Column(database.String(75))
    # Orden de los registros
    order = database.Column(database.Integer(), nullable=True)
    # Valor moneda Predeterminada
    valor = database.Column(database.DECIMAL())
    # Registro en multimoneda
    id_moneda = database.Column(database.String(200))
    tc = database.Column(database.DECIMAL())
    valor_x = database.Column(database.DECIMAL())
    # Informacion ingresada por el usuario
    # Global
    comentario = database.Column(database.String(100))
    referencia = database.Column(database.String(50))
    # Detalle
    comentario_linea = database.Column(database.String(50))
    referencia1 = database.Column(database.String(50))
    referencia2 = database.Column(database.String(50))
    # Terceras partes
    tercero_tipo = database.Column(database.String(26))
    tercero_code = database.Column(database.String(26))


class ComprobanteContable(BaseTransaccion):
    """Comprobante contable manual."""


class ComprobanteContableDetalle(GLBase):
    """Comprobante contable manual detalle."""


# <---------------------------------------------------------------------------------------------> #
# Libro Mayor
class GLEntry(database.Model, GLBase):  # type: ignore[name-defined]
    """Todos los registros que afecten estados financieros vienen de esta tabla."""


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
