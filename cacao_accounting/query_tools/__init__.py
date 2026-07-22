"""Herramientas de consulta reutilizables para el módulo de contabilidad."""

from cacao_accounting.query_tools.registry import Registry, registry
from cacao_accounting.query_tools.decorators import query_tool, QueryTool
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import QueryToolError, ErrorCode
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate
from cacao_accounting.query_tools.publication import (
    EXTERNAL_SCOPE_PERMISSIONS,
    TOOL_EXTERNAL_SCOPES,
    is_published_read_tool,
    permissions_for_scopes,
    published_tool_scope,
)
from cacao_accounting.query_tools.bootstrap import load_query_tools

__all__ = [
    "Registry",
    "registry",
    "query_tool",
    "QueryTool",
    "QueryContext",
    "QueryToolError",
    "ErrorCode",
    "PaginatedResult",
    "paginate",
    "EXTERNAL_SCOPE_PERMISSIONS",
    "TOOL_EXTERNAL_SCOPES",
    "is_published_read_tool",
    "permissions_for_scopes",
    "published_tool_scope",
    "load_query_tools",
]
