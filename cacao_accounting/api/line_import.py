# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José MORENO Reyes

"""Logic for importing detail lines from external sources."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from flask_login import login_required

from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import Accounts, CostCenter, Entity, Item, Project, UOM, Warehouse, database
from cacao_accounting.document_flow.status import _

line_import_bp = Blueprint("line_import", __name__)

DOCTYPES_MODULES = {
    "purchase_request": "purchases",
    "purchase_quotation": "purchases",
    "supplier_quotation": "purchases",
    "purchase_order": "purchases",
    "purchase_receipt": "purchases",
    "purchase_invoice": "purchases",
    "sales_request": "sales",
    "sales_quotation": "sales",
    "sales_order": "sales",
    "delivery_note": "sales",
    "sales_invoice": "sales",
    "journal_entry": "accounting",
    "bank_transaction": "cash",
    "stock_entry": "inventory",
}


def _is_decimal(value: Any) -> bool:
    """Check if a value can be converted to Decimal."""
    if value is None or str(value).strip() == "":
        return False
    try:
        Decimal(str(value))
        return True
    except (InvalidOperation, ValueError):
        return False


def _is_date(value: Any) -> bool:
    """Check if a value can be converted to date."""
    if value is None or str(value).strip() == "":
        return False
    try:
        date.fromisoformat(str(value))
        return True
    except ValueError:
        return False


@line_import_bp.route("/api/line-import/schema")
@login_required
def get_schema():
    """Return the import schema for a given doctype."""
    doctype = request.args.get("doctype")
    if not doctype:
        return jsonify({"error": _("Doctype no especificado")}), 400
    schema = LineImportSchemaRegistry.get_schema(doctype)
    if not schema:
        return jsonify({"error": _("Doctype no soportado")}), 400
    return jsonify(schema)


@line_import_bp.route("/api/line-import/validate", methods=["POST"])
@login_required
def validate_lines():
    """Validate detail lines before importing them into a document."""
    payload = request.get_json(silent=True) or {}
    doctype = payload.get("doctype")
    context = payload.get("context", {})
    rows = payload.get("rows", [])

    if not doctype:
        return jsonify({"error": _("Doctype no especificado")}), 400

    schema = LineImportSchemaRegistry.get_schema(doctype)
    if not schema:
        return jsonify({"error": _("Doctype no soportado")}), 400

    company_id = context.get("company_id")
    if not company_id:
        return (
            jsonify(
                {
                    "valid": False,
                    "errors": [{"row": None, "field": "company_id", "message": _("Compañía no especificada en el contexto.")}],
                }
            ),
            400,
        )

    # Company and permission check
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

    # Check if company exists
    company = database.session.query(Entity).filter_by(id=company_id).first()
    if not company:
        return jsonify({"error": _("La compañía seleccionada no existe.")}), 400

    from flask_login import current_user

    module_name = DOCTYPES_MODULES.get(doctype, "general")
    permiso = Permisos(modulo=obtener_id_modulo_por_nombre(module_name), usuario=current_user.id)
    if not permiso.autorizado or not permiso.importar:
        return jsonify({"error": _("No tiene permisos para importar en este módulo.")}), 403

    if not rows:
        return jsonify(
            {"valid": False, "errors": [{"row": None, "field": "rows", "message": _("Debe importar al menos una línea.")}]}
        )

    if len(rows) > 500:
        return jsonify(
            {"valid": False, "errors": [{"row": None, "field": "rows", "message": _("Límite máximo de 500 líneas excedido.")}]}
        )

    errors: List[Dict[str, Any]] = []
    validated_rows: List[Dict[str, Any]] = []

    for i, row in enumerate(rows):
        row_no = i + 1
        validated_row = row.copy()

        # Basic validation against schema requirements and types
        for col in schema["columns"]:
            key = col["key"]
            val = row.get(key)
            is_empty = val is None or str(val).strip() == ""

            if col["required"] and is_empty:
                errors.append({"row": row_no, "field": key, "message": _("Campo requerido faltante.")})
                continue

            if not is_empty:
                if col["type"] == "decimal":
                    if not _is_decimal(val):
                        errors.append({"row": row_no, "field": key, "message": _("Valor decimal inválido.")})
                    else:
                        d_val = Decimal(str(val))
                        if key == "quantity" and d_val <= 0:
                            errors.append({"row": row_no, "field": key, "message": _("La cantidad debe ser mayor que cero.")})
                        if key == "rate" and d_val < 0:
                            errors.append({"row": row_no, "field": key, "message": _("El precio/tasa no puede ser negativo.")})

                elif col["type"] == "date" and not _is_date(val):
                    errors.append({"row": row_no, "field": key, "message": _("Formato de fecha inválido (AAAA-MM-DD).")})

        # Master data validation
        if row.get("item_code"):
            item = database.session.query(Item).filter_by(code=row["item_code"]).first()
            if not item:
                errors.append({"row": row_no, "field": "item_code", "message": _("El artículo no existe.")})
            else:
                validated_row["item_name"] = item.name
                validated_row["item_id"] = item.id

        if row.get("uom"):
            uom = database.session.query(UOM).filter_by(code=row["uom"]).first()
            if not uom:
                errors.append({"row": row_no, "field": "uom", "message": _("La unidad de medida no existe.")})

        if row.get("account"):
            account = database.session.query(Accounts).filter_by(code=row["account"], entity=company_id).first()
            if not account:
                errors.append({"row": row_no, "field": "account", "message": _("La cuenta contable no existe.")})

        if row.get("cost_center"):
            cc = database.session.query(CostCenter).filter_by(code=row["cost_center"], entity=company_id).first()
            if not cc:
                errors.append({"row": row_no, "field": "cost_center", "message": _("El centro de costo no existe.")})

        if row.get("project"):
            project = database.session.query(Project).filter_by(code=row["project"], entity=company_id).first()
            if not project:
                errors.append({"row": row_no, "field": "project", "message": _("El proyecto no existe.")})

        if row.get("warehouse"):
            wh = database.session.query(Warehouse).filter_by(code=row["warehouse"], company=company_id).first()
            if not wh:
                errors.append({"row": row_no, "field": "warehouse", "message": _("La bodega no existe.")})

        # Journal Entry specific validation
        if doctype == "journal_entry":
            debit = Decimal(str(row.get("debit") or 0)) if _is_decimal(row.get("debit")) else Decimal(0)
            credit = Decimal(str(row.get("credit") or 0)) if _is_decimal(row.get("credit")) else Decimal(0)
            if debit == credit == 0:
                errors.append(
                    {"row": row_no, "field": "debit", "message": _("Debe especificar un monto en Débito o Crédito.")}
                )
            if debit != 0 and credit != 0:
                errors.append(
                    {
                        "row": row_no,
                        "field": "debit",
                        "message": _("No puede especificar Débito y Crédito en la misma línea."),
                    }
                )

        validated_rows.append(validated_row)

    return jsonify({"valid": len(errors) == 0, "rows": validated_rows if len(errors) == 0 else [], "errors": errors})
