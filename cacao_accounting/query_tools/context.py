"""Contexto de ejecución para herramientas de consulta."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QueryContext:
    """Contexto con datos del usuario, compañías, permisos y origen de la solicitud."""

    user_id: str
    company_ids: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    source: str = "test"
    source_client: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    # Service principals are authorized by their signed scopes and company
    # allow-list. They do not have an upstream user row to resolve via
    # ``Permisos``.
    is_service_principal: bool = False
    allow_all_companies: bool = False
