"""#2178/#2238: redacta secretos en listas y listas anidadas."""

from __future__ import annotations

import json

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, database
from cacao_accounting.query_tools.audit import log_query_tool_event, serialize_parameters
from cacao_accounting.query_tools.context import QueryContext


def test_serialize_parameters_redacts_sensitive_keys_inside_nested_lists():
    payload = {
        "filters": [
            {
                "api_key": "list-api-secret",
                "nested": {"secret": "nested-secret-value", "ok": "visible"},
                "tokens": [{"token": "token-secret-value", "access_token": "access-token-secret"}],
            }
        ],
        "password": "top-password-secret",
        "plain": "value",
    }

    sanitized = serialize_parameters(payload)

    assert sanitized["password"] == "***"
    assert sanitized["plain"] == "value"
    assert sanitized["filters"][0]["api_key"] == "***"
    assert sanitized["filters"][0]["nested"]["secret"] == "***"
    assert sanitized["filters"][0]["nested"]["ok"] == "visible"
    assert sanitized["filters"][0]["tokens"][0]["token"] == "***"
    assert sanitized["filters"][0]["tokens"][0]["access_token"] == "***"


def test_log_query_tool_event_persists_redacted_nested_lists():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "redaction-lists-test",
        }
    )
    secret_values = [
        "list-api-secret",
        "nested-secret-value",
        "token-secret-value",
        "access-token-secret",
        "top-password-secret",
    ]
    with app.app_context():
        database.create_all()
        database.session.execute(database.text("PRAGMA foreign_keys=OFF"))
        log_query_tool_event(
            action="query_tool.executed",
            context=QueryContext(user_id="audit-user"),
            tool_name="probe-nested-lists",
            parameters={
                "filters": [
                    {
                        "api_key": "list-api-secret",
                        "nested": {"secret": "nested-secret-value"},
                        "tokens": [{"token": "token-secret-value", "access_token": "access-token-secret"}],
                    }
                ],
                "password": "top-password-secret",
            },
        )
        database.session.commit()

        entry = database.session.execute(
            database.select(AuditTrail).where(
                AuditTrail.document_type == "query_tool",
                AuditTrail.document_id == "probe-nested-lists",
            )
        ).scalar_one()
        persisted = json.loads(entry.after_json)

    assert persisted["password"] == "***"
    assert persisted["filters"][0]["api_key"] == "***"
    assert persisted["filters"][0]["nested"]["secret"] == "***"
    assert persisted["filters"][0]["tokens"][0]["token"] == "***"
    assert persisted["filters"][0]["tokens"][0]["access_token"] == "***"
    for secret in secret_values:
        assert secret not in (entry.after_json or "")
