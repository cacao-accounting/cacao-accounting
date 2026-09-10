# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de contabilidad."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask_wtf import FlaskForm
from flask_babel import gettext as _
from cacao_accounting.i18n import _l
from wtforms import BooleanField, IntegerField, RadioField, SelectField, StringField, TextAreaField
from wtforms.fields import DateField, DecimalField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, ValidationError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import Entity
from cacao_accounting.setup.forms import CATALOG_CHOICES, COUNTRY_CHOICES, LANGUAGE_CHOICES

PADDING_DIGITOS = _l("Padding (digitos)")
CODIGO = _l("Código")
FECHA_INICIO = _l("Fecha Inicio")
FECHA_FIN = _l("Fecha Fin")
_LABEL_DESCRIPCION = _l("Descripción")

ACCOUNT_TYPE_CHOICES = [
    ("", _l("— Seleccione —")),
    ("asset", _l("Activo")),
    ("liability", _l("Pasivo")),
    ("equity", _l("Patrimonio")),
    ("income", _l("Ingreso")),
    ("expense", _l("Gasto")),
    ("cash", _l("Efectivo")),
    ("petty_cash", _l("Caja Chica")),
    ("bank", _l("Banco")),
    ("receivable", _l("Cuentas por Cobrar")),
    ("payable", _l("Cuentas por Pagar")),
    ("inventory", _l("Inventario")),
    ("cost_of_goods_sold", _l("Costo de ventas")),
    ("inventory_adjustment", _l("Ajuste de inventario")),
    ("bridge", _l("Cuenta puente")),
    ("customer_advance", _l("Anticipo de clientes")),
    ("supplier_advance", _l("Anticipo a proveedores")),
    ("bank_difference", _l("Diferencia bancaria")),
    ("tax", _l("Impuesto")),
    ("rounding", _l("Redondeo")),
    ("exchange_gain", _l("Ganancia cambiaria")),
    ("exchange_loss", _l("Pérdida cambiaria")),
    ("unrealized_exchange_gain", _l("Ganancia cambiaria no realizada")),
    ("unrealized_exchange_loss", _l("Pérdida cambiaria no realizada")),
    ("deferred_income", _l("Ingreso diferido")),
    ("deferred_expense", _l("Gasto diferido")),
    ("payment_discount", _l("Descuento de pago")),
    ("period_profit_loss", _l("Resultado del período")),
    ("retained_earnings", _l("Utilidades retenidas")),
]

# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades


class FormularioEntidad(FlaskForm):
    """
    Formulario base para la administración de entidades.

    Este formulario este vinculada la la tabla Entidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(_l("Código"), validators=[DataRequired()])
    razon_social = StringField(_l("Razón social"), validators=[DataRequired()])
    nombre_comercial = StringField(_l("Nombre comercial"), validators=[])
    id_fiscal = StringField(_l("Identificación fiscal"), validators=[DataRequired()])
    pais = SelectField(_l("País"), choices=COUNTRY_CHOICES, validators=[DataRequired()])
    idioma = SelectField(_l("Idioma"), choices=LANGUAGE_CHOICES, validators=[DataRequired()])
    moneda = SelectField(_l("Moneda Principal"), choices=[], validators=[DataRequired()])
    inicio_anio_fiscal = DateField(_l("Inicio Año Fiscal"), validators=[Optional()])
    fin_anio_fiscal = DateField(_l("Fin Año Fiscal"), validators=[Optional()])
    catalogo = RadioField(
        _l("Catálogo contable"), choices=CATALOG_CHOICES, default="preexistente", validators=[DataRequired()]
    )
    catalogo_origen = SelectField(_l("Catálogo existente"), choices=[], validators=[])
    tipo_entidad = SelectField(_l("Tipo de Entidad"), choices=Entity.tipo_entidad_lista, validators=[DataRequired()])
    correo_electronico = StringField(_l("Correo electrónico"), validators=[])
    web = StringField(_l("Sitio web"), validators=[])
    telefono1 = StringField(_l("Teléfono 1"), validators=[])
    telefono2 = StringField(_l("Teléfono 2"), validators=[])
    fax = StringField(_l("Fax"), validators=[])
    habilitado = BooleanField(_l("Habilitado"), default=True)


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades
class FormularioUnidad(FlaskForm):
    """
    Formulario base para la administración de unidades de negocio.

    Este formulario este vinculada la la tabla Unidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(_l("Código"), validators=[DataRequired()])
    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"))
    parent_id = SelectField(_l("Unidad Padre"), choices=[], validators=[Optional()], validate_choice=False)
    correo_electronico = StringField(_l("Correo electrónico"), validators=[])
    web = StringField(_l("Sitio web"), validators=[])
    telefono1 = StringField(_l("Teléfono 1"), validators=[])
    telefono2 = StringField(_l("Teléfono 2"), validators=[])
    fax = StringField(_l("Fax"), validators=[])
    habilitado = BooleanField(_l("Habilitado"), default=True)


