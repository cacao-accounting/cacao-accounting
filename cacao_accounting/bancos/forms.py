# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de bancos."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

_LABEL_COMPANY = "Compañía"


class FormularioBanco(FlaskForm):
    """Formulario para crear o editar un banco."""

    name = StringField("Nombre", validators=[DataRequired()])
    swift_code = StringField("Código SWIFT")


class FormularioCuentaBancaria(FlaskForm):
    """Formulario para crear o editar una cuenta bancaria."""

    bank_id = SelectField("Banco", choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    account_name = StringField("Nombre de Cuenta", validators=[DataRequired()])
    account_no = StringField("Número de Cuenta")
    iban = StringField("IBAN")
    currency = SelectField("Moneda", choices=[])
    gl_account_id = SelectField("Cuenta contable bancaria", choices=[], validators=[Optional()])
    default_naming_series_id = SelectField("Serie interna para pagos", choices=[], validators=[Optional()])
    default_external_counter_id = SelectField("Chequera", choices=[], validators=[Optional()])


class FormularioCajaChica(FlaskForm):
    """Formulario para crear o editar una caja chica."""

    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])
    account_id = SelectField("Cuenta contable de Caja Chica", choices=[], validators=[Optional()])
    currency = SelectField("Moneda", choices=[])
    custodian_id = SelectField("Responsable", choices=[], validators=[Optional()])
    float_amount = StringField("Fondo autorizado")
    is_default = BooleanField("Predeterminada", default=False)
    is_active = BooleanField("Activa", default=True)
    notes = TextAreaField("Notas", validators=[Optional()])


class FormularioPettyCashVoucher(FlaskForm):
    """Formulario para crear un vale de caja chica (control de efectivo, no postea al GL)."""

    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    petty_cash_id = SelectField("Caja Chica", choices=[], validators=[DataRequired()])
    naming_series = SelectField("Serie", choices=[], validators=[Optional()])
    posting_date = StringField("Fecha")
    delivered_to = StringField("Entregado a")
    concept = StringField("Concepto", validators=[DataRequired()])
    amount = StringField("Importe", validators=[DataRequired()])
    cost_center_code = SelectField("Centro de costo", choices=[], validators=[Optional()])
    unit_code = SelectField("Unidad de negocio", choices=[], validators=[Optional()])
    project_code = SelectField("Proyecto", choices=[], validators=[Optional()])
    comments = TextAreaField("Comentario", validators=[Optional()])


class FormularioPettyCashExpense(FlaskForm):
    """Formulario para crear un gasto de caja chica (si genera asiento contable)."""

    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    petty_cash_id = SelectField("Caja Chica", choices=[], validators=[DataRequired()])
    naming_series = SelectField("Serie", choices=[], validators=[Optional()])
    voucher_id = SelectField("Vale origen", choices=[], validators=[Optional()])
    posting_date = StringField("Fecha")
    beneficiary = StringField("Beneficiario / Proveedor")
    concept = StringField("Concepto", validators=[DataRequired()])
    expense_account_code = SelectField("Cuenta de gasto", choices=[], validators=[DataRequired()])
    amount = StringField("Importe", validators=[DataRequired()])
    cost_center_code = SelectField("Centro de costo", choices=[], validators=[DataRequired()])
    unit_code = SelectField("Unidad de negocio", choices=[], validators=[Optional()])
    project_code = SelectField("Proyecto", choices=[], validators=[Optional()])
    remarks = TextAreaField("Observaciones", validators=[Optional()])


class FormularioPago(FlaskForm):
    """Formulario para crear una entrada de pago."""

    payment_type = SelectField(
        "Tipo de Pago",
        choices=[("receive", "Cobro"), ("pay", "Pago"), ("internal_transfer", "Transferencia Interna")],
    )
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha")
    bank_account_id = SelectField("Cuenta Bancaria", choices=[])
    party_type = SelectField("Tipo de Tercero", choices=[("customer", "Cliente"), ("supplier", "Proveedor")])
    party_id = SelectField("Tercero", choices=[])
    paid_amount = StringField("Monto Pagado")
    remarks = TextAreaField("Observaciones")
    # Contador externo — opcional. Si se selecciona, se asigna el numero externo al pago.
    external_counter_id = SelectField(
        "Contador Externo (Cheque / Numero Fiscal)",
        choices=[],
        validators=[Optional()],
    )
    # Numero externo: si se deja vacio, el sistema usa el siguiente sugerido por el contador.
    external_number = StringField(
        "Numero Externo",
        validators=[Optional()],
    )
