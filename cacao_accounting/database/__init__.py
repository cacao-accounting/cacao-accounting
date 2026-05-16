# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Definicion de base de datos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from cuid2 import Cuid
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
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

ENTITY_CODE = "entity.code"
CURRENCY_CODE = "currency.code"
ACCOUNT_ID = "accounts.id"
PARTY_ID = "party.id"
WAREHOUSE_CODE = "warehouse.code"
ITEM_CODE = "item.code"
UOM_CODE = "uom.code"
BOOK_CODE = "book.code"
NAMING_SERIES_ID = "naming_series.id"
EXTERNAL_COUNTER_ID = "external_counter.id"
USER_ID = "user.id"
FISCAL_YEAR_ID = "fiscal_year.id"
CONTACT_ID = "contact.id"
ADDRESS_ID = "address.id"
TAX_TEMPLATE_ID = "tax_template.id"
BATCH_ID = "batch.id"
PURCHASE_ORDER_ID = "purchase_order.id"
PURCHASE_RECEIPT_ID = "purchase_receipt.id"
SALES_ORDER_ID = "sales_order.id"
BANK_ACCOUNT_ID = "bank_account.id"
RECURRING_JOURNAL_TEMPLATE_ID = "recurring_journal_template.id"
BOOK_ID = "book.id"
WORKFLOW_STATE_ID = "workflow_state.id"

# < --------------------------------------------------------------------------------------------- >
# Definición central de status web.
# < --------------------------------------------------------------------------------------------- >


@dataclass(frozen=True)
class StatusWeb:
    """Representa el estado visual de un elemento en la interfaz web."""

    color: str
    leyenda: str


STATUS: dict[str, StatusWeb] = {
    "open": StatusWeb(color="LimeGreen", leyenda="Abierto"),
    "active": StatusWeb(color="LightSeaGreen", leyenda="Activo"),
    "current": StatusWeb(color="DodgerBlue", leyenda="Actual"),
    "canceled": StatusWeb(color="SlateGray", leyenda="Cancelado"),
    "overdue": StatusWeb(color="OrangeRed", leyenda="Atrasado"),
    "closed": StatusWeb(color="Silver", leyenda="Cerrado"),
    "inactive": StatusWeb(color="LightSlateGray", leyenda="Inactivo"),
    "indeterminate": StatusWeb(color="WhiteSmoke", leyenda="Status no definido"),
    "disabled": StatusWeb(color="GhostWhite", leyenda="Inhabilitado"),
    "enabled": StatusWeb(color="PaleGreen", leyenda="Habilitado"),
    "paid": StatusWeb(color="SeaGreen", leyenda="Pagado"),
    "default": StatusWeb(color="Goldenrod", leyenda="Predeterminado"),
    "applied": StatusWeb(color="Green", leyenda="Aplicado"),
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
# Key / Value config.
# <---------------------------------------------------------------------------------------------> #
class CacaoConfig(database.Model):  # type: ignore[name-defined]
    """Key / Value config."""

    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    key = database.Column(database.String(50), nullable=False, index=True)
    value = database.Column(database.String(500), nullable=False, index=True)


# <---------------------------------------------------------------------------------------------> #
# Contiene campos comunes que se pueden reutilizar en otras tablas que deriven de ellas.
# <---------------------------------------------------------------------------------------------> #
class BaseTabla:
    """Columnas estandar para todas las tablas de la base de datos."""

    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    status = database.Column(database.String(50), nullable=True)
    created = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    created_by = database.Column(database.String(26), nullable=True)
    modified = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    modified_by = database.Column(database.String(26), nullable=True)


class BaseTransaccion(BaseTabla):
    """Base para crear transacciones en la entidad."""

    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE))
    book = database.Column(database.String(10), database.ForeignKey(BOOK_CODE))
    user_id = database.Column(database.String(75))
    date = database.Column(database.Date())
    reference = database.Column(database.String(50))
    memo = database.Column(database.String(200), nullable=True)
    canceled = database.Column(database.DateTime, nullable=True)
    canceled_by = database.Column(database.String(15), nullable=True)
    applied = database.Column(database.DateTime, nullable=True)
    applied_por = database.Column(database.String(15), nullable=True)
    serie = database.Column(database.String(10), nullable=True)
    sequential = database.Column(database.Integer(), nullable=True)
    sequential_id = database.Column(database.String(10), nullable=True)


class BaseTercero(BaseTabla):
    """Base para crear terceros en la entidad."""

    name = database.Column(database.String(150), nullable=False)
    comercial_name = database.Column(database.String(150), nullable=False)
    classification = database.Column(database.String(50), nullable=False)
    group = database.Column(database.String(50), nullable=False)
    enabled = database.Column(database.Boolean(), nullable=True)
    id_ = database.Column(database.String(30), nullable=True)
    tax_id = database.Column(database.String(30), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Base for transactional documents with full accounting lifecycle.
# <---------------------------------------------------------------------------------------------> #
class DocBase(BaseTabla):
    """Base para documentos transaccionales con ciclo de vida contable completo."""

    # 0=draft, 1=submitted, 2=cancelled
    docstatus = database.Column(database.Integer(), default=0, nullable=False)
    posting_date = database.Column(database.Date(), nullable=True, index=True)
    document_date = database.Column(database.Date(), nullable=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True, index=True)
    # Human-readable identifier generated from NamingSeries + Sequence
    document_no = database.Column(database.String(100), nullable=True, index=True)
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=True)
    # External counter support — llevar numeracion paralela externa (cheque, numero fiscal, etc.)
    # external_counter_id: FK al ExternalCounter seleccionado para este documento
    external_counter_id = database.Column(
        database.String(26), database.ForeignKey(EXTERNAL_COUNTER_ID), nullable=True, index=True
    )
    # external_number: numero fisico asignado (puede ser distinto del sugerido por el contador)
    external_number = database.Column(database.String(100), nullable=True, index=True)
    # Multi-currency support
    transaction_currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    base_currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    exchange_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    # Reversal support (never delete, always reverse)
    is_reversal = database.Column(database.Boolean(), default=False, nullable=False)
    reversal_of = database.Column(database.String(26), nullable=True)
    # Voucher traceability
    voucher_type = database.Column(database.String(50), nullable=True, index=True)
    voucher_id = database.Column(database.String(26), nullable=True, index=True)


