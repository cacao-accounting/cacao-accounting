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
from wtforms import BooleanField, IntegerField, RadioField, SelectField, StringField, TextAreaField
from wtforms.fields import DateField, DecimalField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import Entity
from cacao_accounting.setup.forms import CATALOG_CHOICES, COUNTRY_CHOICES, LANGUAGE_CHOICES

# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades


class FormularioEntidad(FlaskForm):
    """
    Formulario base para la administración de entidades.

    Este formulario este vinculada la la tabla Entidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(validators=[DataRequired()])
    razon_social = StringField(validators=[DataRequired()])
    nombre_comercial = StringField(validators=[])
    id_fiscal = StringField(validators=[DataRequired()])
    pais = SelectField("País", choices=COUNTRY_CHOICES, validators=[DataRequired()])
    idioma = SelectField("Idioma", choices=LANGUAGE_CHOICES, validators=[DataRequired()])
    moneda = SelectField("Moneda Principal", choices=[], validators=[DataRequired()])
    inicio_anio_fiscal = DateField("Inicio Año Fiscal", validators=[Optional()])
    fin_anio_fiscal = DateField("Fin Año Fiscal", validators=[Optional()])
    catalogo = RadioField("Catálogo contable", choices=CATALOG_CHOICES, default="preexistente", validators=[DataRequired()])
    catalogo_origen = SelectField("Catálogo existente", choices=[], validators=[])
    tipo_entidad = SelectField("Tipo de Entidad", choices=Entity.tipo_entidad_lista, validators=[DataRequired()])
    correo_electronico = StringField(validators=[])
    web = StringField(validators=[])
    telefono1 = StringField(validators=[])
    telefono2 = StringField(validators=[])
    fax = StringField(validators=[])
    habilitado = BooleanField("Habilitado", default=True)


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades
class FormularioUnidad(FlaskForm):
    """
    Formulario base para la administración de unidades de negocio.

    Este formulario este vinculada la la tabla Unidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(validators=[DataRequired()])
    nombre = StringField(validators=[DataRequired()])
    entidad = SelectField("Entidad")
    correo_electronico = StringField(validators=[])
    web = StringField(validators=[])
    telefono1 = StringField(validators=[])
    telefono2 = StringField(validators=[])
    fax = StringField(validators=[])
    habilitado = BooleanField("Habilitado", default=True)


class FormularioLibro(FlaskForm):
    """Formulario base para la administración de libros de contabilidad."""

    id = StringField(validators=[DataRequired()])
    nombre = StringField(validators=[DataRequired()])
    entidad = SelectField("Entidad", validators=[DataRequired()])
    moneda = SelectField("Moneda", choices=[], validators=[DataRequired()])
    estado = SelectField(
        "Estado",
        choices=[("activo", "Activo"), ("inactivo", "Inactivo")],
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
    ("", "— Seleccione tipo de documento —"),
    ("journal_entry", "Comprobante de Diario"),
    ("sales_invoice", "Factura de Venta"),
    ("purchase_invoice", "Factura de Compra"),
    ("payment_entry", "Pago"),
    ("stock_entry", "Movimiento de Inventario"),
    ("purchase_order", "Orden de Compra"),
    ("purchase_receipt", "Recepcion de Compra"),
    ("purchase_request", "Solicitud de Compra"),
    ("purchase_quotation", "Solicitud de Cotizacion"),
    ("supplier_quotation", "Cotizacion de Proveedor"),
    ("sales_order", "Orden de Venta"),
    ("sales_request", "Pedido de Venta"),
    ("sales_quotation", "Cotizacion de Venta"),
    ("delivery_note", "Nota de Entrega"),
]

RESET_POLICY_CHOICES = [
    ("never", "Nunca"),
    ("yearly", "Anual"),
    ("monthly", "Mensual"),
]

EXTERNAL_COUNTER_TYPE_CHOICES = [
    ("checkbook", "Chequera"),
    ("fiscal", "Numero Fiscal"),
    ("receipt", "Recibo Preimpreso"),
    ("bank_transfer", "Transferencia Bancaria"),
    ("other", "Otro"),
]


