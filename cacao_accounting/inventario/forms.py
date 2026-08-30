# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de inventario."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

CODIGO = "Código"


class FormularioArticulo(FlaskForm):
    """Formulario para crear o editar un artículo."""

    name = StringField("Nombre", validators=[DataRequired()])
    description = TextAreaField("Descripción")
    item_type = SelectField("Tipo", choices=[("goods", "Bien"), ("service", "Servicio")], validators=[DataRequired()])
    is_stock_item = BooleanField("Es artículo de inventario")
    is_purchase_item = BooleanField("Es artículo de compra", default=True)
    is_sale_item = BooleanField("Es artículo de venta", default=True)
    item_category_id = SelectField("Categoría", choices=[], validators=[Optional()])
    has_expiry_date = BooleanField("Controlar vencimiento")
    allow_negative_stock = BooleanField("Permitir stock negativo")
    currency = SelectField("Moneda", choices=[], validators=[Optional()])
    default_uom = SelectField("UOM Base", choices=[], validators=[DataRequired()])
    barcode = StringField("Código de barras", validators=[Optional()])
    brand = StringField("Marca", validators=[Optional()])
    model_name = StringField("Modelo", validators=[Optional()])
    has_batch = BooleanField("Controlar lote")
    has_serial_no = BooleanField("Controlar número de serie")
    purchase_uom = SelectField("UOM de compra", choices=[], validators=[Optional()])
    sale_uom = SelectField("UOM de venta", choices=[], validators=[Optional()])
    standard_rate = DecimalField("Tarifa estándar", places=4, validators=[Optional()])
    last_purchase_rate = DecimalField("Última tarifa de compra", places=4, validators=[Optional()])
    default_supplier_id = StringField("Proveedor predeterminado", validators=[Optional()])
    default_warehouse_id = StringField("Bodega predeterminada", validators=[Optional()])
    min_stock_qty = DecimalField("Stock mínimo", places=4, validators=[Optional()])
    max_stock_qty = DecimalField("Stock máximo", places=4, validators=[Optional()])
    reorder_level = DecimalField("Punto de reorden", places=4, validators=[Optional()])


class FormularioUOM(FlaskForm):
    """Formulario para crear o editar una unidad de medida."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])


class FormularioBodega(FlaskForm):
    """Formulario para crear o editar una bodega."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField("Nombre", validators=[DataRequired()])


class FormularioLote(FlaskForm):
    """Formulario para crear un lote de inventario."""

    item_code = SelectField("Artículo", choices=[], validators=[DataRequired()])
    batch_no = StringField("Número de lote", validators=[DataRequired()])
    expiry_date = DateField("Fecha de vencimiento", validators=[Optional()])
    manufacturing_date = DateField("Fecha de fabricación", validators=[Optional()])
    description = TextAreaField("Descripción")
    is_active = BooleanField("Activo", default=True)


class FormularioEntradaAlmacen(FlaskForm):
    """Formulario para crear una entrada de almacén."""

    purpose = SelectField(
        "Propósito",
        choices=[
            ("material_receipt", "Recepción de Material"),
            ("material_issue", "Salida de Material"),
            ("material_transfer", "Transferencia"),
            ("stock_adjustment", "Ajuste de Inventario"),
            ("adjustment_positive", "Ajuste Positivo"),
            ("adjustment_negative", "Ajuste Negativo"),
            ("stock_reconciliation", "Conciliación de Inventario"),
        ],
        validators=[DataRequired()],
    )
    company = SelectField("Compañía", choices=[], validators=[DataRequired()])
    naming_series = SelectField("Serie", choices=[], validators=[DataRequired()])
    posting_date = StringField("Fecha", validators=[DataRequired()])
    from_warehouse = SelectField("Bodega Origen", choices=[], validators=[Optional()])
    to_warehouse = SelectField("Bodega Destino", choices=[], validators=[Optional()])
    remarks = TextAreaField("Observaciones")
