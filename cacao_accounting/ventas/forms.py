# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de ventas."""

from cacao_accounting.i18n import _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

_LABEL_COMPANY = _l("Compañía")
_LABEL_POSTING_DATE = _l("Fecha de Publicación")


class FormularioCliente(FlaskForm):
    """Formulario para crear o editar un cliente."""

    name = StringField(_l("Nombre"), validators=[DataRequired()])
    comercial_name = StringField(_l("Nombre Comercial"))
    fiscal_name = StringField(_l("Nombre fiscal"))
    tax_id = StringField(_l("ID Fiscal"))
    company = StringField(_LABEL_COMPANY)
    party_group_id = StringField(_l("Tipo de Cliente"))
    nationality_type = SelectField(
        _l("Nacionalidad"),
        choices=[
            ("", _l("Seleccione")),
            ("national", _l("Nacional")),
            ("foreign", _l("Extranjero")),
        ],
        validators=[Optional()],
    )
    person_type = SelectField(
        _l("Tipo de Persona"),
        choices=[
            ("", _l("Seleccione")),
            ("natural", _l("Natural")),
            ("juridical", _l("Jurídica")),
        ],
        validators=[Optional()],
    )
    primary_phone = StringField(_l("Teléfono principal"))
    primary_email = StringField(_l("Correo principal"))
    website = StringField(_l("Página web"))
    primary_address_line1 = StringField(_l("Dirección principal"))
    primary_address_line2 = StringField(_l("Dirección principal línea 2"))
    primary_address_city = StringField(_l("Ciudad"))
    primary_address_state = StringField(_l("Estado / Provincia"))
    primary_address_country = StringField(_l("País"))
    primary_address_postal_code = StringField(_l("Código postal"))
    receivable_account_id = StringField(_l("Cuenta por cobrar"))
    tax_template_id = StringField(_l("Plantilla de impuestos"))
    default_tax_rule_id = StringField(_l("Regla fiscal predeterminada"))
    default_price_list_id = StringField(_l("Lista de precio predeterminada"))
    legal_representative_name = StringField(_l("Representante legal"))
    legal_representative_id = StringField(_l("Documento del representante"))
    legal_representative_position = StringField(_l("Cargo del representante"))
    legal_representative_email = StringField(_l("Correo del representante"))
    legal_representative_phone = StringField(_l("Teléfono del representante"))
    legal_constitution_date = DateField(_l("Fecha de constitución"), format="%Y-%m-%d", validators=[Optional()])
    legal_constitution_place = StringField(_l("Lugar de constitución"))
    legal_registration_number = StringField(_l("Número de registro"))
    legal_notification_address = StringField(_l("Dirección para notificaciones legales"))
    legal_notes = TextAreaField(_l("Observaciones legales"))
    is_active = BooleanField(_l("Activo"), default=True)
    company_is_active = BooleanField(_l("Activo en la compañía"), default=True)


class FormularioOrdenVenta(FlaskForm):
    """Formulario para crear una orden de venta."""

    customer_id = SelectField(_l("Cliente"), choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioPedidoVenta(FlaskForm):
    """Formulario para crear un pedido de venta."""

    customer_id = SelectField(_l("Cliente"), choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioEntregaVenta(FlaskForm):
    """Formulario para crear una nota de entrega."""

    customer_id = SelectField(_l("Cliente"), choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    is_return = BooleanField(_l("Es devolución"))
    remarks = TextAreaField(_l("Observaciones"))


class FormularioFacturaVenta(FlaskForm):
    """Formulario para crear una factura de venta."""

    customer_id = SelectField(_l("Cliente"), choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    is_return = BooleanField(_l("Es devolución"))
    update_inventory = BooleanField(_l("Actualizar inventario"))
    remarks = TextAreaField(_l("Observaciones"))


class FormularioCotizacionVenta(FlaskForm):
    """Formulario para crear una cotización de venta."""

    customer_id = SelectField(_l("Cliente"), choices=[])
    company = SelectField(_LABEL_COMPANY, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(_LABEL_POSTING_DATE)
    valid_until = DateField(_l("Válida hasta"), format="%Y-%m-%d", validators=[Optional()])
    remarks = TextAreaField(_l("Observaciones"))
