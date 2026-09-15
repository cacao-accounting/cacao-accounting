"""Registro central de herramientas de consulta."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cacao_accounting.i18n import _
from cacao_accounting.query_tools.decorators import QueryTool
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError

_LazyStringType: Any

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel.speaklater import LazyString as _LazyStringType  # type: ignore[no-redef]
except ImportError:  # pragma: no cover

    class _LazyStringType:  # type: ignore[no-redef]
        """Stub que nunca se instancia cuando Flask-Babel no esta disponible."""


class Registry:
    """Registro que almacena y gestiona las herramientas de consulta disponibles."""

    def __init__(self) -> None:
        """Inicializa el registro con un diccionario interno vacío de herramientas."""
        self._tools: dict[str, QueryTool] = {}

    def register(self, tool: QueryTool) -> None:
        """Registra una herramienta validando que sea única y de solo lectura."""
        if tool.name in self._tools:
            raise ValueError(
                _("La herramienta '%(tool)s' ya está registrada. Los nombres deben ser únicos.") % {"tool": tool.name}
            )
        if not tool.read_only:
            raise ValueError(
                _("La herramienta '%(tool)s' debe declarar read_only=True. Las operaciones de escritura no están permitidas.")
                % {"tool": tool.name}
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> QueryTool:
        """Obtiene una herramienta por su nombre; lanza QueryToolError si no existe."""
        tool = self._tools.get(name)
        if tool is None:
            raise QueryToolError(
                code=ErrorCode.TOOL_NOT_FOUND,
                message=_("Herramienta '%(name)s' no encontrada.") % {"name": name},
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
            "description": _serialize_schema(tool.description),
            "read_only": tool.read_only,
            "parameters": _serialize_schema(tool.parameters_schema),
            "response": _serialize_schema(tool.response_schema),
        }

    def get_count(self) -> int:
        """Devuelve la cantidad de herramientas registradas."""
        return len(self._tools)


def _serialize_schema(value: Any) -> Any:
    """Materializa textos diferidos antes de incluirlos en una respuesta JSON."""
    if isinstance(value, _LazyStringType):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _serialize_schema(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return tuple(_serialize_schema(child) for child in value)
    if isinstance(value, list):
        return [_serialize_schema(child) for child in value]
    return value


registry = Registry()
