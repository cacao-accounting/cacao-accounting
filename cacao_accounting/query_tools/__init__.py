"""Herramientas de consulta reutilizables para el módulo de contabilidad."""

from cacao_accounting.query_tools.registry import Registry, registry
from cacao_accounting.query_tools.decorators import query_tool, QueryTool
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import QueryToolError, ErrorCode
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate

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
]
