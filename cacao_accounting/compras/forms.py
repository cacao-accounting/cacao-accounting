# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de compras."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

COMPANIA = "Compañía"
FECHA_DE_PUBLICACION = "Fecha de Publicación"


class FormularioProveedor(FlaskForm):
    """Formulario para crear o editar un proveedor."""

    name = StringField("Nombre", validators=[DataRequired()])
    comercial_name = StringField("Nombre Comercial")
    fiscal_name = StringField("Nombre fiscal")
    tax_id = StringField("ID Fiscal")
    party_group_id = StringField("Tipo de Proveedor")
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
    company = StringField(COMPANIA)
    payable_account_id = StringField("Cuenta por pagar")
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
    allow_purchase_invoice_without_order = BooleanField("Permitir factura sin orden de compra", default=False)
    allow_purchase_invoice_without_receipt = BooleanField("Permitir factura sin recibo de compra", default=False)


class FormularioOrdenCompra(FlaskForm):
    """Formulario para crear una orden de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField("Observaciones")


class FormularioRecepcionCompra(FlaskForm):
    """Formulario para crear una recepción de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField("Observaciones")


class FormularioFacturaCompra(FlaskForm):
    """Formulario para crear una factura de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    supplier_invoice_no = StringField("Número de Factura del Proveedor")
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    is_return = BooleanField("Es devolución")
    remarks = TextAreaField("Observaciones")


class FormularioSolicitudCompra(FlaskForm):
    """Formulario para crear una solicitud de compra interna."""

    requested_by = StringField("Solicitado por")
    department = StringField("Departamento")
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField("Observaciones")


class FormularioCotizacionProveedor(FlaskForm):
    """Formulario para crear una cotización de proveedor."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField("Observaciones")


class FormularioSolicitudCotizacion(FlaskForm):
    """Formulario para crear una solicitud de cotización de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    remarks = TextAreaField("Observaciones")


class FormularioImportLandedCost(FlaskForm):
    """Formulario para crear un documento de costos de importación."""

    company = SelectField(COMPANIA, choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField(FECHA_DE_PUBLICACION)
    purchase_invoice_id = StringField("Factura de Compra")
    allocation_method = SelectField(
        "Método de Prorrateo",
        choices=[
            ("by_value", "Por Valor"),
            ("by_quantity", "Por Cantidad"),
            ("by_weight", "Por Peso"),
            ("by_volume", "Por Volumen"),
            ("equal", "Equitativo"),
        ],
        default="by_value",
    )
    remarks = TextAreaField("Observaciones")
