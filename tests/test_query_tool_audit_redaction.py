# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los eventos de query tools no persisten secretos dentro de filtros anidados."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, User, database
from cacao_accounting.query_tools.audit import log_query_tool_event
from cacao_accounting.query_tools.context import QueryContext

pytestmark = pytest.mark.database


@pytest.fixture
def isolated_audit_app(tmp_path: Path, request):
    """Provide an isolated SQLite database or PostgreSQL schema for audit evidence."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    external_postgres = uri.startswith("postgresql")
    check_database = os.environ.get("CHECK_DATABASE", "").strip().lower() in {"1", "true", "yes", "on"}
    if check_database and not external_postgres and not uri.startswith("sqlite"):
        pytest.skip("La auditoría aislada solo admite SQLite o PostgreSQL.")

    schema_name = f"query_audit_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri) if external_postgres else None
    if external_postgres:
        assert bootstrap_engine is not None
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        connect_args = {"options": f"-csearch_path={schema_name}"}
        database_uri = uri
        engine_options: Any = {"pool_size": 4, "max_overflow": 0, "connect_args": connect_args}
    else:
        database_uri = f"sqlite:///{tmp_path / 'query-audit.sqlite'}"
        engine_options = {"connect_args": {"check_same_thread": False}}

    application = None

    def cleanup_database():
        """Dispose of the app engine and remove its PostgreSQL schema."""
        if application is not None:
            with application.app_context():
                database.session.remove()
                database.engine.dispose()
        if bootstrap_engine is not None:
            with bootstrap_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            bootstrap_engine.dispose()

    request.addfinalizer(cleanup_database)
    app_settings: dict[str, Any] = dict(configuracion)
    app_settings.update(
        {
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": engine_options,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "isolated-query-audit-test",
        }
    )
    application = create_app(app_settings)
    with application.app_context():
        database.create_all()
        user_name = f"audit-{uuid4().hex[:18]}"
        user = User(user=user_name, name="Audit Test", password=b"unused", classification="admin", active=True)
        database.session.add(user)
        database.session.commit()
        user_id = str(database.session.execute(select(User.id).where(User.user == user_name)).scalar_one())

    yield application, user_id


def test_auditoria_redacta_secretos_en_listas_anidadas(isolated_audit_app):
    """La evidencia persistida conserva filtros sin exponer sus credenciales."""
    app, user_id = isolated_audit_app
    tool_name = f"redact-{uuid4().hex[:18]}"
    secrets = {
        "api_key": "api-list-secret",
        "password": "password-list-secret",
        "nested": {"secret": "nested-list-secret"},
        "tokens": [{"token": "token-list-secret", "access_token": "access-list-secret"}],
    }

    with app.app_context():
        log_query_tool_event(
            action="query_tool.executed",
            context=QueryContext(user_id=user_id),
            tool_name=tool_name,
            parameters={"filters": [secrets]},
        )
        database.session.commit()

        entry = database.session.execute(
            select(AuditTrail).where(AuditTrail.document_id == tool_name, AuditTrail.document_type == "query_tool")
        ).scalar_one()
        persisted_parameters = json.loads(entry.after_json)

    persisted_filters = persisted_parameters["filters"][0]
    assert persisted_filters == {
        "api_key": "***",
        "password": "***",
        "nested": {"secret": "***"},
        "tokens": [{"token": "***", "access_token": "***"}],
    }
    secret_values = (
        "api-list-secret",
        "password-list-secret",
        "nested-list-secret",
        "token-list-secret",
        "access-list-secret",
    )
    assert all(value not in entry.after_json for value in secret_values)
