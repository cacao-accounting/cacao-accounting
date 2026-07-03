# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José MORENO Reyes

"""Logic for importing detail lines from external sources."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from sqlalchemy import or_

from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import Accounts, CostCenter, Entity, Item, Project, UOM, Warehouse, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
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


@dataclass(frozen=True)
class LineValidationPayload:
    """Normalized payload for line import validation."""

    doctype: str | None
    context: dict[str, Any]
    rows: list[dict[str, Any]]


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
def get_schema() -> ResponseReturnValue:
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
def validate_lines() -> ResponseReturnValue:
    """Validate detail lines before importing them into a document."""
    payload = _get_validation_payload()
    schema, schema_error = _load_import_schema(payload.doctype)
    if schema_error:
        return schema_error
    if schema is None:
        return _invalid_payload_response("doctype", _("Doctype no soportado."), 400)

    company_id, company_error = _validate_company_context(payload.context)
    if company_error:
        return company_error
    if company_id is None:
        return _invalid_payload_response("company_id", _("Compañía no especificada en el contexto."), 400)

    permission_error = _validate_import_permission(str(payload.doctype))
    if permission_error:
        return permission_error

    rows_error = _validate_rows_limit(payload.rows)
    if rows_error:
        return rows_error

    errors: list[dict[str, Any]] = []
    validated_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(payload.rows):
        row_errors, validated_row = _validate_import_row(
            row=row,
            row_no=row_index + 1,
            schema=schema,
            doctype=str(payload.doctype),
            company_id=company_id,
        )
        errors.extend(row_errors)
        validated_rows.append(validated_row)

    return _validation_result_response(errors, validated_rows)


def _get_validation_payload() -> LineValidationPayload:
    """Read and normalize the validation payload."""
    payload = request.get_json(silent=True) or {}
    return LineValidationPayload(
        doctype=cast(str | None, payload.get("doctype")),
        context=cast(dict[str, Any], payload.get("context", {})),
        rows=cast(list[dict[str, Any]], payload.get("rows", [])),
    )


def _load_import_schema(doctype: str | None) -> tuple[dict[str, Any] | None, ResponseReturnValue | None]:
    """Load the import schema or return the corresponding HTTP error."""
    if not doctype:
        return None, _error_response(_("Doctype no especificado"), 400)
    schema = LineImportSchemaRegistry.get_schema(doctype)
    if not schema:
        return None, _error_response(_("Doctype no soportado"), 400)
    return schema, None


def _validate_company_context(context: dict[str, Any]) -> tuple[str | None, ResponseReturnValue | None]:
    """Validate that the request context contains an existing company."""
    company_id = context.get("company_id")
    if not company_id:
        return None, _invalid_payload_response("company_id", _("Compañía no especificada en el contexto."), 400)
    company = database.session.query(Entity).filter(or_(Entity.id == company_id, Entity.code == company_id)).first()
    if not company:
        return None, _error_response(_("La compañía seleccionada no existe."), 400)
    return str(company.code), None


def _validate_import_permission(doctype: str) -> ResponseReturnValue | None:
    """Validate the current user's import permission for the document module."""
    module_name = DOCTYPES_MODULES.get(doctype, "general")
    permission = Permisos(modulo=obtener_id_modulo_por_nombre(module_name), usuario=current_user.id)
    if not permission.autorizado or not permission.importar:
        return _error_response(_("No tiene permisos para importar en este módulo."), 403)
    return None


def _validate_rows_limit(rows: list[dict[str, Any]]) -> ResponseReturnValue | None:
    """Validate import row count limits."""
    if not rows:
        return _invalid_payload_response("rows", _("Debe importar al menos una línea."))
    if len(rows) > 500:
        return _invalid_payload_response("rows", _("Límite máximo de 500 líneas excedido."))
    return None


