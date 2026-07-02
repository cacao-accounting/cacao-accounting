# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José MORENO Reyes

"""Registry for line import schemas."""

from typing import Any, Dict

LABEL_ITEM = "Artículo"
LABEL_DESCRIPTION = "Descripción"
LABEL_REQUIRED_DATE = "Fecha requerida"
LABEL_COST_CENTER = "Centro de costo"
LABEL_DELIVERY_DATE = "Fecha de entrega"
ALIASES_ITEM_CODE = ["producto", "item", "codigo", "código"]
ALIASES_DESCRIPTION = ["nombre"]
ALIASES_REQUIRED_DATE = ["fecha"]


class LineImportSchemaRegistry:
    """Registry for document line import schemas."""

    SCHEMAS: Dict[str, Dict[str, Any]] = {
        "purchase_request": {
            "doctype": "purchase_request",
            "label": "Solicitud de compra",
            "columns": [
                {
                    "key": "item_code",
                    "label": LABEL_ITEM,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_ITEM_CODE,
                },
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal", "aliases": ["cant", "qty"]},
                {
                    "key": "uom",
                    "label": "Unidad",
                    "required": True,
                    "type": "string",
                    "aliases": ["uom", "unidad de medida"],
                },
                {
                    "key": "required_date",
                    "label": LABEL_REQUIRED_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_REQUIRED_DATE,
                },
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
            ],
        },
        "purchase_order": {
            "doctype": "purchase_order",
            "label": "Orden de compra",
            "columns": [
                {
                    "key": "item_code",
                    "label": LABEL_ITEM,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_ITEM_CODE,
                },
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {
                    "key": "rate",
                    "label": "Precio",
                    "required": True,
                    "type": "decimal",
                    "aliases": ["costo", "precio unitario"],
                },
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
                {"key": "required_date", "label": LABEL_REQUIRED_DATE, "required": False, "type": "date"},
            ],
        },
        "purchase_quotation": {
            "doctype": "purchase_quotation",
            "label": "Solicitud de cotización",
            "columns": [
                {
                    "key": "item_code",
                    "label": LABEL_ITEM,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_ITEM_CODE,
                },
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio estimado", "required": False, "type": "decimal"},
                {"key": "required_date", "label": LABEL_REQUIRED_DATE, "required": False, "type": "date"},
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
            ],
        },
        "supplier_quotation": {
            "doctype": "supplier_quotation",
            "label": "Cotización de proveedor",
            "columns": [
                {
                    "key": "item_code",
                    "label": LABEL_ITEM,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_ITEM_CODE,
                },
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": True, "type": "decimal"},
                {"key": "required_date", "label": LABEL_REQUIRED_DATE, "required": False, "type": "date"},
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
            ],
        },
        "purchase_receipt": {
            "doctype": "purchase_receipt",
            "label": "Recibo de compra",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": False, "type": "decimal"},
                {"key": "warehouse", "label": "Bodega", "required": False, "type": "string"},
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
            ],
        },
        "sales_request": {
            "doctype": "sales_request",
            "label": "Pedido de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": False, "type": "decimal"},
                {"key": "delivery_date", "label": LABEL_DELIVERY_DATE, "required": False, "type": "date"},
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
            ],
        },
        "sales_quotation": {
            "doctype": "sales_quotation",
            "label": "Cotización de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": True, "type": "decimal"},
                {"key": "discount", "label": "Descuento", "required": False, "type": "decimal"},
            ],
        },
        "sales_order": {
            "doctype": "sales_order",
            "label": "Orden de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": True, "type": "decimal"},
                {"key": "warehouse", "label": "Bodega", "required": False, "type": "string"},
                {"key": "delivery_date", "label": LABEL_DELIVERY_DATE, "required": False, "type": "date"},
            ],
        },
        "delivery_note": {
            "doctype": "delivery_note",
            "label": "Nota de entrega",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": False, "type": "decimal"},
                {"key": "warehouse", "label": "Bodega", "required": False, "type": "string"},
                {"key": "delivery_date", "label": LABEL_DELIVERY_DATE, "required": False, "type": "date"},
            ],
        },
        "journal_entry": {
            "doctype": "journal_entry",
            "label": "Comprobante contable",
            "columns": [
                {
                    "key": "account",
                    "label": "Cuenta",
                    "required": True,
                    "type": "string",
                    "aliases": ["cuenta contable", "codigo cuenta"],
                },
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "debit", "label": "Débito", "required": False, "type": "decimal", "aliases": ["debe"]},
                {"key": "credit", "label": "Crédito", "required": False, "type": "decimal", "aliases": ["haber"]},
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
                {"key": "project", "label": "Proyecto", "required": False, "type": "string"},
                {"key": "reference", "label": "Referencia", "required": False, "type": "string"},
            ],
        },
        "purchase_invoice": {
            "doctype": "purchase_invoice",
            "label": "Factura de compra",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": True, "type": "decimal"},
                {"key": "cost_center", "label": LABEL_COST_CENTER, "required": False, "type": "string"},
            ],
        },
        "sales_invoice": {
            "doctype": "sales_invoice",
            "label": "Factura de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "rate", "label": "Precio", "required": True, "type": "decimal"},
            ],
        },
        "bank_transaction": {
            "doctype": "bank_transaction",
            "label": "Transacción bancaria",
            "columns": [
                {"key": "date", "label": "Fecha", "required": True, "type": "date"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": True, "type": "string"},
                {"key": "debit", "label": "Débito", "required": False, "type": "decimal"},
                {"key": "credit", "label": "Crédito", "required": False, "type": "decimal"},
                {"key": "reference", "label": "Referencia", "required": False, "type": "string"},
            ],
        },
        "stock_entry": {
            "doctype": "stock_entry",
            "label": "Movimiento de inventario",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string"},
                {"key": "description", "label": LABEL_DESCRIPTION, "required": False, "type": "string"},
                {"key": "quantity", "label": "Cantidad", "required": True, "type": "decimal"},
                {"key": "uom", "label": "Unidad", "required": True, "type": "string"},
                {"key": "source_warehouse", "label": "Bodega origen", "required": False, "type": "string"},
                {"key": "target_warehouse", "label": "Bodega destino", "required": False, "type": "string"},
            ],
        },
    }

    @classmethod
    def get_schema(cls, doctype: str) -> Dict[str, Any] | None:
        """Return the schema for a doctype."""
        return cls.SCHEMAS.get(doctype)
