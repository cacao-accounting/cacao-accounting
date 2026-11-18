# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""ACL por módulo para las herramientas de consulta documental.

Replica el criterio del árbol documental (#1407): el ámbito
`documents.reports.read` no sustituye el permiso del módulo dueño ni el
acceso a la compañía del documento (#2252, #2253).
"""

from __future__ import annotations

from typing import Any

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import Modules
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.database import database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, normalize_doctype
from cacao_accounting.document_flow.repository import document_matches_type, get_document, get_document_company
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.permissions import validate_company_access, validate_module_active
from cacao_accounting.i18n import _

_ALTERNATE_MODULES: dict[str, tuple[str, ...]] = {
    "delivery_note": ("sales", "inventory"),
    "purchase_order": ("purchases", "inventory"),
    "purchase_receipt": ("purchases", "inventory"),
}


def read_modules_for(document_type: str) -> tuple[str, ...]:
    """Devuelve los módulos que pueden leer el tipo documental."""
    doctype = normalize_doctype(document_type)
    alternate = _ALTERNATE_MODULES.get(doctype)
    if alternate is not None:
        return alternate
    spec = DOCUMENT_TYPES.get(doctype)
    if spec is None:
        return ()
    module = spec.permission_module or spec.module
    if not module or module == "general":
        return ()
    return (module,)


def _module_enabled(module: str) -> bool:
    """Indica si el módulo existe y está habilitado."""
    module_id = obtener_id_modulo_por_nombre(module)
    if not module_id:
        return False
    record = database.session.get(Modules, module_id)
    return bool(record and record.enabled)


def _module_allowed(context: QueryContext, module: str, company_id: str) -> bool:
    """Evalúa el permiso de consulta del módulo para el actor y la compañía."""
    if not _module_enabled(module):
        return False
    if context.is_service_principal:
        return f"{module}.reports.read" in context.permissions
    module_id = obtener_id_modulo_por_nombre(module)
    if not module_id:
        return False
    permissions = Permisos(modulo=module_id, usuario=context.user_id)
    return bool(permissions.consultar and permissions.tiene_acceso_compania(company_id))


def require_document_read(context: QueryContext, document_type: str, company_id: str) -> tuple[str, ...]:
    """Exige al menos un módulo dueño legible para el tipo y la compañía."""
    doctype = normalize_doctype(document_type)
    modules = read_modules_for(doctype)
    if not modules:
        raise QueryToolError(
            code=ErrorCode.PERMISSION_DENIED,
            message=_("No tiene permisos para consultar este recurso."),
            request_id=context.request_id,
        )
    validate_company_access(context, company_id)
    if context.is_service_principal:
        for module in modules:
            validate_module_active(module)
    if not any(_module_allowed(context, module, company_id) for module in modules):
        raise QueryToolError(
            code=ErrorCode.PERMISSION_DENIED,
            message=_("No tiene permisos para consultar este recurso."),
            request_id=context.request_id,
        )
    return modules


def require_document_id_read(context: QueryContext, document_type: str, document_id: str, company_id: str) -> Any:
    """Valida módulo, compañía y subtipo del documento concreto."""
    doctype = normalize_doctype(document_type)
    document = get_document(doctype, document_id)
    if document is None or not document_matches_type(doctype, document):
        raise QueryToolError(
            code=ErrorCode.PERMISSION_DENIED,
            message=_("No tiene permisos para consultar este recurso."),
            request_id=context.request_id,
        )
    document_company = get_document_company(doctype, document_id)
    if str(document_company or "") != str(company_id):
        raise QueryToolError(
            code=ErrorCode.COMPANY_ACCESS_DENIED,
            message=_("No tiene acceso a la compañía solicitada."),
            request_id=context.request_id,
        )
    require_document_read(context, doctype, company_id)
    return document


def allowed_doctypes(context: QueryContext, company_id: str) -> set[str]:
    """Devuelve los tipos documentales legibles por el actor en la compañía."""
    allowed: set[str] = set()
    for doctype in DOCUMENT_TYPES:
        modules = read_modules_for(doctype)
        if modules and any(_module_allowed(context, module, company_id) for module in modules):
            allowed.add(doctype)
    return allowed