def _validate_import_row(
    *,
    row: dict[str, Any],
    row_no: int,
    schema: dict[str, Any],
    doctype: str,
    company_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate and enrich one imported line."""
    errors: list[dict[str, Any]] = []
    validated_row = row.copy()
    _validate_schema_columns(row, row_no, schema, errors)
    _enrich_and_validate_master_data(row, validated_row, row_no, company_id, errors)
    if doctype == "journal_entry":
        _validate_journal_entry_row(row, row_no, errors)
    return errors, validated_row


def _validate_schema_columns(
    row: dict[str, Any],
    row_no: int,
    schema: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    """Validate required fields and primitive schema types for a row."""
    for column in schema["columns"]:
        key = column["key"]
        value = row.get(key)
        is_empty = value is None or str(value).strip() == ""
        if column["required"] and is_empty:
            errors.append({"row": row_no, "field": key, "message": _("Campo requerido faltante.")})
            continue
        if not is_empty:
            _validate_typed_value(key, value, str(column["type"]), row_no, errors)


def _validate_typed_value(
    key: str,
    value: Any,
    column_type: str,
    row_no: int,
    errors: list[dict[str, Any]],
) -> None:
    """Validate a non-empty value according to its schema type."""
    if column_type == "decimal":
        _validate_decimal_value(key, value, row_no, errors)
    elif column_type == "date" and not _is_date(value):
        errors.append({"row": row_no, "field": key, "message": _("Formato de fecha inválido (AAAA-MM-DD).")})


def _validate_decimal_value(
    key: str,
    value: Any,
    row_no: int,
    errors: list[dict[str, Any]],
) -> None:
    """Validate decimal format and field-specific numeric constraints."""
    if not _is_decimal(value):
        errors.append({"row": row_no, "field": key, "message": _("Valor decimal inválido.")})
        return
    _validate_decimal_constraints(key, Decimal(str(value)), row_no, errors)


def _validate_decimal_constraints(
    key: str,
    decimal_value: Decimal,
    row_no: int,
    errors: list[dict[str, Any]],
) -> None:
    """Validate business constraints for known decimal fields."""
    if key == "quantity" and decimal_value <= 0:
        errors.append({"row": row_no, "field": key, "message": _("La cantidad debe ser mayor que cero.")})
    if key == "rate" and decimal_value < 0:
        errors.append({"row": row_no, "field": key, "message": _("El precio/tasa no puede ser negativo.")})


def _enrich_and_validate_master_data(
    row: dict[str, Any],
    validated_row: dict[str, Any],
    row_no: int,
    company_id: str,
    errors: list[dict[str, Any]],
) -> None:
    """Validate master-data references and enrich the imported row."""
    _validate_item_reference(row, validated_row, row_no, errors)
    _validate_uom_reference(row, row_no, errors)
    _validate_account_reference(row, row_no, company_id, errors)
    _validate_cost_center_reference(row, row_no, company_id, errors)
    _validate_project_reference(row, row_no, company_id, errors)
    _validate_warehouse_reference(row, row_no, company_id, errors)


def _validate_item_reference(
    row: dict[str, Any],
    validated_row: dict[str, Any],
    row_no: int,
    errors: list[dict[str, Any]],
) -> None:
    """Validate and enrich an item reference."""
    if not row.get("item_code"):
        return
    item = database.session.query(Item).filter_by(code=row["item_code"]).first()
    if not item:
        errors.append({"row": row_no, "field": "item_code", "message": _("El artículo no existe.")})
        return
    validated_row["item_name"] = item.name
    validated_row["item_id"] = item.id


def _validate_uom_reference(row: dict[str, Any], row_no: int, errors: list[dict[str, Any]]) -> None:
    """Validate a UOM reference."""
    if row.get("uom") and not database.session.query(UOM).filter_by(code=row["uom"]).first():
        errors.append({"row": row_no, "field": "uom", "message": _("La unidad de medida no existe.")})


def _validate_account_reference(
    row: dict[str, Any],
    row_no: int,
    company_id: str,
    errors: list[dict[str, Any]],
) -> None:
    """Validate an account reference scoped by company."""
    if row.get("account") and not database.session.query(Accounts).filter_by(code=row["account"], entity=company_id).first():
        errors.append({"row": row_no, "field": "account", "message": _("La cuenta contable no existe.")})


def _validate_cost_center_reference(
    row: dict[str, Any],
    row_no: int,
    company_id: str,
    errors: list[dict[str, Any]],
) -> None:
    """Validate a cost center reference scoped by company."""
    cost_center = row.get("cost_center")
    if cost_center and not database.session.query(CostCenter).filter_by(code=cost_center, entity=company_id).first():
        errors.append({"row": row_no, "field": "cost_center", "message": _("El centro de costo no existe.")})


def _validate_project_reference(
    row: dict[str, Any],
    row_no: int,
    company_id: str,
    errors: list[dict[str, Any]],
) -> None:
    """Validate a project reference scoped by company."""
    if row.get("project") and not database.session.query(Project).filter_by(code=row["project"], entity=company_id).first():
        errors.append({"row": row_no, "field": "project", "message": _("El proyecto no existe.")})


def _validate_warehouse_reference(
    row: dict[str, Any],
    row_no: int,
    company_id: str,
    errors: list[dict[str, Any]],
) -> None:
    """Validate a warehouse reference scoped by company."""
    warehouse = row.get("warehouse")
    if warehouse and not database.session.query(Warehouse).filter_by(code=warehouse, company=company_id).first():
        errors.append({"row": row_no, "field": "warehouse", "message": _("La bodega no existe.")})


def _validate_journal_entry_row(row: dict[str, Any], row_no: int, errors: list[dict[str, Any]]) -> None:
    """Validate debit and credit rules for imported journal lines."""
    debit_amount = Decimal(str(row.get("debit") or 0)) if _is_decimal(row.get("debit")) else Decimal(0)
    credit_amount = Decimal(str(row.get("credit") or 0)) if _is_decimal(row.get("credit")) else Decimal(0)
    if debit_amount == credit_amount == 0:
        errors.append({"row": row_no, "field": "debit", "message": _("Debe especificar un monto en Débito o Crédito.")})
    if debit_amount != 0 and credit_amount != 0:
        errors.append(
            {
                "row": row_no,
                "field": "debit",
                "message": _("No puede especificar Débito y Crédito en la misma línea."),
            }
        )


def _error_response(message: str, status_code: int) -> ResponseReturnValue:
    """Build a simple API error response."""
    return jsonify({"error": message}), status_code


def _invalid_payload_response(field: str, message: str, status_code: int = 200) -> ResponseReturnValue:
    """Build a validation response for request-level payload errors."""
    return jsonify({"valid": False, "errors": [{"row": None, "field": field, "message": message}]}), status_code


def _validation_result_response(
    errors: list[dict[str, Any]],
    validated_rows: list[dict[str, Any]],
) -> ResponseReturnValue:
    """Build the final line validation result response."""
    return jsonify({"valid": len(errors) == 0, "rows": validated_rows if len(errors) == 0 else [], "errors": errors})
