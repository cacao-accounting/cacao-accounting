# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


def _seed_accounts():
    from cacao_accounting.database import Accounts, database

    debit_account = Accounts(entity="cacao", code="EXP-001", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-001", name="Caja", active=True, enabled=True, group=False)
    database.session.add_all([debit_account, credit_account])
    database.session.commit()
    return debit_account, credit_account


def _journal_payload(debit_account_id: str, credit_account_id: str, memo: str = "Registro inicial") -> dict:
    return {
        "company": "cacao",
        "posting_date": date.today().isoformat(),
        "memo": memo,
        "lines": [
            {"account": debit_account_id, "debit": "100.00", "credit": "0"},
            {"account": credit_account_id, "debit": "0", "credit": "100.00"},
        ],
    }


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_audit_trail_created_on_journal_create(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import AuditTrail, database

    debit_account, credit_account = _seed_accounts()
    journal = create_journal_draft(_journal_payload(debit_account.id, credit_account.id), user_id="admin")
    rows = database.session.execute(database.select(AuditTrail).where(AuditTrail.document_id == journal.id)).scalars().all()
    assert any(row.action == "created" for row in rows)


def test_audit_trail_updated_contains_changes_json(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, update_journal_draft
    from cacao_accounting.database import AuditTrail, database

    debit_account, credit_account = _seed_accounts()
    journal = create_journal_draft(_journal_payload(debit_account.id, credit_account.id), user_id="admin")
    update_journal_draft(
        journal.id, _journal_payload(debit_account.id, credit_account.id, memo="Memo editado"), user_id="admin"
    )
    updated = (
        database.session.execute(
            database.select(AuditTrail)
            .where(AuditTrail.document_id == journal.id)
            .where(AuditTrail.action == "updated")
            .order_by(AuditTrail.timestamp.desc())
        )
        .scalars()
        .first()
    )
    assert updated is not None
    changes = json.loads(updated.changes_json or "{}")
    assert "memo" in changes
    assert changes["memo"]["after"] == "Memo editado"


def test_audit_trail_submit_and_cancel_events(app_ctx):
    from cacao_accounting.contabilidad.journal_service import cancel_submitted_journal, create_journal_draft, submit_journal
    from cacao_accounting.database import AuditTrail, database

    debit_account, credit_account = _seed_accounts()
    journal = create_journal_draft(_journal_payload(debit_account.id, credit_account.id), user_id="admin")
    submit_journal(journal.id)
    cancel_submitted_journal(journal.id, user_id="admin")
    actions = [
        row.action
        for row in database.session.execute(
            database.select(AuditTrail).where(AuditTrail.document_id == journal.id).order_by(AuditTrail.timestamp.asc())
        )
        .scalars()
        .all()
    ]
    assert "submitted" in actions
    assert "cancelled" in actions


def test_timeline_skip_fields_handles_none_and_empty_sets(app_ctx):
    from cacao_accounting.audit_trail_service import _timeline_skip_fields

    assert _timeline_skip_fields(None) == frozenset(
        {
            "updated_at",
            "modified_at",
            "last_seen",
            "last_modified",
            "last_updated",
            "modification_date",
        }
    )
    assert _timeline_skip_fields(set()) == _timeline_skip_fields(None)


def test_timeline_skip_fields_merges_exclusions(app_ctx):
    from cacao_accounting.audit_trail_service import _timeline_skip_fields

    skip_fields = _timeline_skip_fields({"status", "memo"})

    assert "status" in skip_fields
    assert "memo" in skip_fields
    assert "updated_at" in skip_fields


def test_format_document_timeline_hides_noise_fields_and_formats_values(app_ctx):
    from cacao_accounting.audit_trail_service import format_document_timeline
    from cacao_accounting.database import AuditTrail, database

    database.session.add(
        AuditTrail(
            document_type="journal_entry",
            document_id="JRN-001",
            action="updated",
            changes_json=json.dumps(
                {
                    "memo": {"before": "", "after": "Memo final"},
                    "updated_at": {"before": "2026-05-06", "after": "2026-05-07"},
                    "status": {"before": None, "after": 1},
                }
            ),
        )
    )
    database.session.commit()

    timeline = format_document_timeline("journal_entry", "JRN-001", exclude_fields={"status"})

    assert len(timeline) == 1
    assert timeline[0]["changes"] == [{"field": "memo", "before": "-", "after": "Memo final"}]


def test_format_document_timeline_handles_invalid_json(app_ctx):
    from cacao_accounting.audit_trail_service import format_document_timeline
    from cacao_accounting.database import AuditTrail, database

    database.session.add(
        AuditTrail(
            document_type="journal_entry",
            document_id="JRN-002",
            action="updated",
            changes_json="{not-valid-json}",
        )
    )
    database.session.commit()

    timeline = format_document_timeline("journal_entry", "JRN-002")

    assert len(timeline) == 1
    assert timeline[0]["changes"] == []


def test_journal_detail_renders_changes_timeline(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, update_journal_draft
    from cacao_accounting.database import User, database

    debit_account, credit_account = _seed_accounts()
    journal = create_journal_draft(_journal_payload(debit_account.id, credit_account.id), user_id="admin")
    update_journal_draft(
        journal.id, _journal_payload(debit_account.id, credit_account.id, memo="Cambio visible"), user_id="admin"
    )

    user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    client = app_ctx.test_client()
    _login(client, str(user.id))
    response = client.get(f"/accounting/journal/{journal.id}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Historial del documento" in html
    assert "Cambió" in html
    assert "memo" in html
