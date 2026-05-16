# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de compras."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired

COMPANIA = "Compañía"
FECHA_DE_PUBLICACION = "Fecha de Publicación"


class FormularioProveedor(FlaskForm):
    """Formulario para crear o editar un proveedor."""

    name = StringField("Nombre", validators=[DataRequired()])
    comercial_name = StringField("Nombre Comercial")
    tax_id = StringField("ID Fiscal")
    classification = StringField("Clasificación")
    company = StringField(COMPANIA)
    payable_account_id = StringField("Cuenta por pagar")
    tax_template_id = StringField("Plantilla de impuestos")
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
