from __future__ import annotations

from typing import Any

from cacao_accounting.query_tools.decorators import QueryTool
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, QueryTool] = {}

    def register(self, tool: QueryTool) -> None:
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                "Tool names must be unique."
            )
        if not tool.read_only:
            raise ValueError(
                f"Tool '{tool.name}' must declare read_only=True. "
                "Write operations are not allowed in query_tools."
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> QueryTool:
        tool = self._tools.get(name)
        if tool is None:
            raise QueryToolError(
                code=ErrorCode.TOOL_NOT_FOUND,
                message=f"Tool '{name}' not found.",
            )
        return tool

    def list_tools(self) -> dict[str, QueryTool]:
        return dict(self._tools)

    def get_tools_for_permissions(
        self, permissions: set[str]
    ) -> list[dict[str, Any]]:
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
        return len(self._tools)


registry = Registry()
