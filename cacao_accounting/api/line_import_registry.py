# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José MORENO Reyes

"""Registry for line import schemas."""

from typing import Any, Dict

LABEL_ITEM = "Artículo"
LABEL_DESCRIPTION = "Descripción"
LABEL_REQUIRED_DATE = "Fecha requerida"
LABEL_COST_CENTER = "Centro de costo"
LABEL_DELIVERY_DATE = "Fecha de entrega"
LABEL_QUANTITY = "Cantidad"
LABEL_UOM = "Unidad"
LABEL_RATE = "Precio"
LABEL_WAREHOUSE = "Bodega"
LABEL_PROJECT = "Proyecto"
LABEL_REFERENCE = "Referencia"
LABEL_DEBIT = "Débito"
LABEL_CREDIT = "Crédito"
LABEL_ACCOUNT = "Cuenta"
LABEL_DATE = "Fecha"
LABEL_DISCOUNT = "Descuento"
LABEL_SOURCE_WAREHOUSE = "Bodega origen"
LABEL_TARGET_WAREHOUSE = "Bodega destino"

ALIASES_ITEM_CODE = ["producto", "item", "codigo", "código", "article", "product", "item code", "item_code", "code"]
ALIASES_DESCRIPTION = ["nombre", "description", "item name", "item_name", "name"]
ALIASES_REQUIRED_DATE = ["fecha", "required date", "required_date"]
ALIASES_QUANTITY = ["cantidad", "cant", "qty", "quantity"]
ALIASES_UOM = ["uom", "unidad de medida", "unit", "unit of measure"]
ALIASES_RATE = ["costo", "precio unitario", "rate", "price", "unit price", "unit cost"]
ALIASES_WAREHOUSE = ["warehouse", "bodega", "almacen", "almacén"]
ALIASES_COST_CENTER = ["cost center", "cost_center"]
ALIASES_PROJECT = ["project"]
ALIASES_REFERENCE = ["reference", "ref"]
ALIASES_DEBIT = ["debe", "debit"]
ALIASES_CREDIT = ["haber", "credit"]
ALIASES_ACCOUNT = ["cuenta contable", "codigo cuenta", "código cuenta", "account", "account code", "account_code"]
ALIASES_DATE = ["date", "posting date", "posting_date"]
ALIASES_DISCOUNT = ["discount"]
ALIASES_DELIVERY_DATE = ["delivery date", "delivery_date"]
ALIASES_SOURCE_WAREHOUSE = ["source warehouse", "source_warehouse", "from warehouse", "bodega salida"]
ALIASES_TARGET_WAREHOUSE = ["target warehouse", "target_warehouse", "to warehouse", "bodega entrada"]


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
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {
                    "key": "uom",
                    "label": LABEL_UOM,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_UOM,
                },
                {
                    "key": "required_date",
                    "label": LABEL_REQUIRED_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_REQUIRED_DATE,
                },
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
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
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {
                    "key": "rate",
                    "label": LABEL_RATE,
                    "required": True,
                    "type": "decimal",
                    "aliases": ALIASES_RATE,
                },
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
                {
                    "key": "required_date",
                    "label": LABEL_REQUIRED_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_REQUIRED_DATE,
                },
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
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": "Precio estimado", "required": False, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "required_date",
                    "label": LABEL_REQUIRED_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_REQUIRED_DATE,
                },
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
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
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": True, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "required_date",
                    "label": LABEL_REQUIRED_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_REQUIRED_DATE,
                },
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
            ],
        },
        "purchase_receipt": {
            "doctype": "purchase_receipt",
            "label": "Recibo de compra",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": False, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "warehouse",
                    "label": LABEL_WAREHOUSE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_WAREHOUSE,
                },
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
            ],
        },
        "sales_request": {
            "doctype": "sales_request",
            "label": "Pedido de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": False, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "delivery_date",
                    "label": LABEL_DELIVERY_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_DELIVERY_DATE,
                },
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
            ],
        },
        "sales_quotation": {
            "doctype": "sales_quotation",
            "label": "Cotización de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": True, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "discount",
                    "label": LABEL_DISCOUNT,
                    "required": False,
                    "type": "decimal",
                    "aliases": ALIASES_DISCOUNT,
                },
            ],
        },
        "sales_order": {
            "doctype": "sales_order",
            "label": "Orden de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": True, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "warehouse",
                    "label": LABEL_WAREHOUSE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_WAREHOUSE,
                },
                {
                    "key": "delivery_date",
                    "label": LABEL_DELIVERY_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_DELIVERY_DATE,
                },
            ],
        },
        "delivery_note": {
            "doctype": "delivery_note",
            "label": "Nota de entrega",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": False, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "warehouse",
                    "label": LABEL_WAREHOUSE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_WAREHOUSE,
                },
                {
                    "key": "delivery_date",
                    "label": LABEL_DELIVERY_DATE,
                    "required": False,
                    "type": "date",
                    "aliases": ALIASES_DELIVERY_DATE,
                },
            ],
        },
        "journal_entry": {
            "doctype": "journal_entry",
            "label": "Comprobante contable",
            "columns": [
                {
                    "key": "account",
                    "label": LABEL_ACCOUNT,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_ACCOUNT,
                },
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "debit", "label": LABEL_DEBIT, "required": False, "type": "decimal", "aliases": ALIASES_DEBIT},
                {"key": "credit", "label": LABEL_CREDIT, "required": False, "type": "decimal", "aliases": ALIASES_CREDIT},
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
                {"key": "project", "label": LABEL_PROJECT, "required": False, "type": "string", "aliases": ALIASES_PROJECT},
                {
                    "key": "reference",
                    "label": LABEL_REFERENCE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE,
                },
            ],
        },
        "purchase_invoice": {
            "doctype": "purchase_invoice",
            "label": "Factura de compra",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": True, "type": "decimal", "aliases": ALIASES_RATE},
                {
                    "key": "cost_center",
                    "label": LABEL_COST_CENTER,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_COST_CENTER,
                },
            ],
        },
        "sales_invoice": {
            "doctype": "sales_invoice",
            "label": "Factura de venta",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {"key": "rate", "label": LABEL_RATE, "required": True, "type": "decimal", "aliases": ALIASES_RATE},
            ],
        },
        "bank_transaction": {
            "doctype": "bank_transaction",
            "label": "Transacción bancaria",
            "columns": [
                {"key": "date", "label": LABEL_DATE, "required": True, "type": "date", "aliases": ALIASES_DATE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "debit", "label": LABEL_DEBIT, "required": False, "type": "decimal", "aliases": ALIASES_DEBIT},
                {"key": "credit", "label": LABEL_CREDIT, "required": False, "type": "decimal", "aliases": ALIASES_CREDIT},
                {
                    "key": "reference",
                    "label": LABEL_REFERENCE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE,
                },
            ],
        },
        "stock_entry": {
            "doctype": "stock_entry",
            "label": "Movimiento de inventario",
            "columns": [
                {"key": "item_code", "label": LABEL_ITEM, "required": True, "type": "string", "aliases": ALIASES_ITEM_CODE},
                {
                    "key": "description",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
                {"key": "quantity", "label": LABEL_QUANTITY, "required": True, "type": "decimal", "aliases": ALIASES_QUANTITY},
                {"key": "uom", "label": LABEL_UOM, "required": True, "type": "string", "aliases": ALIASES_UOM},
                {
                    "key": "source_warehouse",
                    "label": LABEL_SOURCE_WAREHOUSE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_SOURCE_WAREHOUSE,
                },
                {
                    "key": "target_warehouse",
                    "label": LABEL_TARGET_WAREHOUSE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_TARGET_WAREHOUSE,
                },
            ],
        },
    }

    @classmethod
    def get_schema(cls, doctype: str) -> Dict[str, Any] | None:
        """Return the schema for a doctype."""
        return cls.SCHEMAS.get(doctype)
