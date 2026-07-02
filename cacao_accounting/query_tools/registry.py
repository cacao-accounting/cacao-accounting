"""Registro central de herramientas de consulta."""

from __future__ import annotations

from typing import Any

from cacao_accounting.query_tools.decorators import QueryTool
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError


class Registry:
    """Registro que almacena y gestiona las herramientas de consulta disponibles."""

    def __init__(self) -> None:
        """Inicializa el registro con un diccionario interno vacío de herramientas."""
        self._tools: dict[str, QueryTool] = {}

    def register(self, tool: QueryTool) -> None:
        """Registra una herramienta validando que sea única y de solo lectura."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered. " "Tool names must be unique.")
        if not tool.read_only:
            raise ValueError(
                f"Tool '{tool.name}' must declare read_only=True. " "Write operations are not allowed in query_tools."
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> QueryTool:
        """Obtiene una herramienta por su nombre; lanza QueryToolError si no existe."""
        tool = self._tools.get(name)
        if tool is None:
            raise QueryToolError(
                code=ErrorCode.TOOL_NOT_FOUND,
                message=f"Tool '{name}' not found.",
            )
        return tool

    def list_tools(self) -> dict[str, QueryTool]:
        """Devuelve una copia del diccionario con todas las herramientas registradas."""
        return dict(self._tools)

    def get_tools_for_permissions(self, permissions: set[str]) -> list[dict[str, Any]]:
        """Filtra y devuelve las herramientas que el conjunto de permisos puede ejecutar."""
        result: list[dict[str, Any]] = []
        for tool in self._tools.values():
            if tool.required_permission and tool.required_permission not in permissions:
                continue
            result.append(self._tool_to_schema(tool))
        return result

    def _tool_to_schema(self, tool: QueryTool) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "read_only": tool.read_only,
            "parameters": tool.parameters_schema,
            "response": tool.response_schema,
        }

    def get_count(self) -> int:
        """Devuelve la cantidad de herramientas registradas."""
        return len(self._tools)


registry = Registry()
