"""Validación de permisos, acceso a compañías y módulos para herramientas de consulta."""

from __future__ import annotations

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import database, Entity, Modules
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError


def validate_company_access(
    context: QueryContext, company_id: str
) -> None:
    """Verifica que el contexto tenga acceso a la compañía indicada y que esta exista."""
    if context.company_ids and company_id not in context.company_ids:
        raise QueryToolError(
            code=ErrorCode.COMPANY_ACCESS_DENIED,
            message="No tiene acceso a la compañía solicitada.",
            request_id=context.request_id,
        )

    entity = database.session.execute(
        database.select(Entity).where(Entity.code == company_id)
    ).scalars().first()

    if not entity:
        raise QueryToolError(
            code=ErrorCode.COMPANY_ACCESS_DENIED,
            message="La compañía solicitada no existe.",
            request_id=context.request_id,
        )


def validate_module_active(module_name: str) -> None:
    """Verifica que el módulo indicado exista y se encuentre habilitado."""
    module_id = obtener_id_modulo_por_nombre(module_name)
    if not module_id:
        raise QueryToolError(
            code=ErrorCode.MODULE_DISABLED,
            message=f"El módulo '{module_name}' no está disponible.",
        )
    module = database.session.get(Modules, module_id)
    if not module or not module.enabled:
        raise QueryToolError(
            code=ErrorCode.MODULE_DISABLED,
            message=f"El módulo '{module_name}' se encuentra deshabilitado.",
        )


def validate_permission(
    context: QueryContext,
    required_permission: str | None,
    required_module: str | None = None,
    company_id: str | None = None,
) -> None:
    """Valida permisos, módulo activo y acceso a compañía de forma combinada."""
    if required_permission and required_permission not in context.permissions:
        raise QueryToolError(
            code=ErrorCode.PERMISSION_DENIED,
            message="No tiene permisos para consultar este recurso.",
            request_id=context.request_id,
        )

    if required_module:
        validate_module_active(required_module)

        module_id = obtener_id_modulo_por_nombre(required_module)
        if not module_id:
            raise QueryToolError(
                code=ErrorCode.MODULE_DISABLED,
                message=f"El módulo '{required_module}' no está disponible.",
                request_id=context.request_id,
            )

        permisos = Permisos(modulo=module_id, usuario=context.user_id)
        if not permisos.autorizado:
            raise QueryToolError(
                code=ErrorCode.PERMISSION_DENIED,
                message="No tiene permisos para consultar este recurso.",
                request_id=context.request_id,
            )

    if company_id:
        validate_company_access(context, company_id)
