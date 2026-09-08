# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de compras."""

from cacao_accounting.i18n import _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

COMPANIA = _l("Compañía")
FECHA_DE_PUBLICACION = _l("Fecha de Publicación")


class FormularioProveedor(FlaskForm):
    """Formulario para crear o editar un proveedor."""

    name = StringField(_l("Nombre"), validators=[DataRequired()])
    comercial_name = StringField(_l("Nombre Comercial"))
    fiscal_name = StringField(_l("Nombre fiscal"))
    tax_id = StringField(_l("ID Fiscal"))
    party_group_id = StringField(_l("Tipo de Proveedor"))
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
    company = StringField(COMPANIA)
    payable_account_id = StringField(_l("Cuenta por pagar"))
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
    allow_purchase_invoice_without_order = BooleanField(_l("Permitir factura sin orden de compra"), default=False)
    allow_purchase_invoice_without_receipt = BooleanField(_l("Permitir factura sin recibo de compra"), default=False)


class FormularioOrdenCompra(FlaskForm):
    """Formulario para crear una orden de compra."""

    supplier_id = SelectField(_l("Proveedor"), choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioRecepcionCompra(FlaskForm):
    """Formulario para crear una recepción de compra."""

    supplier_id = SelectField(_l("Proveedor"), choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioFacturaCompra(FlaskForm):
    """Formulario para crear una factura de compra."""

    supplier_id = SelectField(_l("Proveedor"), choices=[])
    supplier_invoice_no = StringField(_l("Número de Factura del Proveedor"))
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    is_return = BooleanField(_l("Es devolución"))
    remarks = TextAreaField(_l("Observaciones"))


class FormularioSolicitudCompra(FlaskForm):
    """Formulario para crear una solicitud de compra interna."""

    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioCotizacionProveedor(FlaskForm):
    """Formulario para crear una cotización de proveedor."""

    supplier_id = SelectField(_l("Proveedor"), choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioSolicitudCotizacion(FlaskForm):
    """Formulario para crear una solicitud de cotización de compra."""

    supplier_id = SelectField(_l("Proveedor"), choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField(_l("Observaciones"))


class FormularioImportLandedCost(FlaskForm):
    """Formulario para crear un documento de costos de importación."""

    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField(_l("Serie"), choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    purchase_invoice_id = StringField(_l("Factura de Compra"))
    allocation_method = SelectField(
        _l("Método de Prorrateo"),
        choices=[
            ("by_value", _l("Por Valor")),
            ("by_quantity", _l("Por Cantidad")),
            ("by_weight", _l("Por Peso")),
            ("by_volume", _l("Por Volumen")),
            ("equal", _l("Equitativo")),
        ],
        default="by_value",
    )
    remarks = TextAreaField(_l("Observaciones"))