class FormularioNamingSeries(FlaskForm):
    """Formulario para crear y editar series de numeracion (NamingSeries)."""

    nombre = StringField("Nombre", validators=[DataRequired()])
    entity_type = SelectField("Tipo de Documento", choices=ENTITY_TYPE_CHOICES, validators=[DataRequired()])
    company = SelectField("Compania (opcional — dejar vacio para serie global)", validators=[Optional()])
    prefix_template = StringField("Plantilla de Prefijo", validators=[DataRequired()])
    current_value = IntegerField("Ultimo Numero Interno Usado", default=0, validators=[InputRequired(), NumberRange(min=0)])
    increment = IntegerField("Incremento", default=1, validators=[InputRequired(), NumberRange(min=1)])
    padding = IntegerField("Padding (digitos)", default=5, validators=[InputRequired(), NumberRange(min=1, max=20)])
    reset_policy = SelectField("Politica de Reinicio", choices=RESET_POLICY_CHOICES)
    is_active = BooleanField("Activa", default=True)
    is_default = BooleanField("Predeterminada para esta compania y documento")


class FormularioMoneda(FlaskForm):
    """Formulario para crear y editar monedas."""

    code = StringField("Código", validators=[DataRequired(), Length(max=10)])
    name = StringField("Nombre", validators=[DataRequired()])
    decimals = IntegerField("Decimales", default=2, validators=[Optional(), NumberRange(min=0, max=8)])
    active = BooleanField("Activo", default=True)
    default = BooleanField("Predeterminada", default=False)


class FormularioTasaCambio(FlaskForm):
    """Formulario para crear tasas de cambio."""

    origin = SelectField("Moneda Base", validators=[DataRequired()])
    destination = SelectField("Moneda Destino", validators=[DataRequired()])
    rate = DecimalField("Tasa", places=9, validators=[DataRequired(), NumberRange(min=0)])
    date = DateField("Fecha", validators=[DataRequired()])


class FormularioCuenta(FlaskForm):
    """Formulario para crear y editar cuentas contables."""

    code = StringField("Código", validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])
    entidad = SelectField("Entidad", validators=[DataRequired()])
    grupo = BooleanField("Grupo", default=False)
    padre = SelectField("Cuenta Padre", choices=[], validators=[Optional()])
    clasificacion = SelectField(
        "Clasificación",
        choices=[
            ("", "— Seleccione —"),
            ("activo", "Activo"),
            ("pasivo", "Pasivo"),
            ("patrimonio", "Patrimonio"),
            ("ingresos", "Ingresos"),
            ("gastos", "Gastos"),
        ],
        validators=[Optional()],
    )
    account_type = SelectField(
        "Tipo de Cuenta",
        choices=[
            ("", "— Seleccione —"),
            ("receivable", "Cuentas por Cobrar"),
            ("payable", "Cuentas por Pagar"),
            ("bank", "Banco"),
            ("cash", "Efectivo"),
            ("expense", "Gasto"),
            ("income", "Ingreso"),
            ("asset", "Activo"),
            ("liability", "Pasivo"),
        ],
        validators=[Optional()],
    )
    activo = BooleanField("Activo", default=True)


class FormularioCentroCosto(FlaskForm):
    """Formulario para crear y editar centros de costos."""

    id = StringField("Codigo", validators=[DataRequired()])
    nombre = StringField("Nombre", validators=[DataRequired()])
    entidad = SelectField("Entidad", validators=[DataRequired()])
    activo = BooleanField("Activo", default=True)
    predeterminado = BooleanField("Predeterminado", default=False)
    grupo = BooleanField("Grupo", default=False)
    padre = SelectField("Centro Padre", choices=[], validators=[Optional()])


class FormularioProyecto(FlaskForm):
    """Formulario para crear y editar proyectos."""

    id = StringField("Codigo", validators=[DataRequired()])
    nombre = StringField("Nombre", validators=[DataRequired()])
    entidad = SelectField("Entidad", validators=[DataRequired()])
    inicio = DateField("Fecha Inicio", validators=[Optional()])
    fin = DateField("Fecha Fin", validators=[Optional()])
    presupuesto = DecimalField("Presupuesto", places=2, validators=[Optional(), NumberRange(min=0)])
    habilitado = BooleanField("Habilitado", default=True)
    status = SelectField(
        "Estado",
        choices=[
            ("open", "Abierto"),
            ("closed", "Cerrado"),
            ("paused", "Detenido"),
        ],
        default="open",
        validators=[DataRequired()],
    )


