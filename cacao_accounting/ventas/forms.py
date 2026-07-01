# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de ventas."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

_LABEL_COMPANY = "Compañía"
_LABEL_POSTING_DATE = "Fecha de Publicación"


class FormularioCliente(FlaskForm):
    """Formulario para crear o editar un cliente."""

    name = StringField("Nombre", validators=[DataRequired()])
    comercial_name = StringField("Nombre Comercial")
    fiscal_name = StringField("Nombre fiscal")
    tax_id = StringField("ID Fiscal")
    company = StringField(_LABEL_COMPANY)
    party_group_id = StringField("Tipo de Cliente")
    nationality_type = SelectField(
        "Nacionalidad",
        choices=[("", "Seleccione"), ("national", "Nacional"), ("foreign", "Extranjero")],
        validators=[Optional()],
    )
    person_type = SelectField(
        "Tipo de Persona",
        choices=[("", "Seleccione"), ("natural", "Natural"), ("juridical", "Jurídica")],
        validators=[Optional()],
    )
    primary_phone = StringField("Teléfono principal")
    primary_email = StringField("Correo principal")
    website = StringField("Página web")
    primary_address_line1 = StringField("Dirección principal")
    primary_address_line2 = StringField("Dirección principal línea 2")
    primary_address_city = StringField("Ciudad")
    primary_address_state = StringField("Estado / Departamento")
    primary_address_country = StringField("País")
    primary_address_postal_code = StringField("Código postal")
    receivable_account_id = StringField("Cuenta por cobrar")
    tax_template_id = StringField("Plantilla de impuestos")
    default_tax_rule_id = StringField("Regla fiscal predeterminada")
    default_price_list_id = StringField("Lista de precio predeterminada")
    legal_representative_name = StringField("Representante legal")
    legal_representative_id = StringField("Documento del representante")
    legal_representative_position = StringField("Cargo del representante")
    legal_representative_email = StringField("Correo del representante")
    legal_representative_phone = StringField("Teléfono del representante")
    legal_constitution_date = DateField("Fecha de constitución", format="%Y-%m-%d", validators=[Optional()])
    legal_constitution_place = StringField("Lugar de constitución")
    legal_registration_number = StringField("Número de registro")
    legal_notification_address = StringField("Dirección para notificaciones legales")
    legal_notes = TextAreaField("Observaciones legales")
    is_active = BooleanField("Activo", default=True)
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
