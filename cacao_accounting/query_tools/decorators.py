"""Decoradores y definición de herramientas de consulta."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class QueryTool:
    """Descriptor inmutable de una herramienta de consulta."""

    name: str
    description: str
    required_permission: str | None = None
    required_module: str | None = None
    read_only: bool = True
    handler: Callable[..., Any] | None = None
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] = field(default_factory=dict)
    max_date_range_months: int | None = None
    needs_company: bool = True


def _validate_read_only(tool: QueryTool) -> None:
    if not tool.read_only:
        raise ValueError(
            f"Tool '{tool.name}' must declare read_only=True. " "Write operations are not allowed in query_tools."
        )


def query_tool(
    name: str,
    description: str,
    *,
    required_permission: str | None = None,
    required_module: str | None = None,
    parameters_schema: dict[str, Any] | None = None,
    response_schema: dict[str, Any] | None = None,
    max_date_range_months: int | None = None,
    needs_company: bool = True,
) -> Callable[[Callable[..., Any]], QueryTool]:
    """Decorador que registra una función como herramienta de consulta en el registro global."""
    from cacao_accounting.query_tools.registry import registry

    def wrapper(handler: Callable[..., Any]) -> QueryTool:
        tool = QueryTool(
            name=name,
            description=description,
            required_permission=required_permission,
            required_module=required_module,
            read_only=True,
            handler=handler,
            parameters_schema=parameters_schema or {},
            response_schema=response_schema or {},
            max_date_range_months=max_date_range_months,
            needs_company=needs_company,
        )
        _validate_read_only(tool)
        registry.register(tool)
        return tool

    return wrapper
