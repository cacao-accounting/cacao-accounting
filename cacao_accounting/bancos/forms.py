# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de bancos."""

from cacao_accounting.i18n import _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

_LABEL_COMPANY = _l("Compañía")


class FormularioBanco(FlaskForm):
    """Formulario para crear o editar un banco."""

    name = StringField(_l("Nombre"), validators=[DataRequired()])
    swift_code = StringField(_l("Código SWIFT"))


class FormularioCuentaBancaria(FlaskForm):
    """Formulario para crear o editar una cuenta bancaria."""

    bank_id = SelectField(_l("Banco"), choices=[], validators=[DataRequired()])
    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    account_name = StringField(_l("Nombre de Cuenta"), validators=[DataRequired()])
    account_no = StringField(_l("Número de Cuenta"))
    iban = StringField(_l("IBAN"))
    currency = SelectField(_l("Moneda"), choices=[])
    gl_account_id = SelectField(_l("Cuenta contable bancaria"), choices=[], validators=[Optional()])
    default_naming_series_id = SelectField(_l("Serie interna para pagos"), choices=[], validators=[Optional()])
    default_external_counter_id = SelectField(_l("Chequera"), choices=[], validators=[Optional()])


class FormularioCajaChica(FlaskForm):
    """Formulario para crear o editar una caja chica."""

    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    name = StringField(_l("Nombre"), validators=[DataRequired()])
    account_id = SelectField(_l("Cuenta contable de Caja Chica"), choices=[], validators=[Optional()])
    currency = SelectField(_l("Moneda"), choices=[])
    custodian_id = SelectField(_l("Responsable"), choices=[], validators=[Optional()])
    float_amount = StringField(_l("Fondo autorizado"))
    is_default = BooleanField(_l("Predeterminada"), default=False)
    is_active = BooleanField(_l("Activa"), default=True)
    notes = TextAreaField(_l("Notas"), validators=[Optional()])


class FormularioPettyCashVoucher(FlaskForm):
    """Formulario para crear un vale de caja chica (control de efectivo, no postea al GL)."""

    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    petty_cash_id = SelectField(_l("Caja Chica"), choices=[], validators=[DataRequired()])
    naming_series = SelectField(_l("Serie"), choices=[], validators=[Optional()])
    posting_date = StringField(_l("Fecha"))
    delivered_to = StringField(_l("Entregado a"))
    concept = StringField(_l("Concepto"), validators=[DataRequired()])
    amount = StringField(_l("Importe"), validators=[DataRequired()])
    cost_center_code = SelectField(_l("Centro de costo"), choices=[], validators=[Optional()])
    unit_code = SelectField(_l("Unidad de negocio"), choices=[], validators=[Optional()])
    project_code = SelectField(_l("Proyecto"), choices=[], validators=[Optional()])
    comments = TextAreaField(_l("Comentario"), validators=[Optional()])


class FormularioPettyCashExpense(FlaskForm):
    """Formulario para crear un gasto de caja chica (si genera asiento contable)."""

    company = SelectField(_LABEL_COMPANY, choices=[], validators=[DataRequired()])
    petty_cash_id = SelectField(_l("Caja Chica"), choices=[], validators=[DataRequired()])
    naming_series = SelectField(_l("Serie"), choices=[], validators=[Optional()])
    voucher_id = SelectField(_l("Vale origen"), choices=[], validators=[Optional()])
    posting_date = StringField(_l("Fecha"))
    beneficiary = StringField(_l("Beneficiario / Proveedor"))
    concept = StringField(_l("Concepto"), validators=[DataRequired()])
    expense_account_code = SelectField(_l("Cuenta de gasto"), choices=[], validators=[DataRequired()])
    amount = StringField(_l("Importe"), validators=[DataRequired()])
    cost_center_code = SelectField(_l("Centro de costo"), choices=[], validators=[DataRequired()])
    unit_code = SelectField(_l("Unidad de negocio"), choices=[], validators=[Optional()])
    project_code = SelectField(_l("Proyecto"), choices=[], validators=[Optional()])
    remarks = TextAreaField(_l("Observaciones"), validators=[Optional()])


class FormularioPago(FlaskForm):
    """Formulario para crear una entrada de pago."""

    payment_type = SelectField(
        _l("Tipo de Pago"),
        choices=[
            ("receive", _l("Cobro")),
            ("pay", _l("Pago")),
            ("internal_transfer", _l("Transferencia Interna")),
        ],
    )
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(_l("Fecha"))
    bank_account_id = SelectField(_l("Cuenta Bancaria"), choices=[])
    party_type = SelectField(
        _l("Tipo de Tercero"),
        choices=[("customer", _l("Cliente")), ("supplier", _l("Proveedor"))],
    )
    party_id = SelectField(_l("Tercero"), choices=[])
    paid_amount = StringField(_l("Monto Pagado"))
    remarks = TextAreaField(_l("Observaciones"))
    # Contador externo — opcional. Si se selecciona, se asigna el numero externo al pago.
    external_counter_id = SelectField(
        _l("Contador Externo (Cheque / Numero Fiscal)"),
        choices=[],
        validators=[Optional()],
    )
    # Numero externo: si se deja vacio, el sistema usa el siguiente sugerido por el contador.
    external_number = StringField(
        _l("Numero Externo"),
        validators=[Optional()],
    )