# <---------------------------------------------------------------------------------------------> #
# Administración de monedas, localización, tasas de cambio.
# <---------------------------------------------------------------------------------------------> #
class Currency(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Una moneda para los registros de la entidad."""

    code = database.Column(database.String(10), index=True, nullable=False, unique=True)
    name = database.Column(database.String(75), nullable=False)
    decimals = database.Column(database.Integer(), nullable=True)
    active = database.Column(database.Boolean, nullable=True)
    default = database.Column(database.Boolean, nullable=True)


class ExchangeRate(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Tasa de conversión entre dos monedas distintas."""

    __tablename__ = "exchange_rate"
    __table_args__ = (UniqueConstraint("origin", "destination", "date", name="uq_exchange_rate_date"),)
    origin = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=False)
    destination = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=False)
    rate = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    date = database.Column(database.Date(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de usuario, roles, grupos y permisos.
# <---------------------------------------------------------------------------------------------> #
class User(UserMixin, database.Model, BaseTabla):  # type: ignore[name-defined]
    """Una entidad con acceso al sistema."""

    __allow_unmapped__ = True

    user = database.Column(database.String(15), nullable=False)
    name = database.Column(database.String(80))
    name2 = database.Column(database.String(80))
    last_name = database.Column(database.String(80))
    last_name2 = database.Column(database.String(80))
    e_mail = database.Column(database.String(150), unique=True, nullable=True)
    password = database.Column(database.LargeBinary(), nullable=False)
    classification = database.Column(database.String(15))
    active = database.Column(database.Boolean())
    genre = database.Column(database.String(10))
    birthday = database.Column(database.Date())
    phone = database.Column(database.String(50))
    token: str | None = None


class Roles(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles para las administración de permisos de usuario."""

    name = database.Column(database.String(50), nullable=False, unique=True)
    note = database.Column(database.String(100), nullable=False, unique=True)


class RolesAccess(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Los roles definen una cantidad de permisos."""

    rol_id = database.Column(database.String(26), database.ForeignKey("roles.id"))
    module_id = database.Column(database.String(26), database.ForeignKey("modules.id"))
    access = database.Column(database.Boolean, nullable=False, default=False)
    update = database.Column(database.Boolean, nullable=False, default=False)
    set_null = database.Column(database.Boolean, nullable=False, default=False)
    approve = database.Column(database.Boolean, nullable=False, default=False)
    bi = database.Column(database.Boolean, nullable=False, default=False)
    close = database.Column(database.Boolean, nullable=False, default=False)
    setup = database.Column(database.Boolean, nullable=False, default=False)
    view = database.Column(database.Boolean, nullable=False, default=False)
    create = database.Column(database.Boolean, nullable=False, default=False)
    edit = database.Column(database.Boolean, nullable=False, default=False)
    delete = database.Column(database.Boolean, nullable=False, default=False)
    import_ = database.Column(database.Boolean, nullable=False, default=False)
    report = database.Column(database.Boolean, nullable=False, default=False)
    request = database.Column(database.Boolean, nullable=False, default=False)
    validate = database.Column(database.Boolean, nullable=False, default=False)


class RolesUser(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Roles dan permisos a los usuarios del sistema."""

    user_id = database.Column(database.String(26), database.ForeignKey(USER_ID))
    role_id = database.Column(database.String(26), database.ForeignKey("roles.id"))
    active = database.Column(database.Boolean, nullable=True)


class UserFormPreference(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Preferencias persistentes de formularios por usuario."""

    __tablename__ = "user_form_preference"
    __table_args__ = (
        database.UniqueConstraint(
            "user_id",
            "form_key",
            "view_key",
            name="uq_user_form_preference",
        ),
    )

    user_id = database.Column(database.String(26), database.ForeignKey(USER_ID), nullable=False, index=True)
    form_key = database.Column(database.String(100), nullable=False, index=True)
    view_key = database.Column(database.String(50), nullable=False, index=True)
    schema_version = database.Column(database.Integer(), nullable=False, default=1)
    config_json = database.Column(database.Text(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Administración de módulos del sistema.
# <---------------------------------------------------------------------------------------------> #
class Modules(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Lista de los modulos del sistema."""

    __table_args__ = (database.UniqueConstraint("module", name="modulo_unico"),)
    module = database.Column(database.String(50), unique=True, index=True)
    default = database.Column(database.Boolean(), nullable=False)
    enabled = database.Column(database.Boolean(), nullable=True)


# Alias para compatibilidad
Modulos = Modules


# <---------------------------------------------------------------------------------------------> #
# Descripción de la estructura funcional de la entidad (Compañía).
# <---------------------------------------------------------------------------------------------> #
class Entity(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Todas las transacciones se deben grabar a una entidad."""

    __tablename__ = "entity"
    code = database.Column(database.String(10), unique=True, index=True)
    status = database.Column(database.String(50), nullable=True)
    company_name = database.Column(database.String(100), unique=True, nullable=False)
    name = database.Column(database.String(100))
    tax_id = database.Column(database.String(50), unique=True, nullable=False)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE))
    country = database.Column(database.String(2), nullable=True)
    entity_type = database.Column(database.String(50))
    tipo_entidad_lista = [
        "Asociación",
        "Compañia Limitada",
        "Cooperativa",
        "Sociedad Anonima",
        "Organización sin Fines de Lucro",
        "Persona Natural",
    ]
    e_mail = database.Column(database.String(150))
    web = database.Column(database.String(50))
    phone1 = database.Column(database.String(50))
    phone2 = database.Column(database.String(50))
    fax = database.Column(database.String(50))
    enabled = database.Column(database.Boolean())
    default = database.Column(database.Boolean())


class Unit(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Unidad de negocio: sucursal, oficina o area operativa.

    Ademas de ser una entidad organizacional, la Unidad actua como
    dimension analitica de primer nivel en el General Ledger,
    permitiendo analizar resultados por sucursal o punto de operacion.
    """

    __table_args__ = (database.UniqueConstraint("entity", "code", name="unidad_unica"),)
    code = database.Column(database.String(10), unique=True, index=True)
    name = database.Column(database.String(50), nullable=False)
    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE))
    enabled = database.Column(database.Boolean(), nullable=True)


# Alias para compatibilidad
Unidad = Unit

# <---------------------------------------------------------------------------------------------> #
# Multi-Ledger: soporte para multiples libros contables paralelos.
# Ejemplos: Fiscal (NIO), NIIF/IFRS (USD), Board Review, Tax Book, etc.
# Un solo documento genera multiples gl_entry, una por libro activo.
# <---------------------------------------------------------------------------------------------> #


class Book(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Libro contable — cada compania puede tener multiples libros paralelos.

    Ejemplos de libros:
    - Fiscal (moneda local, normas fiscales)
    - NIIF/IFRS (USD, normas internacionales)
    - Board Review (consolidacion gerencial)
    - Tax Book (calculo de impuestos)

    Cada transaccion genera una entrada en gl_entry por cada libro activo.
    """

    __table_args__ = (database.UniqueConstraint("entity", "code", name="libro_unico"),)
    code = database.Column(database.String(10), index=True)
    name = database.Column(database.String(100), nullable=False)
    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE))
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    # El libro primario es la fuente de verdad base
    is_primary = database.Column(database.Boolean(), default=False, nullable=False)
    default = database.Column(database.Boolean())
    # Reglas especificas del libro (JSON: ajustes de depreciacion, etc.)
    mapping_rules = database.Column(database.Text(), nullable=True)


class LedgerMappingRule(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Regla de diferencia entre libros contables.

    Define ajustes automaticos entre el libro primario y libros secundarios.
    Ejemplo: cuenta de depreciacion diferente entre libro fiscal e IFRS.
    """

    __tablename__ = "ledger_mapping_rule"
    source_book = database.Column(database.String(10), database.ForeignKey(BOOK_CODE), nullable=False, index=True)
    target_book = database.Column(database.String(10), database.ForeignKey(BOOK_CODE), nullable=False, index=True)
    source_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    target_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    rule_description = database.Column(database.String(200), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class FiscalYear(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Anio fiscal de una entidad."""

    __tablename__ = "fiscal_year"
    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    name = database.Column(database.String(50), nullable=False)
    year_start_date = database.Column(database.Date(), nullable=False)
    year_end_date = database.Column(database.Date(), nullable=False)
    is_closed = database.Column(database.Boolean(), default=False, nullable=False)
    financial_closed = database.Column(database.Boolean(), default=False, nullable=False)
    closing_voucher_id = database.Column(
        database.String(26),
        database.ForeignKey("comprobante_contable.id", use_alter=True),
        nullable=True,
    )


class AccountingPeriod(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Todas las transaciones deben estar vinculadas a un periodo contable."""

    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), index=True)
    fiscal_year_id = database.Column(database.String(26), database.ForeignKey(FISCAL_YEAR_ID), nullable=True)
    name = database.Column(database.String(50), nullable=False)
    status = database.Column(database.String(50))
    enabled = database.Column(database.Boolean(), index=True)
    # Periodo cerrado: no se permiten nuevas transacciones
    is_closed = database.Column(database.Boolean(), default=False, nullable=False)
    start = database.Column(database.Date(), nullable=False)
    end = database.Column(database.Date(), nullable=False)


class Accounts(database.Model, BaseTabla):  # type: ignore[name-defined]
    """La base de contabilidad es el catalogo de cuentas."""

    __table_args__ = (database.UniqueConstraint("entity", "code", name="cta_unica"),)
    active = database.Column(database.Boolean(), index=True)
    enabled = database.Column(database.Boolean(), index=True)
    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE))
    code = database.Column(database.String(50), index=True)
    name = database.Column(database.String(100))
    group = database.Column(database.Boolean())
    parent = database.Column(database.String(50), nullable=True)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    # Activo, Pasivo, Patrimonio, Ingresos, Gastos
    classification = database.Column(database.String(50), index=True)
    # Efectivo, Cta. Bancaria, Inventario, Por Cobrar, Por Pagar
    type_ = database.Column(database.String(50))
    # receivable, payable, bank, cash, expense, income, asset, liability
    account_type = database.Column(database.String(50), nullable=True, index=True)


class CostCenter(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Centro de Costos — dimension analitica para clasificacion de gastos e ingresos."""

    __table_args__ = (database.UniqueConstraint("entity", "code", name="cc_unico"),)
    active = database.Column(database.Boolean(), index=True)
    default = database.Column(database.Boolean())
    enabled = database.Column(database.Boolean(), index=True)
    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE))
    code = database.Column(database.String(10), index=True)
    name = database.Column(database.String(100))
    group = database.Column(database.Boolean())
    parent = database.Column(database.String(100), nullable=True)


class Project(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Proyecto — dimension analitica con presupuesto y fechas definidas."""

    __table_args__ = (database.UniqueConstraint("entity", "code", name="py_unico"),)
    enabled = database.Column(database.Boolean(), index=True)
    entity = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE))
    code = database.Column(database.String(10), unique=True, index=True)
    name = database.Column(database.String(100))
    start = database.Column(database.Date())
    end = database.Column(database.Date())
    budget = database.Column(database.Float())


# <---------------------------------------------------------------------------------------------> #
# Series e Identificadores — Framework robusto multi-contexto.
# <---------------------------------------------------------------------------------------------> #
class NamingSeries(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Define el formato logico de una serie de numeracion.

    Soporta tokens dinamicos basados en posting_date (no created_at):
    *YYYY*, *YY*, *MMM*, *MM*, *DD*, *COMP*

    Ejemplo: CHOCO-SI-*YYYY*-*MMM*-

    Regla de negocio: como maximo una serie puede ser predeterminada (is_default=True)
    por combinacion de entity_type + company. Para series globales, company=NULL.
    """

    __tablename__ = "naming_series"
    name = database.Column(database.String(100), nullable=False)
    # Tipo de entidad: sales_invoice, payment_entry, journal_entry, etc.
    entity_type = database.Column(database.String(50), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True)
    prefix_template = database.Column(database.String(100), nullable=False)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)
    # Solo una serie activa puede ser predeterminada por entity_type + company.
    is_default = database.Column(database.Boolean(), default=False, nullable=False, index=True)


class Sequence(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Contador fisico para una serie.

    Permite multiples secuencias por serie:
    - Cheques Banco A, Cheques Banco B, Transferencias
    - POS1, POS2, POS3
    - Serie fiscal autorizada por gobierno
    """

    __tablename__ = "sequence"
    name = database.Column(database.String(100), nullable=False)
    current_value = database.Column(database.Integer(), default=0, nullable=False)
    increment = database.Column(database.Integer(), default=1, nullable=False)
    # Padding: 5 => 00001, 8 => 00000001
    padding = database.Column(database.Integer(), default=5, nullable=False)
    # never, yearly, monthly
    reset_policy = database.Column(database.String(20), default="never", nullable=False)


class SeriesSequenceMap(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Mapa N:M entre series y secuencias — flexibilidad maxima."""

    __tablename__ = "series_sequence_map"
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=False, index=True)
    sequence_id = database.Column(database.String(26), database.ForeignKey("sequence.id"), nullable=False, index=True)
    priority = database.Column(database.Integer(), default=0, nullable=False)
    # Condicion JSON para seleccion dinamica (banco, metodo de pago, etc.)
    condition = database.Column(database.Text(), nullable=True)


class GeneratedIdentifierLog(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Auditoria obligatoria de identificadores generados.

    Garantiza unicidad y trazabilidad de todos los identificadores del sistema.
    Los tokens se resuelven usando posting_date, nunca created_at.
    """

    __tablename__ = "generated_identifier_log"
    entity_type = database.Column(database.String(50), nullable=False, index=True)
    entity_id = database.Column(database.String(26), nullable=False, index=True)
    full_identifier = database.Column(database.String(200), nullable=False, unique=True)
    sequence_id = database.Column(database.String(26), database.ForeignKey("sequence.id"), nullable=True)
    generated_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True, index=True)
    posting_date = database.Column(database.Date(), nullable=True)


class ExternalCounter(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Contador externo para numeraciones fuera del control directo del sistema.

    Representa numeraciones fisicas, fiscales o bancarias: chequeras, resoluciones
    fiscales, recibos preimpresos, etc.

    El sistema sugiere el siguiente numero pero el usuario conserva control
    operativo. Toda modificacion del ultimo numero usado queda auditada en
    ExternalCounterAuditLog.
    """

    __tablename__ = "external_counter"
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    name = database.Column(database.String(100), nullable=False)
    # Tipo: checkbook, fiscal, receipt, bank_transfer, other
    counter_type = database.Column(database.String(50), nullable=True)
    prefix = database.Column(database.String(30), nullable=True)
    last_used = database.Column(database.Integer(), default=0, nullable=False)
    padding = database.Column(database.Integer(), default=5, nullable=False)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)
    description = database.Column(database.Text(), nullable=True)
    # Relacion opcional con una NamingSeries interna
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=True)

    @property
    def next_suggested(self) -> int:
        """Devuelve el siguiente numero externo sugerido."""
        return (self.last_used or 0) + 1

    @property
    def next_suggested_formatted(self) -> str:
        """Devuelve el siguiente numero externo formateado con padding y prefijo."""
        val = self.next_suggested
        prefix = self.prefix or ""
        return f"{prefix}{str(val).zfill(self.padding or 5)}"


class ExternalCounterAuditLog(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Bitacora de auditoria obligatoria de cambios en contadores externos.

    Registra cada ajuste al campo last_used de ExternalCounter.
    El motivo es obligatorio para garantizar trazabilidad operativa completa.
    """

    __tablename__ = "external_counter_audit_log"
    external_counter_id = database.Column(
        database.String(26), database.ForeignKey(EXTERNAL_COUNTER_ID), nullable=False, index=True
    )
    previous_value = database.Column(database.Integer(), nullable=False)
    new_value = database.Column(database.Integer(), nullable=False)
    # Motivo obligatorio por politica de negocio
    reason = database.Column(database.Text(), nullable=False)
    changed_by = database.Column(database.String(26), nullable=True)
    changed_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)


class SeriesExternalCounterMap(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Mapa N:M entre series y contadores externos — un contador por tipo de operacion.

    Permite que una misma serie tenga multiples contadores externos asociados,
    seleccionados dinamicamente mediante condition_json.

    Ejemplo: Serie PAY puede tener:
    - Contador "Chequera BANPRO": condition_json = {"payment_method": "check", "bank": "BANPRO"}
    - Contador "Chequera BDF":    condition_json = {"payment_method": "check", "bank": "BDF"}
    - Sin condicion (prioridad 0): contador predeterminado para transferencias

    El campo condition_json soporta claves arbitrarias del contexto del documento:
    payment_method, bank_account_id, party_type, etc.
    """

    __tablename__ = "series_external_counter_map"
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=False, index=True)
    external_counter_id = database.Column(
        database.String(26), database.ForeignKey(EXTERNAL_COUNTER_ID), nullable=False, index=True
    )
    priority = database.Column(database.Integer(), default=0, nullable=False)
    # JSON con condiciones para seleccion dinamica. Ejemplo:
    # {"payment_method": "check", "bank_account_id": "abc123"}
    condition_json = database.Column(database.Text(), nullable=True)


class ExternalNumberUsage(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Registro de uso de numeros externos por documento.

    Garantiza unicidad de (external_counter_id, external_number):
    un mismo numero externo no puede asignarse dos veces al mismo contador.
    Permite trazabilidad completa: saber que documento uso que cheque/numero fiscal.
    """

    __tablename__ = "external_number_usage"
    __table_args__ = (UniqueConstraint("external_counter_id", "external_number", name="uq_external_number_per_counter"),)
    external_counter_id = database.Column(
        database.String(26), database.ForeignKey(EXTERNAL_COUNTER_ID), nullable=False, index=True
    )
    # Numero externo como string para soportar prefijos alfanumericos
    external_number = database.Column(database.String(100), nullable=False, index=True)
    # Tipo y ID del documento que uso este numero
    entity_type = database.Column(database.String(50), nullable=False, index=True)
    entity_id = database.Column(database.String(26), nullable=False, index=True)
    # Valor entero del numero para facilitar validaciones de rango
    sequence_value = database.Column(database.Integer(), nullable=True)
    recorded_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Party System — Clientes y Proveedores (entidades globales).
# <---------------------------------------------------------------------------------------------> #
class Party(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Entidad global para terceros (clientes y proveedores).

    Los terceros son globales — no pertenecen a una sola compania.
    La activacion por compania se gestiona mediante CompanyParty.
    """

    __tablename__ = "party"
    # customer, supplier
    party_type = database.Column(database.String(20), nullable=False, index=True)
    name = database.Column(database.String(150), nullable=False)
    comercial_name = database.Column(database.String(150), nullable=True)
    tax_id = database.Column(database.String(50), nullable=True, index=True)
    classification = database.Column(database.String(50), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class Contact(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Contacto de un tercero."""

    __tablename__ = "contact"
    first_name = database.Column(database.String(100), nullable=False)
    last_name = database.Column(database.String(100), nullable=True)
    email = database.Column(database.String(150), nullable=True)
    phone = database.Column(database.String(50), nullable=True)
    mobile = database.Column(database.String(50), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class Address(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Direccion de un tercero."""

    __tablename__ = "address"
    address_line1 = database.Column(database.String(200), nullable=False)
    address_line2 = database.Column(database.String(200), nullable=True)
    city = database.Column(database.String(100), nullable=True)
    state = database.Column(database.String(100), nullable=True)
    country = database.Column(database.String(100), nullable=True)
    postal_code = database.Column(database.String(20), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class PartyContact(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Relacion N:M entre terceros y contactos."""

    __tablename__ = "party_contact"
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=False, index=True)
    contact_id = database.Column(database.String(26), database.ForeignKey(CONTACT_ID), nullable=False, index=True)
    # billing, sales, purchasing, logistics, support, primary
    role = database.Column(database.String(30), nullable=True)


class PartyAddress(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Relacion N:M entre terceros y direcciones."""

    __tablename__ = "party_address"
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=False, index=True)
    address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=False, index=True)
    # billing, shipping, office, branch, warehouse
    address_type = database.Column(database.String(30), nullable=True)
    is_primary = database.Column(database.Boolean(), default=False, nullable=False)


class PaymentTerms(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Condiciones de pago para terceros.

    Define plazos, descuentos por pronto pago y politica de vencimiento.
    """

    __tablename__ = "payment_terms"
    name = database.Column(database.String(100), nullable=False, unique=True)
    description = database.Column(database.Text(), nullable=True)
    # Days from posting_date until payment is due
    due_days = database.Column(database.Integer(), default=0, nullable=False)
    # Days from posting_date to qualify for early payment discount
    discount_days = database.Column(database.Integer(), nullable=True)
    # Percentage discount for early payment (e.g. 2.5 = 2.5%)
    discount_percent = database.Column(database.Numeric(precision=5, scale=2), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


PAYMENT_TERMS_ID = "payment_terms.id"


class CompanyParty(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Activa el uso de un tercero dentro de una compania."""

    __tablename__ = "company_party"
    __table_args__ = (UniqueConstraint("company", "party_id", name="uq_company_party"),)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=False, index=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)
    credit_limit = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    payment_terms_id = database.Column(database.String(26), database.ForeignKey(PAYMENT_TERMS_ID), nullable=True, index=True)
    tax_template_id = database.Column(database.String(26), database.ForeignKey(TAX_TEMPLATE_ID), nullable=True, index=True)
    allow_purchase_invoice_without_order = database.Column(database.Boolean(), default=False, nullable=False)
    allow_purchase_invoice_without_receipt = database.Column(database.Boolean(), default=False, nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Inventory — Items, UOM, Almacenes y Stock.
# <---------------------------------------------------------------------------------------------> #
class UOM(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Unidad de medida."""

    __tablename__ = "uom"
    code = database.Column(database.String(20), unique=True, index=True, nullable=False)
    name = database.Column(database.String(100), nullable=False)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class Item(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Articulo o servicio.

    Reglas de clasificacion:
    - service: nunca es stock_item
    - goods + is_stock_item=True: afecta inventario y stock_ledger_entry
    - goods + is_stock_item=False: gasto directo, no afecta inventario
    """

    __tablename__ = "item"
    code = database.Column(database.String(50), unique=True, index=True, nullable=False)
    name = database.Column(database.String(200), nullable=False)
    description = database.Column(database.Text(), nullable=True)
    # goods, service
    item_type = database.Column(database.String(20), nullable=False, index=True)
    is_stock_item = database.Column(database.Boolean(), default=False, nullable=False)
    has_batch = database.Column(database.Boolean(), default=False, nullable=False)
    has_serial_no = database.Column(database.Boolean(), default=False, nullable=False)
    default_uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=False)
    # FIFO, moving_average — inmutable una vez hay transacciones
    valuation_method = database.Column(database.String(20), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class ItemUOMConversion(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Conversiones de unidades de medida por item (no globales)."""

    __tablename__ = "item_uom_conversion"
    __table_args__ = (UniqueConstraint("item_code", "from_uom", "to_uom", name="uq_item_uom_conv"),)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    from_uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=False)
    to_uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=False)
    conversion_factor = database.Column(database.Numeric(precision=20, scale=9), nullable=False)


class Warehouse(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Almacen o bodega."""

    __tablename__ = "warehouse"
    __table_args__ = (
        UniqueConstraint("company", "code", name="uq_warehouse_code"),
        UniqueConstraint("code", name="uq_warehouse_code_global"),
    )
    code = database.Column(database.String(20), index=True, nullable=False)
    name = database.Column(database.String(150), nullable=False)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    parent_warehouse = database.Column(database.String(20), nullable=True)
    is_group = database.Column(database.Boolean(), default=False, nullable=False)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class Batch(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Lote de un item inventariable."""

    __tablename__ = "batch"
    __table_args__ = (UniqueConstraint("item_code", "batch_no", name="uq_batch"),)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    batch_no = database.Column(database.String(100), nullable=False, index=True)
    expiry_date = database.Column(database.Date(), nullable=True)
    manufacturing_date = database.Column(database.Date(), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class SerialNumber(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Numero de serie de un item inventariable."""

    __tablename__ = "serial_number"
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    serial_no = database.Column(database.String(100), nullable=False, unique=True, index=True)
    serial_status = database.Column(database.String(20), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    purchase_date = database.Column(database.Date(), nullable=True)
    warranty_expiry_date = database.Column(database.Date(), nullable=True)


class StockEntry(database.Model, DocBase):  # type: ignore[name-defined]
    """Entrada de almacen (movimiento de inventario)."""

    __tablename__ = "stock_entry"
    # receipt, issue, transfer, manufacture, repack
    purpose = database.Column(database.String(30), nullable=False, index=True)
    from_warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    to_warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    total_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class StockEntryItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de una entrada de almacen."""

    __tablename__ = "stock_entry_item"
    stock_entry_id = database.Column(database.String(26), database.ForeignKey("stock_entry.id"), nullable=False, index=True)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    source_warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    target_warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=False)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    basic_rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    batch_id = database.Column(database.String(26), database.ForeignKey(BATCH_ID), nullable=True)
    serial_no = database.Column(database.String(100), nullable=True)
    valuation_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)


class StockLedgerEntry(database.Model):  # type: ignore[name-defined]
    """Libro mayor de inventario — fuente de verdad del stock."""

    __tablename__ = "stock_ledger_entry"
    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    posting_date = database.Column(database.Date(), nullable=False, index=True)
    posting_time = database.Column(database.Time(), nullable=True)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    qty_change = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    qty_after_transaction = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    valuation_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    stock_value_difference = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    stock_value = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    voucher_type = database.Column(database.String(50), nullable=False, index=True)
    voucher_id = database.Column(database.String(26), nullable=False, index=True)
    batch_id = database.Column(database.String(26), database.ForeignKey(BATCH_ID), nullable=True)
    serial_no = database.Column(database.String(100), nullable=True)
    is_cancelled = database.Column(database.Boolean(), default=False, nullable=False)
    created = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    created_by = database.Column(database.String(26), nullable=True)


class StockBin(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Snapshot de stock por item y almacen (optimizacion de performance)."""

    __tablename__ = "stock_bin"
    __table_args__ = (UniqueConstraint("item_code", "warehouse", name="uq_stock_bin"),)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    actual_qty = database.Column(database.Numeric(precision=20, scale=9), default=0, nullable=False)
    reserved_qty = database.Column(database.Numeric(precision=20, scale=9), default=0, nullable=True)
    ordered_qty = database.Column(database.Numeric(precision=20, scale=9), default=0, nullable=True)
    valuation_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    stock_value = database.Column(database.Numeric(precision=20, scale=4), nullable=True)


class StockValuationLayer(database.Model):  # type: ignore[name-defined]
    """Capa de valuacion de inventario para FIFO y Promedio Movil."""

    __tablename__ = "stock_valuation_layer"
    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    rate = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    stock_value_difference = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remaining_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    remaining_stock_value = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    voucher_type = database.Column(database.String(50), nullable=False, index=True)
    voucher_id = database.Column(database.String(26), nullable=False, index=True)
    posting_date = database.Column(database.Date(), nullable=False, index=True)
    created = database.Column(database.DateTime, default=database.func.now(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Purchasing — Compras y Cuentas por Pagar.
# <---------------------------------------------------------------------------------------------> #
class PurchaseOrder(database.Model, DocBase):  # type: ignore[name-defined]
    """Orden de compra."""

    __tablename__ = "purchase_order"
    supplier_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    supplier_name = database.Column(database.String(200), nullable=True)
    supplier_invoice_no = database.Column(database.String(50), nullable=True)
    total_qty = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    net_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    tax_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    billing_address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class PurchaseOrderItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de una orden de compra."""

    __tablename__ = "purchase_order_item"
    purchase_order_id = database.Column(
        database.String(26), database.ForeignKey(PURCHASE_ORDER_ID), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    received_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    billed_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


class PurchaseQuotation(database.Model, DocBase):  # type: ignore[name-defined]
    """Solicitud de cotización de compra."""

    __tablename__ = "purchase_quotation"
    supplier_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    supplier_name = database.Column(database.String(200), nullable=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class PurchaseQuotationItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de una solicitud de cotización de compra."""

    __tablename__ = "purchase_quotation_item"
    purchase_quotation_id = database.Column(
        database.String(26), database.ForeignKey("purchase_quotation.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


class PurchaseRequest(database.Model, DocBase):  # type: ignore[name-defined]
    """Solicitud de compra interna."""

    __tablename__ = "purchase_request"
    requested_by = database.Column(database.String(100), nullable=True)
    department = database.Column(database.String(100), nullable=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class PurchaseRequestItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de una solicitud de compra."""

    __tablename__ = "purchase_request_item"
    purchase_request_id = database.Column(
        database.String(26), database.ForeignKey("purchase_request.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


class SupplierQuotation(database.Model, DocBase):  # type: ignore[name-defined]
    """Cotización de proveedor derivada de una solicitud de cotización."""

    __tablename__ = "supplier_quotation"
    supplier_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    supplier_name = database.Column(database.String(200), nullable=True)
    purchase_quotation_id = database.Column(
        database.String(26), database.ForeignKey("purchase_quotation.id"), nullable=True, index=True
    )
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class SupplierQuotationItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de una cotización de proveedor."""

    __tablename__ = "supplier_quotation_item"
    supplier_quotation_id = database.Column(
        database.String(26), database.ForeignKey("supplier_quotation.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_rate = database.Column(database.Numeric(20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


class PurchaseReceipt(database.Model, DocBase):  # type: ignore[name-defined]
    """Recepcion de compra."""

    __tablename__ = "purchase_receipt"
    supplier_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    supplier_name = database.Column(database.String(200), nullable=True)
    purchase_order_id = database.Column(database.String(26), database.ForeignKey(PURCHASE_ORDER_ID), nullable=True, index=True)
    is_return = database.Column(database.Boolean(), default=False, nullable=False)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class PurchaseReceiptItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de recepcion de compra."""

    __tablename__ = "purchase_receipt_item"
    purchase_receipt_id = database.Column(
        database.String(26), database.ForeignKey(PURCHASE_RECEIPT_ID), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    batch_id = database.Column(database.String(26), database.ForeignKey("batch.id"), nullable=True)
    serial_no = database.Column(database.String(100), nullable=True)
    valuation_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)


class PurchaseInvoice(database.Model, DocBase):  # type: ignore[name-defined]
    """Factura de compra."""

    __tablename__ = "purchase_invoice"
    supplier_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    supplier_name = database.Column(database.String(200), nullable=True)
    supplier_invoice_no = database.Column(database.String(50), nullable=True)
    document_type = database.Column(database.String(50), nullable=False, default="purchase_invoice")
    is_return = database.Column(database.Boolean(), default=False, nullable=False)
    purchase_order_id = database.Column(database.String(26), database.ForeignKey(PURCHASE_ORDER_ID), nullable=True, index=True)
    purchase_receipt_id = database.Column(
        database.String(26), database.ForeignKey(PURCHASE_RECEIPT_ID), nullable=True, index=True
    )
    tax_template_id = database.Column(database.String(26), database.ForeignKey(TAX_TEMPLATE_ID), nullable=True, index=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    tax_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    outstanding_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_outstanding_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    billing_address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class PurchaseInvoiceItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de factura de compra."""

    __tablename__ = "purchase_invoice_item"
    purchase_invoice_id = database.Column(
        database.String(26), database.ForeignKey("purchase_invoice.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    expense_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Sales — Ventas y Cuentas por Cobrar.
# <---------------------------------------------------------------------------------------------> #
class SalesOrder(database.Model, DocBase):  # type: ignore[name-defined]
    """Orden de venta."""

    __tablename__ = "sales_order"
    customer_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    customer_name = database.Column(database.String(200), nullable=True)
    sales_quotation_id = database.Column(
        database.String(26), database.ForeignKey("sales_quotation.id"), nullable=True, index=True
    )
    is_pos = database.Column(database.Boolean(), default=False, nullable=False)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    tax_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    billing_address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=True)
    shipping_address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=True)
    contact_id = database.Column(database.String(26), database.ForeignKey(CONTACT_ID), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class SalesRequest(database.Model, DocBase):  # type: ignore[name-defined]
    """Pedido de venta interno."""

    __tablename__ = "sales_request"
    customer_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    customer_name = database.Column(database.String(200), nullable=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class SalesRequestItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de pedido de venta."""

    __tablename__ = "sales_request_item"
    sales_request_id = database.Column(
        database.String(26), database.ForeignKey("sales_request.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


class SalesQuotation(database.Model, DocBase):  # type: ignore[name-defined]
    """Cotización de venta."""

    __tablename__ = "sales_quotation"
    customer_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    customer_name = database.Column(database.String(200), nullable=True)
    sales_request_id = database.Column(database.String(26), database.ForeignKey("sales_request.id"), nullable=True, index=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class SalesQuotationItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de cotización de venta."""

    __tablename__ = "sales_quotation_item"
    sales_quotation_id = database.Column(
        database.String(26), database.ForeignKey("sales_quotation.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(20, scale=4), nullable=True)
    discount_percentage = database.Column(database.Numeric(precision=10, scale=4), nullable=True)
    discount_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)


class SalesOrderItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de orden de venta."""

    __tablename__ = "sales_order_item"
    sales_order_id = database.Column(database.String(26), database.ForeignKey(SALES_ORDER_ID), nullable=False, index=True)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    discount_percentage = database.Column(database.Numeric(precision=10, scale=4), nullable=True)
    discount_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    delivered_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    billed_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=True)


class DeliveryNote(database.Model, DocBase):  # type: ignore[name-defined]
    """Nota de entrega."""

    __tablename__ = "delivery_note"
    customer_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    customer_name = database.Column(database.String(200), nullable=True)
    sales_order_id = database.Column(database.String(26), database.ForeignKey(SALES_ORDER_ID), nullable=True, index=True)
    is_return = database.Column(database.Boolean(), default=False, nullable=False)
    shipping_address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=True)
    contact_id = database.Column(database.String(26), database.ForeignKey(CONTACT_ID), nullable=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class DeliveryNoteItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de nota de entrega."""

    __tablename__ = "delivery_note_item"
    delivery_note_id = database.Column(
        database.String(26), database.ForeignKey("delivery_note.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    batch_id = database.Column(database.String(26), database.ForeignKey("batch.id"), nullable=True)
    serial_no = database.Column(database.String(100), nullable=True)


class SalesInvoice(database.Model, DocBase):  # type: ignore[name-defined]
    """Factura de venta."""

    __tablename__ = "sales_invoice"
    customer_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    customer_name = database.Column(database.String(200), nullable=True)
    document_type = database.Column(database.String(50), nullable=False, default="sales_invoice")
    is_pos = database.Column(database.Boolean(), default=False, nullable=False)
    is_return = database.Column(database.Boolean(), default=False, nullable=False)
    sales_order_id = database.Column(database.String(26), database.ForeignKey(SALES_ORDER_ID), nullable=True, index=True)
    delivery_note_id = database.Column(database.String(26), database.ForeignKey("delivery_note.id"), nullable=True, index=True)
    tax_template_id = database.Column(database.String(26), database.ForeignKey(TAX_TEMPLATE_ID), nullable=True, index=True)
    total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    tax_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_grand_total = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    outstanding_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_outstanding_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    billing_address_id = database.Column(database.String(26), database.ForeignKey(ADDRESS_ID), nullable=True)
    contact_id = database.Column(database.String(26), database.ForeignKey(CONTACT_ID), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class SalesInvoiceItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de factura de venta."""

    __tablename__ = "sales_invoice_item"
    sales_invoice_id = database.Column(
        database.String(26), database.ForeignKey("sales_invoice.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    item_name = database.Column(database.String(200), nullable=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    qty_in_base_uom = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    discount_percentage = database.Column(database.Numeric(precision=10, scale=4), nullable=True)
    discount_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    income_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True)
    batch_id = database.Column(database.String(26), database.ForeignKey("batch.id"), nullable=True)
    serial_no = database.Column(database.String(100), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Banking — Bancos, Cuentas Bancarias y Pagos.
# <---------------------------------------------------------------------------------------------> #
class Bank(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Banco."""

    __tablename__ = "bank"
    name = database.Column(database.String(150), nullable=False)
    swift_code = database.Column(database.String(20), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class BankAccount(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Cuenta bancaria."""

    __tablename__ = "bank_account"
    __table_args__ = (UniqueConstraint("company", "account_no", name="uq_bank_account"),)
    bank_id = database.Column(database.String(26), database.ForeignKey("bank.id"), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    account_name = database.Column(database.String(150), nullable=False)
    account_no = database.Column(database.String(50), nullable=True)
    iban = database.Column(database.String(50), nullable=True)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    gl_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=True)
    default_external_counter_id = database.Column(database.String(26), database.ForeignKey(EXTERNAL_COUNTER_ID), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class PaymentEntry(database.Model, DocBase):  # type: ignore[name-defined]
    """Entrada de pago."""

    __tablename__ = "payment_entry"
    # receive, pay, internal_transfer
    payment_type = database.Column(database.String(30), nullable=False, index=True)
    party_type = database.Column(database.String(20), nullable=True, index=True)
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    party_name = database.Column(database.String(200), nullable=True)
    bank_account_id = database.Column(database.String(26), database.ForeignKey(BANK_ACCOUNT_ID), nullable=True, index=True)
    paid_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_paid_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    received_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    base_received_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    paid_from_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    paid_to_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    reference_no = database.Column(database.String(100), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


class PaymentReference(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Aplicacion de pagos a documentos — soporta pagos parciales."""

    __tablename__ = "payment_reference"
    payment_id = database.Column(database.String(26), database.ForeignKey("payment_entry.id"), nullable=False, index=True)
    reference_type = database.Column(database.String(50), nullable=False, index=True)
    reference_id = database.Column(database.String(26), nullable=False, index=True)
    total_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    outstanding_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    allocated_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=False)
    allocation_date = database.Column(database.Date(), nullable=True, index=True)


class DocumentRelation(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Relacion generica entre documentos y sus lineas.

    Guarda la trazabilidad source row -> target row para parcialidades y flujos
    documentales sin acoplar tablas entre modulos.
    """

    __tablename__ = "document_relation"
    __table_args__ = (
        database.Index("ix_document_relation_source", "source_type", "source_id", "source_item_id"),
        database.Index("ix_document_relation_target", "target_type", "target_id", "target_item_id"),
        UniqueConstraint(
            "source_type",
            "source_id",
            "source_item_id",
            "target_type",
            "target_id",
            "target_item_id",
            "relation_type",
            name="uq_document_relation_line",
        ),
    )
    source_type = database.Column(database.String(50), nullable=False, index=True)
    source_id = database.Column(database.String(26), nullable=False, index=True)
    source_item_id = database.Column(database.String(26), nullable=True, index=True)
    target_type = database.Column(database.String(50), nullable=False, index=True)
    target_id = database.Column(database.String(26), nullable=False, index=True)
    target_item_id = database.Column(database.String(26), nullable=True, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True, index=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    rate = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    relation_type = database.Column(database.String(50), nullable=False, index=True)
    # active, reverted, closed. Reverted/closed relations remain as historical trace.
    status = database.Column(database.String(20), default="active", nullable=False, index=True)
    reversed_at = database.Column(database.DateTime, nullable=True)
    reversed_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    reversal_reason = database.Column(database.Text(), nullable=True)
    cancelled_at = database.Column(database.DateTime, nullable=True)
    cancelled_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    metadata_json = database.Column(database.Text(), nullable=True)


class DocumentLineFlowState(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Estado acumulado de una linea fuente dentro de un flujo documental.

    La fuente de verdad sigue siendo ``DocumentRelation``; esta tabla actua como
    cache auditable para consultas rapidas y cierres manuales de saldo.
    """

    __tablename__ = "document_line_flow_state"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "source_item_id",
            "target_type",
            name="uq_document_line_flow_state",
        ),
        database.Index("ix_document_line_flow_state_source", "source_type", "source_id", "source_item_id"),
    )
    source_type = database.Column(database.String(50), nullable=False, index=True)
    source_id = database.Column(database.String(26), nullable=False, index=True)
    source_item_id = database.Column(database.String(26), nullable=False, index=True)
    target_type = database.Column(database.String(50), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True, index=True)
    source_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False, default=0)
    processed_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False, default=0)
    cancelled_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False, default=0)
    closed_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False, default=0)
    pending_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False, default=0)
    # open, partial, complete, closed, cancelled
    line_status = database.Column(database.String(30), default="open", nullable=False, index=True)
    closed_at = database.Column(database.DateTime, nullable=True)
    closed_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    close_reason = database.Column(database.Text(), nullable=True)


class BankTransaction(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Transaccion bancaria importada o ingresada manualmente."""

    __tablename__ = "bank_transaction"
    bank_account_id = database.Column(database.String(26), database.ForeignKey(BANK_ACCOUNT_ID), nullable=False, index=True)
    posting_date = database.Column(database.Date(), nullable=False, index=True)
    deposit = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    withdrawal = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    description = database.Column(database.Text(), nullable=True)
    reference_number = database.Column(database.String(100), nullable=True)
    is_reconciled = database.Column(database.Boolean(), default=False, nullable=False)
    payment_entry_id = database.Column(database.String(26), database.ForeignKey("payment_entry.id"), nullable=True, index=True)


# <---------------------------------------------------------------------------------------------> #
# General Ledger — Fuente unica de verdad contable.
#
# Arquitectura Multi-Ledger:
#   - ledger_id apunta al libro contable (Book) al que pertenece esta entrada
#   - Un documento genera N entradas en gl_entry, una por cada libro activo
#   - Libros posibles: Fiscal, NIIF/IFRS, Board Review, Tax, etc.
#
# Dimensiones analiticas en GL:
#   - cost_center_code: dimension Centro de Costo
#   - unit_code: dimension Unidad de Negocio (sucursal/oficina)
#   - project_code: dimension Proyecto
#
# <---------------------------------------------------------------------------------------------> #
class GLBase:
    """General Ledger Base — columnas compartidas por entidades GL."""

    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    entity = database.Column(database.String(10), index=True)
    account = database.Column(database.String(50), index=True)
    cost_center = database.Column(database.String(50), index=True)
    unit = database.Column(database.String(10), index=True)
    project = database.Column(database.String(50), index=True)
    book = database.Column(database.String(10), index=True)
    date = database.Column(database.Date)
    transaction = database.Column(database.String(50))
    transaction_id = database.Column(database.String(75))
    order = database.Column(database.Integer(), nullable=True)
    value = database.Column(database.Numeric(precision=20, scale=4))
    currency_id = database.Column(database.String(200))
    exchange_rate = database.Column(database.Numeric(precision=20, scale=9))
    value_default = database.Column(database.Numeric(precision=20, scale=4))
    memo = database.Column(database.String(500), nullable=True)
    reference = database.Column(database.String(50))
    line_memo = database.Column(database.String(50), nullable=True)
    internal_reference = database.Column(database.String(50))
    internal_reference_id = database.Column(database.String(75))
    reference1 = database.Column(database.String(50))
    reference2 = database.Column(database.String(50))
    third_type = database.Column(database.String(26))
    third_code = database.Column(database.String(26))
    # Trazabilidad documental para detalle legacy
    voucher_type = database.Column(database.String(50), nullable=True, index=True)
    voucher_id = database.Column(database.String(26), nullable=True, index=True)
    document_no = database.Column(database.String(100), nullable=True, index=True)
    naming_series_id = database.Column(database.String(26), database.ForeignKey("naming_series.id"), nullable=True)


class ComprobanteContable(database.Model, BaseTransaccion):  # type: ignore[name-defined]
    """Comprobante contable manual."""

    __tablename__ = "comprobante_contable"
    voucher_type = database.Column(database.String(50), nullable=True, index=True)
    voucher_id = database.Column(database.String(26), nullable=True, index=True)
    document_no = database.Column(database.String(100), nullable=True, index=True)
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=True)
    book_codes = database.Column(database.Text(), nullable=True)
    transaction_currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    exchange_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    is_closing = database.Column(database.Boolean(), default=False, nullable=False)
    is_fiscal_year_closing = database.Column(database.Boolean(), default=False, nullable=False)
    fiscal_year_id = database.Column(
        database.String(26),
        database.ForeignKey(FISCAL_YEAR_ID, use_alter=True),
        nullable=True,
    )
    is_recurrent = database.Column(database.Boolean(), default=False, nullable=False)
    recurrent_template_id = database.Column(
        database.String(26), database.ForeignKey(RECURRING_JOURNAL_TEMPLATE_ID), nullable=True
    )
    recurrent_application_id = database.Column(
        database.String(26), database.ForeignKey("recurring_journal_application.id", use_alter=True), nullable=True
    )


class RecurringJournalTemplate(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Plantilla para comprobantes recurrentes."""

    __tablename__ = "recurring_journal_template"
    code = database.Column(database.String(50), unique=True, index=True, nullable=False)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    ledger_id = database.Column(database.String(26), database.ForeignKey(BOOK_ID), nullable=True, index=True)
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=True)
    book_codes = database.Column(database.Text(), nullable=True)
    name = database.Column(database.String(100), nullable=False)
    description = database.Column(database.Text(), nullable=True)
    start_date = database.Column(database.Date(), nullable=False)
    end_date = database.Column(database.Date(), nullable=False)
    # monthly, etc.
    frequency = database.Column(database.String(20), default="monthly", nullable=False)
    status = database.Column(database.String(20), default="draft", nullable=False, index=True)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    # 0=draft, 1=approved, 2=cancelled, 3=completed
    docstatus = database.Column(database.Integer(), default=0, nullable=False)
    approved_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    approved_at = database.Column(database.DateTime, nullable=True)
    cancelled_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    cancelled_at = database.Column(database.DateTime, nullable=True)
    cancel_reason = database.Column(database.Text(), nullable=True)
    last_applied_date = database.Column(database.Date(), nullable=True)
    is_completed = database.Column(database.Boolean(), default=False, nullable=False)


class RecurringJournalItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de plantilla para comprobantes recurrentes."""

    __tablename__ = "recurring_journal_item"
    template_id = database.Column(
        database.String(26), database.ForeignKey(RECURRING_JOURNAL_TEMPLATE_ID), nullable=False, index=True
    )
    account_code = database.Column(database.String(50), nullable=False)
    debit = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    credit = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    description = database.Column(database.String(200), nullable=True)
    cost_center = database.Column(database.String(10), nullable=True)
    unit = database.Column(database.String(10), nullable=True)
    project = database.Column(database.String(10), nullable=True)
    party_type = database.Column(database.String(20), nullable=True)
    party_id = database.Column(database.String(26), nullable=True)
    reference_type = database.Column(database.String(50), nullable=True)
    reference_name = database.Column(database.String(100), nullable=True)
    reference1 = database.Column(database.String(100), nullable=True)
    reference2 = database.Column(database.String(100), nullable=True)
    is_advance = database.Column(database.Boolean(), default=False, nullable=False)


class RecurringJournalApplication(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Registro de aplicacion de comprobante recurrente por periodo."""

    __tablename__ = "recurring_journal_application"
    __table_args__ = (
        UniqueConstraint(
            "company", "ledger_id", "template_id", "fiscal_year", "accounting_period", name="uq_recurring_application"
        ),
    )
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    ledger_id = database.Column(database.String(26), database.ForeignKey(BOOK_ID), nullable=True, index=True)
    template_id = database.Column(
        database.String(26), database.ForeignKey(RECURRING_JOURNAL_TEMPLATE_ID), nullable=False, index=True
    )
    fiscal_year = database.Column(database.String(50), nullable=False)
    accounting_period = database.Column(database.String(50), nullable=False)
    application_date = database.Column(database.Date(), nullable=False)
    # applied, failed, reversed, skipped
    status = database.Column(database.String(20), default="applied", nullable=False, index=True)
    journal_id = database.Column(
        database.String(26), database.ForeignKey("comprobante_contable.id", use_alter=True), nullable=True
    )
    applied_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    error_message = database.Column(database.Text(), nullable=True)


class ComprobanteContableDetalle(database.Model, GLBase):  # type: ignore[name-defined]
    """Comprobante contable manual detalle."""

    __tablename__ = "comprobante_contable_detalle"
    is_advance = database.Column(database.Boolean(), default=False, nullable=False)
    bank_account_id = database.Column(database.String(26), database.ForeignKey(BANK_ACCOUNT_ID), nullable=True, index=True)


class GLEntry(database.Model):  # type: ignore[name-defined]
    """Todos los registros que afecten estados financieros vienen de esta tabla.

    Multi-Ledger: cada entrada pertenece a un ledger_id (libro contable).
    Para cada transaccion se genera una gl_entry por cada libro activo.
    Libros disponibles: Fiscal, NIIF/IFRS, Board Review, Tax, etc.

    Dimensiones analiticas de primer nivel:
    - cost_center_code: Centro de Costos
    - unit_code: Unidad de Negocio (sucursal/oficina) — dimension analitica
    - project_code: Proyecto
    """

    __tablename__ = "gl_entry"
    __table_args__ = (
        database.Index("ix_gl_entry_voucher", "voucher_type", "voucher_id"),
        database.Index("ix_gl_entry_party", "party_type", "party_id"),
        database.Index("ix_gl_entry_company_date", "company", "posting_date"),
        database.Index("ix_gl_entry_ledger", "ledger_id", "posting_date"),
        database.Index("ix_gl_entry_reversal", "reversal_of"),
        ForeignKeyConstraint(["company", "cost_center_code"], ["cost_center.entity", "cost_center.code"]),
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_gl_entry_debit_credit_integrity",
        ),
        CheckConstraint("debit >= 0", name="ck_gl_entry_debit_non_negative"),
        CheckConstraint("credit >= 0", name="ck_gl_entry_credit_non_negative"),
    )

    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    posting_date = database.Column(database.Date(), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    # Libro contable al que pertenece esta entrada (Fiscal, NIIF, Board Review, etc.)
    ledger_id = database.Column(database.String(26), database.ForeignKey(BOOK_ID), nullable=True, index=True)
    account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True, index=True)
    account_code = database.Column(database.String(50), nullable=True, index=True)
    # Debito y credito en moneda base de la compania
    debit = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    credit = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    # Debito y credito en moneda original de la transaccion
    debit_in_account_currency = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    credit_in_account_currency = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    account_currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    company_currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    exchange_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    # Tercero (AR/AP) — requerido si la cuenta es receivable o payable
    party_type = database.Column(database.String(20), nullable=True, index=True)
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    bank_account_id = database.Column(database.String(26), database.ForeignKey(BANK_ACCOUNT_ID), nullable=True, index=True)
    is_advance = database.Column(database.Boolean(), default=False, nullable=False)
    is_fiscal_year_closing = database.Column(database.Boolean(), default=False, nullable=False)
    # Trazabilidad de voucher — permite rastrear el origen de cada entrada
    voucher_type = database.Column(database.String(50), nullable=False, index=True)
    voucher_id = database.Column(database.String(26), nullable=False, index=True)
    # Identificador documental (series) persistido para trazabilidad cruzada
    document_no = database.Column(database.String(100), nullable=True, index=True)
    naming_series_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID), nullable=True)
    # Periodo fiscal
    fiscal_year_id = database.Column(database.String(26), database.ForeignKey(FISCAL_YEAR_ID), nullable=True)
    accounting_period_id = database.Column(database.String(26), database.ForeignKey("accounting_period.id"), nullable=True)
    # Dimensiones analiticas de primer nivel
    cost_center_code = database.Column(database.String(10), nullable=True)
    # Unidad de negocio como dimension analitica (sucursal, oficina, punto de venta)
    unit_code = database.Column(database.String(10), database.ForeignKey("unit.code"), nullable=True)
    project_code = database.Column(database.String(10), database.ForeignKey("project.code"), nullable=True)
    remarks = database.Column(database.String(500), nullable=True)
    # Reversion contable append-only
    is_reversal = database.Column(database.Boolean(), default=False, nullable=False)
    reversal_of = database.Column(database.String(26), database.ForeignKey("gl_entry.id"), nullable=True)
    is_cancelled = database.Column(database.Boolean(), default=False, nullable=False)
    created = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    created_by = database.Column(database.String(26), nullable=True)
    modified = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=True,
    )
    modified_by = database.Column(database.String(26), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Accounting Dimensions — Dimensiones analiticas adicionales en GL.
# Complementan las dimensiones de primer nivel (cost_center, unit, project).
# <---------------------------------------------------------------------------------------------> #
class DimensionType(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Tipo de dimension analitica adicional."""

    __tablename__ = "dimension_type"
    name = database.Column(database.String(50), nullable=False, unique=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class DimensionValue(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Valor de una dimension analitica."""

    __tablename__ = "dimension_value"
    dimension_type_id = database.Column(
        database.String(26), database.ForeignKey("dimension_type.id"), nullable=False, index=True
    )
    value = database.Column(database.String(100), nullable=False)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class GLEntryDimension(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Dimension analitica adicional de una entrada GL (0..N por entrada)."""

    __tablename__ = "gl_entry_dimension"
    gl_entry_id = database.Column(database.String(26), database.ForeignKey("gl_entry.id"), nullable=False, index=True)
    dimension_type_id = database.Column(
        database.String(26), database.ForeignKey("dimension_type.id"), nullable=False, index=True
    )
    dimension_value_id = database.Column(
        database.String(26), database.ForeignKey("dimension_value.id"), nullable=False, index=True
    )


# <---------------------------------------------------------------------------------------------> #
# Account Mapping — Asignacion jerarquica de cuentas contables.
# Orden de resolucion: item_account > party_account > company_default_account
# <---------------------------------------------------------------------------------------------> #
class ItemAccount(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Asignacion de cuentas contables por item y compania."""

    __tablename__ = "item_account"
    __table_args__ = (UniqueConstraint("item_code", "company", name="uq_item_account"),)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    income_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    expense_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    inventory_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)


class PartyAccount(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Asignacion de cuentas contables por tercero y compania."""

    __tablename__ = "party_account"
    __table_args__ = (UniqueConstraint("party_id", "company", name="uq_party_account"),)
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    receivable_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    payable_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)


class CompanyDefaultAccount(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Cuentas contables predeterminadas por compania."""

    __tablename__ = "company_default_account"
    __table_args__ = (UniqueConstraint("company", name="uq_company_default_account"),)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, unique=True)
    default_receivable = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_payable = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_cash = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_bank = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_income = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_expense = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_inventory = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_cogs = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    inventory_adjustment_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    # Cuenta puente para conciliacion de recepciones con facturas de compra
    bridge_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    customer_advance_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    supplier_advance_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    bank_difference_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_sales_tax_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_purchase_tax_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    default_rounding_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    exchange_gain_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    exchange_loss_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    unrealized_exchange_gain_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    unrealized_exchange_loss_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    deferred_income_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    deferred_expense_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    payment_discount_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    period_profit_loss_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    retained_earnings_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Tax Structure — Impuestos (estructura sin logica de calculo).
# <---------------------------------------------------------------------------------------------> #
class Tax(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Definicion de impuesto."""

    __tablename__ = "tax"
    name = database.Column(database.String(100), nullable=False)
    rate = database.Column(database.Numeric(precision=10, scale=4), nullable=True)
    # percentage, fixed
    tax_type = database.Column(database.String(20), nullable=False)
    # purchase, sales, both
    applies_to = database.Column(database.String(20), default="both", nullable=False, index=True)
    account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    is_charge = database.Column(database.Boolean(), default=False, nullable=False)
    is_capitalizable = database.Column(database.Boolean(), default=False, nullable=False)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class TaxTemplate(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Plantilla de impuestos para aplicar a documentos."""

    __tablename__ = "tax_template"
    name = database.Column(database.String(100), nullable=False)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True)
    # buying, selling
    template_type = database.Column(database.String(20), default="selling", nullable=False, index=True)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class TaxTemplateItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de plantilla de impuestos."""

    __tablename__ = "tax_template_item"
    tax_template_id = database.Column(database.String(26), database.ForeignKey("tax_template.id"), nullable=False, index=True)
    tax_id = database.Column(database.String(26), database.ForeignKey("tax.id"), nullable=False, index=True)
    sequence = database.Column(database.Integer(), nullable=True)
    # net_line, net_document, previous_total
    calculation_base = database.Column(database.String(30), default="net_document", nullable=False)
    # additive, deductive
    behavior = database.Column(database.String(20), default="additive", nullable=False)
    is_inclusive = database.Column(database.Boolean(), default=False, nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Pricing — Listas de precios e items.
# <---------------------------------------------------------------------------------------------> #
class PriceList(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Lista de precios."""

    __tablename__ = "price_list"
    name = database.Column(database.String(100), nullable=False)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True)
    is_buying = database.Column(database.Boolean(), default=False, nullable=False)
    is_selling = database.Column(database.Boolean(), default=True, nullable=False)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class ItemPrice(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Precio de un item en una lista de precios."""

    __tablename__ = "item_price"
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    price_list_id = database.Column(database.String(26), database.ForeignKey("price_list.id"), nullable=False, index=True)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    price = database.Column(database.Numeric(precision=20, scale=4), nullable=False)
    min_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    valid_from = database.Column(database.Date(), nullable=True)
    valid_upto = database.Column(database.Date(), nullable=True)


class BankMatchingRule(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Regla configurable para matching de extractos bancarios."""

    __tablename__ = "bank_matching_rule"
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    bank_account_id = database.Column(database.String(26), database.ForeignKey("bank_account.id"), nullable=True, index=True)
    name = database.Column(database.String(100), nullable=False)
    days_tolerance = database.Column(database.Integer(), default=7, nullable=False)
    amount_tolerance = database.Column(database.Numeric(precision=20, scale=4), default=0, nullable=False)
    reference_contains = database.Column(database.String(100), nullable=True)
    priority = database.Column(database.Integer(), default=100, nullable=False, index=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False, index=True)


# <---------------------------------------------------------------------------------------------> #
# Reconciliation — Conciliacion de cuentas (AR, AP, Bancos).
# <---------------------------------------------------------------------------------------------> #
class Reconciliation(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Conciliacion de cuentas."""

    __tablename__ = "reconciliation"
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    party_id = database.Column(database.String(26), database.ForeignKey(PARTY_ID), nullable=True, index=True)
    recon_date = database.Column(database.Date(), nullable=False)
    # bank, AR, AP
    recon_type = database.Column(database.String(20), nullable=False)


class ReconciliationItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de conciliacion."""

    __tablename__ = "reconciliation_item"
    __table_args__ = (
        database.Index("ix_reconciliation_item_source", "source_type", "source_id"),
        database.Index("ix_reconciliation_item_target", "target_type", "target_id"),
    )
    reconciliation_id = database.Column(
        database.String(26), database.ForeignKey("reconciliation.id"), nullable=False, index=True
    )
    reference_type = database.Column(database.String(50), nullable=False)
    reference_id = database.Column(database.String(26), nullable=False, index=True)
    amount = database.Column(database.Numeric(precision=20, scale=4), nullable=False)
    allocated_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    reconciliation_date = database.Column(database.Date(), nullable=True, index=True)
    # draft, partial, reconciled, cancelled
    status = database.Column(database.String(20), default="reconciled", nullable=False, index=True)
    source_type = database.Column(database.String(50), nullable=True, index=True)
    source_id = database.Column(database.String(26), nullable=True, index=True)
    target_type = database.Column(database.String(50), nullable=True, index=True)
    target_id = database.Column(database.String(26), nullable=True, index=True)


# <---------------------------------------------------------------------------------------------> #
# Conciliacion de Compras — Framework moderno (process-first, event-driven).
# Concilia recepciones de mercancia con facturas de proveedor de forma desacoplada.
# <---------------------------------------------------------------------------------------------> #


class PurchaseMatchingConfig(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Configuracion de matching de compras por compania.

    Parametros configurables que permiten al usuario ajustar el motor de
    conciliacion sin alterar datos historicos.
    """

    __tablename__ = "purchase_matching_config"
    __table_args__ = (UniqueConstraint("company", name="uq_purchase_matching_config"),)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, unique=True)
    # 2-way: OC vs Factura | 3-way: OC vs Recepcion vs Factura
    matching_type = database.Column(database.String(10), default="3-way", nullable=False)
    # percentage | absolute
    price_tolerance_type = database.Column(database.String(10), default="percentage", nullable=False)
    price_tolerance_value = database.Column(database.Numeric(precision=10, scale=4), default=0, nullable=False)
    # percentage | absolute
    qty_tolerance_type = database.Column(database.String(10), default="percentage", nullable=False)
    qty_tolerance_value = database.Column(database.Numeric(precision=10, scale=4), default=0, nullable=False)
    # Si True, toda factura debe referenciar una OC
    require_purchase_order = database.Column(database.Boolean(), default=True, nullable=False)
    # Si True, se requiere cuenta puente configurada en CompanyDefaultAccount
    bridge_account_required = database.Column(database.Boolean(), default=True, nullable=False)
    # Si True, la conciliacion se ejecuta automaticamente al aprobar la factura
    auto_reconcile = database.Column(database.Boolean(), default=True, nullable=False)
    # Si True, diferencias de precio generan asiento de ajuste; False -> rechazo
    allow_price_difference = database.Column(database.Boolean(), default=False, nullable=False)


class PurchaseEconomicEvent(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Evento economico inmutable generado por documentos de compra.

    Los eventos son append-only y trazables.  Cada accion relevante del
    flujo de compras produce un evento que el motor contable puede consumir
    de forma independiente.
    """

    __tablename__ = "purchase_economic_event"
    # GOODS_RECEIVED | INVOICE_RECEIVED | MATCH_COMPLETED | MATCH_FAILED | MATCH_CANCELLED
    event_type = database.Column(database.String(30), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    # purchase_receipt | purchase_invoice | purchase_reconciliation
    document_type = database.Column(database.String(50), nullable=False, index=True)
    document_id = database.Column(database.String(26), nullable=False, index=True)
    payload = database.Column(database.Text(), nullable=True)
    # pending | processed | failed | skipped
    processing_status = database.Column(database.String(20), default="pending", nullable=False, index=True)
    processed_at = database.Column(database.DateTime(), nullable=True)


class PurchaseReconciliation(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Conciliacion de recepciones de compra con facturas de proveedor."""

    __tablename__ = "purchase_reconciliation"
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    purchase_order_id = database.Column(
        database.String(26), database.ForeignKey("purchase_order.id"), nullable=True, index=True
    )
    purchase_receipt_id = database.Column(
        database.String(26), database.ForeignKey("purchase_receipt.id"), nullable=True, index=True
    )
    purchase_invoice_id = database.Column(
        database.String(26), database.ForeignKey("purchase_invoice.id"), nullable=True, index=True
    )
    # matching_type snapshot from config at the time of reconciliation
    matching_type = database.Column(database.String(10), default="3-way", nullable=False)
    price_tolerance_type = database.Column(database.String(10), nullable=True)
    price_tolerance_value = database.Column(database.Numeric(precision=10, scale=4), nullable=True)
    qty_tolerance_type = database.Column(database.String(10), nullable=True)
    qty_tolerance_value = database.Column(database.Numeric(precision=10, scale=4), nullable=True)
    matched_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
    matched_date = database.Column(database.Date(), nullable=True)
    # pending_receipt | pending_invoice | partial | reconciled | disputed | cancelled
    status = database.Column(database.String(20), default="pending_receipt", nullable=False, index=True)


class PurchaseReconciliationItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Detalle de conciliacion de compra por linea de recepcion y factura."""

    __tablename__ = "purchase_reconciliation_item"
    __table_args__ = (
        database.Index("ix_purch_recon_item_order", "purchase_order_item_id"),
        database.Index("ix_purch_recon_item_receipt", "purchase_receipt_item_id"),
        database.Index("ix_purch_recon_item_invoice", "purchase_invoice_item_id"),
    )
    purchase_reconciliation_id = database.Column(
        database.String(26), database.ForeignKey("purchase_reconciliation.id"), nullable=False, index=True
    )
    purchase_order_item_id = database.Column(
        database.String(26), database.ForeignKey("purchase_order_item.id"), nullable=True, index=True
    )
    purchase_receipt_item_id = database.Column(
        database.String(26), database.ForeignKey("purchase_receipt_item.id"), nullable=True, index=True
    )
    purchase_invoice_item_id = database.Column(
        database.String(26), database.ForeignKey("purchase_invoice_item.id"), nullable=False, index=True
    )
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=True, index=True)
    uom = database.Column(database.String(20), database.ForeignKey(UOM_CODE), nullable=True)
    received_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    invoiced_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    matched_qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False)
    received_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=False)
    invoiced_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=False)
    matched_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=False)
    price_difference = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    # partial, reconciled, cancelled
    status = database.Column(database.String(20), default="reconciled", nullable=False, index=True)


# <---------------------------------------------------------------------------------------------> #
# Exchange Revaluation — Revalorizacion de saldos en moneda extranjera.
# <---------------------------------------------------------------------------------------------> #
class ExchangeRevaluation(database.Model, DocBase):  # type: ignore[name-defined]
    """Revalorizacion de moneda extranjera."""

    __tablename__ = "exchange_revaluation"
    target_account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=True)
    currency = database.Column(database.String(10), database.ForeignKey(CURRENCY_CODE), nullable=True)
    journal_entry_id = database.Column(database.String(26), nullable=True)


class ExchangeRevaluationItem(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Linea de revalorizacion de moneda extranjera."""

    __tablename__ = "exchange_revaluation_item"
    revaluation_id = database.Column(
        database.String(26), database.ForeignKey("exchange_revaluation.id"), nullable=False, index=True
    )
    reference_type = database.Column(database.String(50), nullable=False)
    reference_id = database.Column(database.String(26), nullable=False, index=True)
    old_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    new_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    difference_amount = database.Column(database.Numeric(precision=20, scale=4), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Period Close — Cockpit de cierre contable mensual.
# <---------------------------------------------------------------------------------------------> #
class PeriodCloseRun(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Ejecucion de cierre de periodo."""

    __tablename__ = "period_close_run"
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    period_id = database.Column(database.String(26), database.ForeignKey("accounting_period.id"), nullable=False, index=True)
    # open, in_progress, closed
    run_status = database.Column(database.String(20), nullable=False)
    closed_by = database.Column(database.String(15), nullable=True)
    closed_at = database.Column(database.DateTime, nullable=True)


class PeriodCloseCheck(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Verificacion realizada durante el cierre de periodo."""

    __tablename__ = "period_close_check"
    close_run_id = database.Column(database.String(26), database.ForeignKey("period_close_run.id"), nullable=False, index=True)
    check_type = database.Column(database.String(50), nullable=False)
    check_status = database.Column(database.String(20), nullable=False)
    message = database.Column(database.Text(), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# Collaboration — Comentarios, Asignaciones y Workflows.
# <---------------------------------------------------------------------------------------------> #
class Comment(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Comentario en cualquier registro del sistema."""

    __tablename__ = "comment"
    reference_type = database.Column(database.String(50), nullable=False, index=True)
    reference_id = database.Column(database.String(26), nullable=False, index=True)
    content = database.Column(database.Text(), nullable=False)
    is_deleted = database.Column(database.Boolean(), default=False, nullable=False)


class CommentMention(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Mencion de usuario en un comentario."""

    __tablename__ = "comment_mention"
    comment_id = database.Column(database.String(26), database.ForeignKey("comment.id"), nullable=False, index=True)
    user_id = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=False, index=True)


class Assignment(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Asignacion de un registro a un usuario."""

    __tablename__ = "assignment"
    reference_type = database.Column(database.String(50), nullable=False, index=True)
    reference_id = database.Column(database.String(26), nullable=False, index=True)
    assigned_to = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=False, index=True)
    assigned_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    # open, in_progress, completed, cancelled
    assignment_status = database.Column(database.String(20), nullable=False, default="open")
    due_date = database.Column(database.Date(), nullable=True)


class Workflow(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Definicion de flujo de trabajo."""

    __tablename__ = "workflow"
    name = database.Column(database.String(100), nullable=False)
    entity_type = database.Column(database.String(50), nullable=False, index=True)
    is_active = database.Column(database.Boolean(), default=True, nullable=False)


class WorkflowState(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Estado en un flujo de trabajo."""

    __tablename__ = "workflow_state"
    workflow_id = database.Column(database.String(26), database.ForeignKey("workflow.id"), nullable=False, index=True)
    name = database.Column(database.String(50), nullable=False)
    is_initial = database.Column(database.Boolean(), default=False, nullable=False)
    is_final = database.Column(database.Boolean(), default=False, nullable=False)


class WorkflowTransition(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Transicion entre estados de un flujo de trabajo."""

    __tablename__ = "workflow_transition"
    from_state_id = database.Column(database.String(26), database.ForeignKey(WORKFLOW_STATE_ID), nullable=False, index=True)
    to_state_id = database.Column(database.String(26), database.ForeignKey(WORKFLOW_STATE_ID), nullable=False, index=True)
    action_name = database.Column(database.String(100), nullable=False)
    role_required = database.Column(database.String(50), nullable=True)


class WorkflowInstance(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Instancia de un flujo de trabajo activo en un registro."""

    __tablename__ = "workflow_instance"
    workflow_id = database.Column(database.String(26), database.ForeignKey("workflow.id"), nullable=False, index=True)
    reference_type = database.Column(database.String(50), nullable=False, index=True)
    reference_id = database.Column(database.String(26), nullable=False, index=True)
    current_state_id = database.Column(database.String(26), database.ForeignKey(WORKFLOW_STATE_ID), nullable=True)


class WorkflowActionLog(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Log inmutable de acciones en instancias de workflow."""

    __tablename__ = "workflow_action_log"
    workflow_instance_id = database.Column(
        database.String(26), database.ForeignKey("workflow_instance.id"), nullable=False, index=True
    )
    action = database.Column(database.String(100), nullable=False)
    performed_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)
    performed_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    from_state = database.Column(database.String(50), nullable=True)
    to_state = database.Column(database.String(50), nullable=True)
    remarks = database.Column(database.Text(), nullable=True)


# <---------------------------------------------------------------------------------------------> #
# File Attachments — Archivos adjuntos.
# <---------------------------------------------------------------------------------------------> #
class File(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Archivo adjunto al sistema."""

    __tablename__ = "file"
    file_name = database.Column(database.String(255), nullable=False)
    file_path = database.Column(database.String(500), nullable=True)
    blob_reference = database.Column(database.String(500), nullable=True)
    file_size = database.Column(database.Integer(), nullable=True)
    mime_type = database.Column(database.String(100), nullable=True)
    uploaded_by = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True)


class FileAttachment(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Relacion entre un archivo y cualquier registro del sistema."""

    __tablename__ = "file_attachment"
    file_id = database.Column(database.String(26), database.ForeignKey("file.id"), nullable=False, index=True)
    reference_type = database.Column(database.String(50), nullable=False, index=True)
    reference_id = database.Column(database.String(26), nullable=False, index=True)


# <---------------------------------------------------------------------------------------------> #
# Audit Log — Auditoria real de cambios en datos criticos.
# <---------------------------------------------------------------------------------------------> #
class AuditLog(database.Model):  # type: ignore[name-defined]
    """Log de auditoria inmutable de cambios en registros criticos."""

    __tablename__ = "audit_log"
    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=obtiene_texto_unico,
    )
    entity_type = database.Column(database.String(50), nullable=False, index=True)
    entity_id = database.Column(database.String(26), nullable=False, index=True)
    # insert, update, delete
    action = database.Column(database.String(20), nullable=False)
    before_data = database.Column(database.Text(), nullable=True)
    after_data = database.Column(database.Text(), nullable=True)
    user_id = database.Column(database.String(26), database.ForeignKey("user.id"), nullable=True, index=True)
    timestamp = database.Column(database.DateTime, default=database.func.now(), nullable=False)


# <---------------------------------------------------------------------------------------------> #
# Snapshots — Vistas materializadas para performance de reportes.
# Son derivados recalculables — no son fuente de verdad.
# <---------------------------------------------------------------------------------------------> #
class AccountBalanceSnapshot(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Snapshot de saldo de cuenta contable para reportes rapidos."""

    __tablename__ = "account_balance_snapshot"
    __table_args__ = (UniqueConstraint("account_id", "company", "snapshot_date", name="uq_account_balance_snap"),)
    account_id = database.Column(database.String(26), database.ForeignKey(ACCOUNT_ID), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    snapshot_date = database.Column(database.Date(), nullable=False, index=True)
    debit_balance = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    credit_balance = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)
    net_balance = database.Column(database.Numeric(precision=20, scale=4), nullable=False, default=0)


class StockBalanceSnapshot(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Snapshot de stock por item y almacen para reportes rapidos."""

    __tablename__ = "stock_balance_snapshot"
    __table_args__ = (UniqueConstraint("item_code", "warehouse", "snapshot_date", name="uq_stock_balance_snap"),)
    item_code = database.Column(database.String(50), database.ForeignKey(ITEM_CODE), nullable=False, index=True)
    warehouse = database.Column(database.String(20), database.ForeignKey(WAREHOUSE_CODE), nullable=False, index=True)
    company = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False, index=True)
    snapshot_date = database.Column(database.Date(), nullable=False, index=True)
    qty = database.Column(database.Numeric(precision=20, scale=9), nullable=False, default=0)
    valuation_rate = database.Column(database.Numeric(precision=20, scale=9), nullable=True)
    stock_value = database.Column(database.Numeric(precision=20, scale=4), nullable=True)
