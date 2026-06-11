from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QueryContext:
    user_id: str
    company_ids: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    source: str = "test"
    source_client: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