class FormularioLibro(FlaskForm):
    """Formulario base para la administración de libros de contabilidad."""

    id = StringField(_l("Código"), validators=[DataRequired()])
    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"), validators=[DataRequired()])
    moneda = SelectField(_l("Moneda"), choices=[], validators=[DataRequired()])
    estado = SelectField(
        _l("Estado"),
        choices=[("activo", _l("Activo")), ("inactivo", _l("Inactivo"))],
        default="activo",
        validators=[DataRequired()],
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Comprobantes Contables
class ComprobanteContable(FlaskForm):
    """Comprobante contable manual."""


class ComprobanteContableDetalle(FlaskForm):
    """Detalle de comprobante contable manual."""


# <------------------------------------------------------------------------------------------------------------------------> #
# NamingSeries — Framework robusto de series e identificadores

ENTITY_TYPE_CHOICES = [
    ("", _l("— Seleccione tipo de documento —")),
    ("journal_entry", _l("Comprobante de Diario")),
    ("exchange_revaluation", _l("Revalorizacion Cambiaria")),
    ("sales_invoice", _l("Factura de Venta")),
    ("purchase_invoice", _l("Factura de Compra")),
    ("payment_entry", _l("Pago")),
    ("stock_entry", _l("Movimiento de Inventario")),
    ("purchase_order", _l("Orden de Compra")),
    ("purchase_receipt", _l("Recepcion de Compra")),
    ("purchase_request", _l("Solicitud de Compra")),
    ("purchase_quotation", _l("Solicitud de Cotizacion")),
    ("supplier_quotation", _l("Cotizacion de Proveedor")),
    ("sales_order", _l("Orden de Venta")),
    ("sales_request", _l("Pedido de Venta")),
    ("sales_quotation", _l("Cotizacion de Venta")),
    ("delivery_note", _l("Nota de Entrega")),
    ("bank_payment", _l("Pago a Proveedor (Banco)")),
    ("bank_receipt", _l("Cobro de Cliente (Banco)")),
    ("bank_transfer", _l("Transferencia Bancaria")),
    ("bank_debit_note", _l("Nota de Debito Bancaria")),
    ("bank_credit_note", _l("Nota de Credito Bancaria")),
]

RESET_POLICY_CHOICES = [
    ("never", _l("Nunca")),
    ("yearly", _l("Anual")),
    ("monthly", _l("Mensual")),
]

EXTERNAL_COUNTER_TYPE_CHOICES = [
    ("checkbook", _l("Chequera")),
    ("fiscal", _l("Numero Fiscal")),
    ("receipt", _l("Recibo Preimpreso")),
    ("bank_transfer", _l("Transferencia Bancaria")),
    ("other", _l("Otro")),
]


class FormularioNamingSeries(FlaskForm):
    """Formulario para crear y editar series de numeracion (NamingSeries)."""

    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    entity_type = SelectField(_l("Tipo de Documento"), choices=ENTITY_TYPE_CHOICES, validators=[DataRequired()])
    company = SelectField(_l("Compania (opcional — dejar vacio para serie global)"), validators=[Optional()])
    prefix_template = StringField(_l("Plantilla de Prefijo"), validators=[DataRequired()])
    current_value = IntegerField(
        _l("Ultimo Numero Interno Usado"), default=0, validators=[InputRequired(), NumberRange(min=0)]
    )
    increment = IntegerField(_l("Incremento"), default=1, validators=[InputRequired(), NumberRange(min=1)])
    padding = IntegerField(PADDING_DIGITOS, default=5, validators=[InputRequired(), NumberRange(min=1, max=20)])
    reset_policy = SelectField(_l("Politica de Reinicio"), choices=RESET_POLICY_CHOICES)
    is_active = BooleanField(_l("Activa"), default=True)
    is_default = BooleanField(_l("Predeterminada para esta compania y documento"))


class FormularioMoneda(FlaskForm):
    """Formulario para crear y editar monedas."""

    code = StringField(CODIGO, validators=[DataRequired(), Length(max=10)])
    name = StringField(_l("Nombre"), validators=[DataRequired()])
    decimals = IntegerField(_l("Decimales"), default=2, validators=[Optional(), NumberRange(min=0, max=8)])
    active = BooleanField(_l("Activo"), default=True)
    default = BooleanField(_l("Predeterminada"), default=False)


class FormularioTasaCambio(FlaskForm):
    """Formulario para crear tasas de cambio."""

    origin = SelectField(_l("Moneda Base"), validators=[DataRequired()])
    destination = SelectField(_l("Moneda Destino"), validators=[DataRequired()])
    rate = DecimalField(_l("Tasa"), places=9, validators=[DataRequired(), NumberRange(min=0)])
    date = DateField(_l("Fecha"), validators=[DataRequired()])


CLASSIFICATION_CHOICES = [
    ("", _l("— Seleccione —")),
    ("activo", _l("Activo")),
    ("pasivo", _l("Pasivo")),
    ("patrimonio", _l("Patrimonio")),
    ("ingreso", _l("Ingreso")),
    ("costo", _l("Costo")),
    ("gasto", _l("Gasto")),
]


def validar_clasificacion_de_cuenta(formulario, campo):
    """Valida la clasificación de la cuenta contra la lista permitida.

    Acepta aliases históricos (plurales y valores en inglés usados por los
    catálogos precargados) pero rechaza valores arbitrarios que dejarían a la
    cuenta fuera del balance general y del estado de resultados.
    """
    valor = (campo.data or "").strip()
    if not valor:
        return
    from cacao_accounting.reportes.services import account_classification_is_known

    if not account_classification_is_known(valor):
        raise ValidationError(_("Clasificación no permitida para cuentas contables."))


class FormularioCuenta(FlaskForm):
    """Formulario para crear y editar cuentas contables."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField(_l("Nombre"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"), validators=[DataRequired()])
    grupo = BooleanField(_l("Grupo"), default=False)
    padre = SelectField(_l("Cuenta Padre"), choices=[], validators=[Optional()])
    clasificacion = SelectField(
        _l("Clasificación"),
        choices=CLASSIFICATION_CHOICES,
        validators=[Optional(), validar_clasificacion_de_cuenta],
        validate_choice=False,
        default="",
    )
    account_type = SelectField(
        _l("Tipo de Cuenta"),
        choices=ACCOUNT_TYPE_CHOICES,
        validators=[Optional()],
    )
    activo = BooleanField(_l("Activo"), default=True)


class FormularioCentroCosto(FlaskForm):
    """Formulario para crear y editar centros de costos."""

    id = StringField(_l("Codigo"), validators=[DataRequired()])
    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"), validators=[DataRequired()])
    activo = BooleanField(_l("Activo"), default=True)
    predeterminado = BooleanField(_l("Predeterminado"), default=False)
    grupo = BooleanField(_l("Grupo"), default=False)
    padre = SelectField(_l("Centro Padre"), choices=[], validators=[Optional()])


class FormularioProyecto(FlaskForm):
    """Formulario para crear y editar proyectos."""

    id = StringField(_l("Codigo"), validators=[DataRequired()])
    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"), validators=[DataRequired()])
    parent_id = SelectField(_l("Proyecto Padre"), choices=[], validators=[Optional()], validate_choice=False)
    inicio = DateField(FECHA_INICIO, validators=[Optional()])
    fin = DateField(FECHA_FIN, validators=[Optional()])
    presupuesto = DecimalField(_l("Presupuesto"), places=2, validators=[Optional(), NumberRange(min=0)])
    habilitado = BooleanField(_l("Habilitado"), default=True)
    status = SelectField(
        _l("Estado"),
        choices=[
            ("open", _l("Abierto")),
            ("closed", _l("Cerrado")),
            ("paused", _l("Detenido")),
        ],
        default="open",
        validators=[DataRequired()],
    )
    capitalizable = BooleanField(_l("Capitalizable"), default=False)
    capitalization_account_id = SelectField(
        _l("Cuenta de Activo de Capitalización"), choices=[], validators=[Optional()], validate_choice=False
    )


class FormularioFiscalYear(FlaskForm):
    """Formulario para crear y editar años fiscales."""

    id = StringField(_l("Codigo"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"), validators=[DataRequired()])
    inicio = DateField(FECHA_INICIO, validators=[DataRequired()])
    fin = DateField(FECHA_FIN, validators=[DataRequired()])
    cerrado = BooleanField(_l("Cerrado"), default=False)


class FormularioAccountingPeriod(FlaskForm):
    """Formulario para crear y editar periodos contables."""

    id = StringField(_l("Codigo"), validators=[DataRequired()])
    entidad = SelectField(_l("Entidad"), validators=[DataRequired()])
    fiscal_year = SelectField(_l("Año Fiscal"), validators=[DataRequired()])
    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    habilitado = BooleanField(_l("Habilitado"), default=True)
    inicio = DateField(FECHA_INICIO, validators=[DataRequired()])
    fin = DateField(FECHA_FIN, validators=[DataRequired()])


class FormularioSecuencia(FlaskForm):
    """Formulario para crear y editar secuencias fisicas (Sequence)."""

    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    current_value = IntegerField(_l("Valor Actual"), default=0, validators=[NumberRange(min=0)])
    increment = IntegerField(_l("Incremento"), default=1, validators=[NumberRange(min=1)])
    padding = IntegerField(PADDING_DIGITOS, default=5, validators=[NumberRange(min=1, max=20)])
    reset_policy = SelectField(_l("Politica de Reinicio"), choices=RESET_POLICY_CHOICES)


class FormularioExternalCounter(FlaskForm):
    """Formulario para crear y editar contadores externos."""

    company = SelectField(_l("Compania"), validators=[DataRequired()])
    nombre = StringField(_l("Nombre"), validators=[DataRequired()])
    counter_type = SelectField(_l("Tipo"), choices=EXTERNAL_COUNTER_TYPE_CHOICES)
    prefix = StringField(_l("Prefijo"), validators=[Optional()])
    last_used = IntegerField(_l("Ultimo Numero Usado"), default=0, validators=[NumberRange(min=0)])
    padding = IntegerField(PADDING_DIGITOS, default=5, validators=[NumberRange(min=1, max=20)])
    is_active = BooleanField(_l("Activo"), default=True)
    description = TextAreaField(_l("Descripcion"), validators=[Optional()])
    naming_series_id = SelectField(_l("Serie Interna Asociada (opcional)"), validators=[Optional()])


class FormularioAjusteContadorExterno(FlaskForm):
    """Formulario de ajuste de ultimo numero usado con motivo obligatorio."""

    new_last_used = IntegerField(_l("Nuevo Ultimo Numero Usado"), validators=[InputRequired(), NumberRange(min=0)])
    reason = TextAreaField(_l("Motivo del Ajuste"), validators=[DataRequired()])


class FormularioRecurringJournalTemplate(FlaskForm):
    """Formulario para plantillas de comprobantes recurrentes."""

    code = StringField(CODIGO, validators=[DataRequired()])
    company = SelectField(_l("Entidad"), validators=[DataRequired()])
    ledger_id = SelectField(_l("Libro"), validators=[DataRequired()], validate_choice=False)
    name = StringField(_l("Nombre de la Plantilla"), validators=[DataRequired()])
    description = TextAreaField(_LABEL_DESCRIPCION, validators=[Optional()])
    start_date = DateField(FECHA_INICIO, validators=[DataRequired()])
    end_date = DateField(FECHA_FIN, validators=[DataRequired()])
    frequency = SelectField(
        _l("Frecuencia"),
        choices=[
            ("monthly", _l("Mensual")),
            ("weekly", _l("Semanal")),
            ("daily", _l("Diario")),
        ],
        default="monthly",
        validators=[DataRequired()],
    )
    currency = SelectField(_l("Moneda"), validators=[DataRequired()])


class FormularioBudget(FlaskForm):
    """Formulario para el encabezado del presupuesto."""

    company = SelectField(_l("Compañía"), validators=[DataRequired()])
    ledger_id = SelectField(_l("Libro Contable"), validators=[DataRequired()], validate_choice=False)
    fiscal_year_id = SelectField(_l("Año Fiscal"), validators=[DataRequired()], validate_choice=False)
    budget_code = StringField(CODIGO, validators=[DataRequired(), Length(max=50)])
    name = StringField(_l("Nombre"), validators=[DataRequired(), Length(max=100)])
    description = TextAreaField(_LABEL_DESCRIPCION, validators=[Optional()])
    currency_id = SelectField(_l("Moneda"), validators=[DataRequired()])


class FormularioBudgetLine(FlaskForm):
    """Formulario para una línea de presupuesto."""

    account_id = SelectField(_l("Cuenta Contable"), validators=[DataRequired()], validate_choice=False)
    cost_center_id = SelectField(_l("Centro de Costo"), validators=[DataRequired()], validate_choice=False)
    business_unit_id = SelectField(_l("Unidad de Negocio"), validators=[Optional()], validate_choice=False)
    project_id = SelectField(_l("Proyecto"), validators=[Optional()], validate_choice=False)
    period_id = SelectField(_l("Período Contable"), validators=[DataRequired()], validate_choice=False)
    amount = DecimalField(_l("Monto"), places=4, validators=[InputRequired(), NumberRange(min=0)])
    description = StringField(_LABEL_DESCRIPCION, validators=[Optional(), Length(max=200)])
