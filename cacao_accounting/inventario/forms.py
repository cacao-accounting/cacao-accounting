# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de inventario."""

from cacao_accounting.i18n import _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

CODIGO = _l("Código")


class FormularioArticulo(FlaskForm):
    """Formulario para crear o editar un artículo."""

    name = StringField(_l("Nombre"), validators=[DataRequired()])
    description = TextAreaField(_l("Descripción"))
    item_type = SelectField(
        _l("Tipo"),
        choices=[("goods", _l("Bien")), ("service", _l("Servicio"))],
        validators=[DataRequired()],
    )
    is_stock_item = BooleanField(_l("Es artículo de inventario"))
    is_purchase_item = BooleanField(_l("Es artículo de compra"), default=True)
    is_sale_item = BooleanField(_l("Es artículo de venta"), default=True)
    item_category_id = SelectField(_l("Categoría"), choices=[], validators=[Optional()])
    has_expiry_date = BooleanField(_l("Controlar vencimiento"))
    allow_negative_stock = BooleanField(_l("Permitir stock negativo"))
    currency = SelectField(_l("Moneda"), choices=[], validators=[Optional()])
    default_uom = SelectField(_l("UOM Base"), choices=[], validators=[DataRequired()])
    barcode = StringField(_l("Código de barras"), validators=[Optional()])
    brand = StringField(_l("Marca"), validators=[Optional()])
    model_name = StringField(_l("Modelo"), validators=[Optional()])
    has_batch = BooleanField(_l("Controlar lote"))
    has_serial_no = BooleanField(_l("Controlar número de serie"))
    purchase_uom = SelectField(_l("UOM de compra"), choices=[], validators=[Optional()])
    sale_uom = SelectField(_l("UOM de venta"), choices=[], validators=[Optional()])
    standard_rate = DecimalField(_l("Tarifa estándar"), places=4, validators=[Optional()])
    last_purchase_rate = DecimalField(_l("Última tarifa de compra"), places=4, validators=[Optional()])
    default_supplier_id = StringField(_l("Proveedor predeterminado"), validators=[Optional()])
    default_warehouse_id = StringField(_l("Bodega predeterminada"), validators=[Optional()])
    min_stock_qty = DecimalField(_l("Stock mínimo"), places=4, validators=[Optional()])
    max_stock_qty = DecimalField(_l("Stock máximo"), places=4, validators=[Optional()])
    reorder_level = DecimalField(_l("Punto de reorden"), places=4, validators=[Optional()])


class FormularioUOM(FlaskForm):
    """Formulario para crear o editar una unidad de medida."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField(_l("Nombre"), validators=[DataRequired()])


class FormularioBodega(FlaskForm):
    """Formulario para crear o editar una bodega."""

    code = StringField(CODIGO, validators=[DataRequired()])
    name = StringField(_l("Nombre"), validators=[DataRequired()])


class FormularioLote(FlaskForm):
    """Formulario para crear un lote de inventario."""

    item_code = SelectField(_l("Artículo"), choices=[], validators=[DataRequired()])
    batch_no = StringField(_l("Número de lote"), validators=[DataRequired()])
    expiry_date = DateField(_l("Fecha de vencimiento"), validators=[Optional()])
    manufacturing_date = DateField(_l("Fecha de fabricación"), validators=[Optional()])
    description = TextAreaField(_l("Descripción"))
    is_active = BooleanField(_l("Activo"), default=True)


class FormularioEntradaAlmacen(FlaskForm):
    """Formulario para crear una entrada de almacén."""

    purpose = SelectField(
        _l("Propósito"),
        choices=[
            ("material_receipt", _l("Recepción de Material")),
            ("material_issue", _l("Salida de Material")),
            ("material_transfer", _l("Transferencia")),
            ("stock_adjustment", _l("Ajuste de Inventario")),
            ("adjustment_positive", _l("Ajuste Positivo")),
            ("adjustment_negative", _l("Ajuste Negativo")),
            ("stock_reconciliation", _l("Conciliación de Inventario")),
        ],
        validators=[DataRequired()],
    )
    company = SelectField(_l("Compañía"), choices=[], validators=[DataRequired()])
    naming_series = SelectField(_l("Serie"), choices=[], validators=[DataRequired()])
    posting_date = StringField(_l("Fecha"), validators=[DataRequired()])
    from_warehouse = SelectField(_l("Bodega Origen"), choices=[], validators=[Optional()])
    to_warehouse = SelectField(_l("Bodega Destino"), choices=[], validators=[Optional()])
    remarks = TextAreaField(_l("Observaciones"))
