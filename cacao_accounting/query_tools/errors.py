from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    PERMISSION_DENIED = "permission_denied"
    COMPANY_ACCESS_DENIED = "company_access_denied"
    MODULE_DISABLED = "module_disabled"
    INVALID_PARAMETER = "invalid_parameter"
    MISSING_PARAMETER = "missing_parameter"
    TOOL_NOT_FOUND = "tool_not_found"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    PAGE_SIZE_EXCEEDED = "page_size_exceeded"
    DATE_RANGE_EXCEEDED = "date_range_exceeded"
    READ_ONLY_VIOLATION = "read_only_violation"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class QueryToolError(Exception):
    code: ErrorCode
    message: str
    request_id: str | None = None
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.request_id:
            result["request_id"] = self.request_id
        return {"error": result}
