# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de compras."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired


class FormularioProveedor(FlaskForm):
    """Formulario para crear o editar un proveedor."""

    name = StringField("Nombre", validators=[DataRequired()])
    comercial_name = StringField("Nombre Comercial")
    tax_id = StringField("ID Fiscal")
    classification = StringField("Clasificación")


class FormularioOrdenCompra(FlaskForm):
    """Formulario para crear una orden de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha de Publicación")
    remarks = TextAreaField("Observaciones")


class FormularioRecepcionCompra(FlaskForm):
    """Formulario para crear una recepción de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha de Publicación")
    remarks = TextAreaField("Observaciones")


class FormularioFacturaCompra(FlaskForm):
    """Formulario para crear una factura de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    supplier_invoice_no = StringField("Número de Factura del Proveedor")
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha de Publicación")
    is_return = BooleanField("Es devolución")
    remarks = TextAreaField("Observaciones")


class FormularioSolicitudCompra(FlaskForm):
    """Formulario para crear una solicitud de compra interna."""

    requested_by = StringField("Solicitado por")
    department = StringField("Departamento")
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha de Publicación")
    remarks = TextAreaField("Observaciones")


class FormularioCotizacionProveedor(FlaskForm):
    """Formulario para crear una cotización de proveedor."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha de Publicación")
    remarks = TextAreaField("Observaciones")


class FormularioSolicitudCotizacion(FlaskForm):
    """Formulario para crear una solicitud de cotización de compra."""

    supplier_id = SelectField("Proveedor", choices=[])
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha de Publicación")
    remarks = TextAreaField("Observaciones")
