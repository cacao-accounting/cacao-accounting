# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de ventas."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired


_LABEL_COMPANY = "Compañía"
_LABEL_POSTING_DATE = "Fecha de Publicación"


class FormularioCliente(FlaskForm):
    """Formulario para crear o editar un cliente."""

    name = StringField("Nombre", validators=[DataRequired()])
    comercial_name = StringField("Nombre Comercial")
    tax_id = StringField("ID Fiscal")
    classification = StringField("Clasificación")
    company = StringField(_LABEL_COMPANY)
    party_group_id = StringField("Tipo de Cliente")
    receivable_account_id = StringField("Cuenta por cobrar")
    tax_template_id = StringField("Plantilla de impuestos")
    company_is_active = BooleanField("Activo en la compañía", default=True)


class FormularioOrdenVenta(FlaskForm):
    """Formulario para crear una orden de venta."""

    customer_id = SelectField("Cliente", choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    remarks = TextAreaField("Observaciones")


class FormularioPedidoVenta(FlaskForm):
    """Formulario para crear un pedido de venta."""

    customer_id = SelectField("Cliente", choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    remarks = TextAreaField("Observaciones")


class FormularioEntregaVenta(FlaskForm):
    """Formulario para crear una nota de entrega."""

    customer_id = SelectField("Cliente", choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    remarks = TextAreaField("Observaciones")


class FormularioFacturaVenta(FlaskForm):
    """Formulario para crear una factura de venta."""

    customer_id = SelectField("Cliente", choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    is_return = BooleanField("Es devolución")
    remarks = TextAreaField("Observaciones")


class FormularioCotizacionVenta(FlaskForm):
    """Formulario para crear una cotización de venta."""

    customer_id = SelectField("Cliente", choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    remarks = TextAreaField("Observaciones")