class FormularioFiscalYear(FlaskForm):
    """Formulario para crear y editar años fiscales."""

    id = StringField("Codigo", validators=[DataRequired()])
    entidad = SelectField("Entidad", validators=[DataRequired()])
    inicio = DateField("Fecha Inicio", validators=[DataRequired()])
    fin = DateField("Fecha Fin", validators=[DataRequired()])
    cerrado = BooleanField("Cerrado", default=False)


class FormularioAccountingPeriod(FlaskForm):
    """Formulario para crear y editar periodos contables."""

    id = StringField("Codigo", validators=[DataRequired()])
    entidad = SelectField("Entidad", validators=[DataRequired()])
    fiscal_year = SelectField("Año Fiscal", validators=[DataRequired()])
    nombre = StringField("Nombre", validators=[DataRequired()])
    status = StringField("Estado", validators=[DataRequired()])
    habilitado = BooleanField("Habilitado", default=True)
    cerrado = BooleanField("Cerrado", default=False)
    inicio = DateField("Fecha Inicio", validators=[DataRequired()])
    fin = DateField("Fecha Fin", validators=[DataRequired()])


class FormularioSecuencia(FlaskForm):
    """Formulario para crear y editar secuencias fisicas (Sequence)."""

    nombre = StringField("Nombre", validators=[DataRequired()])
    current_value = IntegerField("Valor Actual", default=0, validators=[NumberRange(min=0)])
    increment = IntegerField("Incremento", default=1, validators=[NumberRange(min=1)])
    padding = IntegerField("Padding (digitos)", default=5, validators=[NumberRange(min=1, max=20)])
    reset_policy = SelectField("Politica de Reinicio", choices=RESET_POLICY_CHOICES)


class FormularioExternalCounter(FlaskForm):
    """Formulario para crear y editar contadores externos."""

    company = SelectField("Compania", validators=[DataRequired()])
    nombre = StringField("Nombre", validators=[DataRequired()])
    counter_type = SelectField("Tipo", choices=EXTERNAL_COUNTER_TYPE_CHOICES)
    prefix = StringField("Prefijo", validators=[Optional()])
    last_used = IntegerField("Ultimo Numero Usado", default=0, validators=[NumberRange(min=0)])
    padding = IntegerField("Padding (digitos)", default=5, validators=[NumberRange(min=1, max=20)])
    is_active = BooleanField("Activo", default=True)
    description = TextAreaField("Descripcion", validators=[Optional()])
    naming_series_id = SelectField("Serie Interna Asociada (opcional)", validators=[Optional()])


class FormularioAjusteContadorExterno(FlaskForm):
    """Formulario de ajuste de ultimo numero usado con motivo obligatorio."""

    new_last_used = IntegerField("Nuevo Ultimo Numero Usado", validators=[InputRequired(), NumberRange(min=0)])
    reason = TextAreaField("Motivo del Ajuste", validators=[DataRequired()])


class FormularioRecurringJournalTemplate(FlaskForm):
    """Formulario para plantillas de comprobantes recurrentes."""

    code = StringField("Código", validators=[DataRequired()])
    company = SelectField("Entidad", validators=[DataRequired()])
    ledger_id = SelectField("Libro", validators=[DataRequired()])
    name = StringField("Nombre de la Plantilla", validators=[DataRequired()])
    description = TextAreaField("Descripción", validators=[Optional()])
    start_date = DateField("Fecha Inicio", validators=[DataRequired()])
    end_date = DateField("Fecha Fin", validators=[DataRequired()])
    frequency = SelectField(
        "Frecuencia",
        choices=[("monthly", "Mensual"), ("weekly", "Semanal"), ("daily", "Diario")],
        default="monthly",
        validators=[DataRequired()],
    )
    currency = SelectField("Moneda", validators=[DataRequired()])
