# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de inventario."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired

CODIGO = "Código"


class FormularioArticulo(FlaskForm):
    """Formulario para crear o editar un artículo."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])
    description = TextAreaField("Descripción")
    item_type = SelectField("Tipo", choices=[("goods", "Bien"), ("service", "Servicio")])
    is_stock_item = BooleanField("Es artículo de inventario")
    default_uom = SelectField("UOM Base", choices=[])


class FormularioUOM(FlaskForm):
    """Formulario para crear o editar una unidad de medida."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])


class FormularioBodega(FlaskForm):
    """Formulario para crear o editar una bodega."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])
    company = SelectField("Compañía", choices=[])


class FormularioEntradaAlmacen(FlaskForm):
    """Formulario para crear una entrada de almacén."""

    purpose = SelectField(
        "Propósito",
        choices=[
            ("material_receipt", "Recepción de Material"),
            ("material_issue", "Salida de Material"),
            ("material_transfer", "Transferencia"),
            ("adjustment_positive", "Ajuste Positivo"),
            ("adjustment_negative", "Ajuste Negativo"),
            ("stock_reconciliation", "Conciliación de Inventario"),
        ],
    )
    company = SelectField("Compañía", choices=[])
    naming_series = SelectField("Serie", choices=[])
    posting_date = StringField("Fecha")
    from_warehouse = SelectField("Bodega Origen", choices=[])
    to_warehouse = SelectField("Bodega Destino", choices=[])
    remarks = TextAreaField("Observaciones")
