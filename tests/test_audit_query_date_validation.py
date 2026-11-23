# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1969: el handler de actividad valida fechas y rango."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cacao_accounting.query_tools.errors import QueryToolError
from cacao_accounting.query_tools.handlers import audit_trail


def _contexto():
    return SimpleNamespace(user_id="u1", company_ids=("cacao",))


def test_fecha_imposible_es_error_de_parametro(app, monkeypatch):
    """Una fecha inválida no escapa como ValueError."""
    monkeypatch.setattr(audit_trail, "validate_permission", lambda *a, **k: None)
    with app.app_context():
        with pytest.raises(QueryToolError):
            audit_trail.get_user_activity_summary.handler(context=_contexto(), company_id="cacao", date_from="2026-02-31")


def test_rango_invertido_es_error_de_parametro(app, monkeypatch):
    """date_from posterior a date_to se rechaza antes de consultar."""
    monkeypatch.setattr(audit_trail, "validate_permission", lambda *a, **k: None)
    with app.app_context():
        with pytest.raises(QueryToolError):
            audit_trail.get_user_activity_summary.handler(
                context=_contexto(), company_id="cacao", date_from="2026-12-31", date_to="2026-01-01"
            )
