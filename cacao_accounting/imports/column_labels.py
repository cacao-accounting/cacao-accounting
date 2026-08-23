"""Localized labels for import template columns."""

from __future__ import annotations

COLUMN_LABELS: dict[str, dict[str, str]] = {
    "document_ref": {"es": "referencia_documento", "en": "document_reference"},
    "fecha": {"es": "fecha", "en": "date"},
    "cuenta": {"es": "cuenta", "en": "account"},
    "centro_costo": {"es": "centro_costo", "en": "cost_center"},
    "tercero": {"es": "tercero", "en": "party"},
    "descripcion": {"es": "descripcion", "en": "description"},
    "debito": {"es": "debito", "en": "debit"},
    "credito": {"es": "credito", "en": "credit"},
    "referencia": {"es": "referencia", "en": "reference"},
    "moneda": {"es": "moneda", "en": "currency"},
    "tipo_cambio": {"es": "tipo_cambio", "en": "exchange_rate"},
    "documento_origen": {"es": "documento_origen", "en": "source_document"},
    "producto": {"es": "producto", "en": "item"},
    "uom": {"es": "unidad_medida", "en": "uom"},
    "cantidad": {"es": "cantidad", "en": "quantity"},
    "precio_unitario": {"es": "precio_unitario", "en": "unit_price"},
    "bodega": {"es": "bodega", "en": "warehouse"},
    "lote": {"es": "lote", "en": "batch"},
    "serie": {"es": "serie", "en": "serial"},
    "notas": {"es": "notas", "en": "notes"},
    "proveedor": {"es": "proveedor", "en": "supplier"},
    "impuesto": {"es": "impuesto", "en": "tax"},
    "nombre": {"es": "nombre", "en": "name"},
    "nombre_comercial": {"es": "nombre_comercial", "en": "trade_name"},
    "identificacion_fiscal": {"es": "identificacion_fiscal", "en": "tax_id"},
    "clasificacion": {"es": "clasificacion", "en": "classification"},
    "grupo": {"es": "grupo", "en": "group"},
    "codigo": {"es": "codigo", "en": "code"},
    "padre": {"es": "padre", "en": "parent"},
    "tipo": {"es": "tipo", "en": "type"},
    "bank_account_id": {"es": "id_cuenta_bancaria", "en": "bank_account_id"},
    "posting_date": {"es": "fecha_contabilizacion", "en": "posting_date"},
    "reference_number": {"es": "numero_referencia", "en": "reference_number"},
    "description": {"es": "descripcion", "en": "description"},
    "deposit": {"es": "deposito", "en": "deposit"},
    "withdrawal": {"es": "retiro", "en": "withdrawal"},
    "forecast_id": {"es": "id_pronostico", "en": "forecast_id"},
    "concept": {"es": "concepto", "en": "concept"},
    "amount": {"es": "importe", "en": "amount"},
    "estimated_date": {"es": "fecha_estimada", "en": "estimated_date"},
}


def localized_columns(columns: list[str], language: str | None) -> list[str]:
    """Return visible template headers in the selected language."""
    lang = "en" if (language or "").lower().startswith("en") else "es"
    return [COLUMN_LABELS.get(column, {}).get(lang, column) for column in columns]


def canonical_columns(columns: list[str], expected: list[str]) -> list[str]:
    """Normalize localized headers using only the adapter's expected fields."""
    aliases = {column: column for column in expected}
    aliases.update({label: column for column in expected for label in COLUMN_LABELS.get(column, {}).values()})
    return [aliases.get(column, column) for column in columns]
