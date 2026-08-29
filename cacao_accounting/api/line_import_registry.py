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
LABEL_BOOK = "Libro"
LABEL_PARTY_TYPE = "Tipo de tercero"
LABEL_PARTY = "Tercero"
LABEL_CURRENCY = "Moneda"
LABEL_EXCHANGE_RATE = "Tipo de cambio"
LABEL_REFERENCE_EXCHANGE_RATE = "Tipo de cambio de referencia"
LABEL_REFERENCE_TYPE = "Tipo de referencia"
LABEL_REFERENCE_DOCUMENT = "Documento de referencia"
LABEL_REFERENCE_LINE = "Línea de referencia"
LABEL_UNIT = "Unidad de negocio"
LABEL_BANK_ACCOUNT = "Cuenta bancaria"
LABEL_IS_ADVANCE = "Es anticipo"
LABEL_PAYMENT_ID = "ID del pago"
LABEL_ALLOCATED_AMOUNT = "Monto aplicado"
LABEL_DISCOUNT_AMOUNT = "Descuento"
LABEL_GAIN_LOSS_AMOUNT = "Diferencia de cambio"

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
ALIASES_BOOK = ["libro", "libro contable", "accounting book", "book"]
ALIASES_PARTY_TYPE = ["tipo de tercero", "party type", "party_type", "tipo tercero"]
ALIASES_PARTY = ["tercero", "party", "party id", "party_id", "cliente", "proveedor"]
ALIASES_CURRENCY = ["moneda", "currency", "currency code", "currency_code"]
ALIASES_EXCHANGE_RATE = ["tipo de cambio", "exchange rate", "exchange_rate", "tasa"]
ALIASES_REFERENCE_EXCHANGE_RATE = [
    "tipo de cambio de referencia",
    "reference exchange rate",
    "reference_exchange_rate",
    "tasa referencia",
]
ALIASES_REFERENCE_TYPE = ["tipo de referencia", "reference type", "reference_type", "tipo referencia"]
ALIASES_REFERENCE_DOCUMENT = [
    "documento de referencia",
    "reference document",
    "reference_document",
    "reference name",
    "reference_name",
]
ALIASES_REFERENCE_LINE = ["línea de referencia", "linea de referencia", "reference line", "reference_line"]
ALIASES_UNIT = ["unidad de negocio", "business unit", "unit"]
ALIASES_BANK_ACCOUNT = ["cuenta bancaria", "bank account", "bank_account", "bank_account_id"]
ALIASES_IS_ADVANCE = ["es anticipo", "is advance", "is_advance", "anticipo"]
ALIASES_PAYMENT_ID = ["id del pago", "payment id", "payment_id", "pago"]
ALIASES_ALLOCATED_AMOUNT = ["monto aplicado", "allocated amount", "allocated_amount", "importe aplicado"]
ALIASES_DISCOUNT_AMOUNT = ["descuento", "discount amount", "discount_amount"]
ALIASES_GAIN_LOSS_AMOUNT = ["diferencia de cambio", "gain loss", "gain_loss_amount", "fx difference"]


class LineImportSchemaRegistry:
    """Registry for document line import schemas."""

    SCHEMAS: Dict[str, Dict[str, Any]] = {
        "payment_reconciliation": {
            "doctype": "payment_reconciliation",
            "label": "Conciliación de pagos",
            "columns": [
                {
                    "key": "payment_id",
                    "label": LABEL_PAYMENT_ID,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_PAYMENT_ID,
                },
                {
                    "key": "reference_type",
                    "label": LABEL_REFERENCE_TYPE,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE_TYPE,
                },
                {
                    "key": "reference_id",
                    "label": LABEL_REFERENCE_DOCUMENT,
                    "required": True,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE_DOCUMENT,
                },
                {
                    "key": "allocated_amount",
                    "label": LABEL_ALLOCATED_AMOUNT,
                    "required": True,
                    "type": "decimal",
                    "aliases": ALIASES_ALLOCATED_AMOUNT,
                },
                {
                    "key": "payment_exchange_rate",
                    "label": LABEL_REFERENCE_EXCHANGE_RATE,
                    "required": False,
                    "type": "decimal",
                    "aliases": ALIASES_REFERENCE_EXCHANGE_RATE,
                },
                {
                    "key": "discount_amount",
                    "label": LABEL_DISCOUNT_AMOUNT,
                    "required": False,
                    "type": "decimal",
                    "aliases": ALIASES_DISCOUNT_AMOUNT,
                },
                {
                    "key": "gain_loss_amount",
                    "label": LABEL_GAIN_LOSS_AMOUNT,
                    "required": False,
                    "type": "decimal",
                    "aliases": ALIASES_GAIN_LOSS_AMOUNT,
                },
                {
                    "key": "notes",
                    "label": LABEL_DESCRIPTION,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_DESCRIPTION,
                },
            ],
        },
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
                {"key": "book", "label": LABEL_BOOK, "required": False, "type": "string", "aliases": ALIASES_BOOK},
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
                    "key": "party_type",
                    "label": LABEL_PARTY_TYPE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_PARTY_TYPE,
                },
                {"key": "party", "label": LABEL_PARTY, "required": False, "type": "string", "aliases": ALIASES_PARTY},
                {
                    "key": "currency",
                    "label": LABEL_CURRENCY,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_CURRENCY,
                },
                {
                    "key": "exchange_rate",
                    "label": LABEL_EXCHANGE_RATE,
                    "required": False,
                    "type": "decimal",
                    "aliases": ALIASES_EXCHANGE_RATE,
                },
                {
                    "key": "reference_exchange_rate",
                    "label": LABEL_REFERENCE_EXCHANGE_RATE,
                    "required": False,
                    "type": "decimal",
                    "aliases": ALIASES_REFERENCE_EXCHANGE_RATE,
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
                    "key": "reference_type",
                    "label": LABEL_REFERENCE_TYPE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE_TYPE,
                },
                {
                    "key": "reference_document",
                    "label": LABEL_REFERENCE_DOCUMENT,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE_DOCUMENT,
                },
                {
                    "key": "reference_line",
                    "label": LABEL_REFERENCE_LINE,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_REFERENCE_LINE,
                },
                {"key": "unit", "label": LABEL_UNIT, "required": False, "type": "string", "aliases": ALIASES_UNIT},
                {
                    "key": "bank_account",
                    "label": LABEL_BANK_ACCOUNT,
                    "required": False,
                    "type": "string",
                    "aliases": ALIASES_BANK_ACCOUNT,
                },
                {
                    "key": "is_advance",
                    "label": LABEL_IS_ADVANCE,
                    "required": False,
                    "type": "boolean",
                    "aliases": ALIASES_IS_ADVANCE,
                },
                {
                    "key": "reference_1",
                    "label": "Referencia 1",
                    "required": False,
                    "type": "string",
                    "aliases": ["referencia 1", "reference 1", "reference_1"],
                },
                {
                    "key": "reference_2",
                    "label": "Referencia 2",
                    "required": False,
                    "type": "string",
                    "aliases": ["referencia 2", "reference 2", "reference_2"],
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
