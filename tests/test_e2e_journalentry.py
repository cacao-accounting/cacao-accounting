# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

import json
from typing import Any

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


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _seed_journal_catalog() -> dict[str, str]:
    from cacao_accounting.database import Accounts, Book, User, database

    debit_account = Accounts(entity="cacao", code="EXP-E2E", name="Gasto E2E", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-E2E", name="Caja E2E", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    ifrs_book = Book(entity="cacao", code="IFRS", name="IFRS", status="activo")
    database.session.add_all([debit_account, credit_account, fiscal_book, ifrs_book])
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    return {
        "debit": debit_account.id,
        "credit": credit_account.id,
        "user_id": user.id,
    }


def _post_new_journal(client: Any, payload: dict[str, Any]):
    return client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})


def test_e2e_journalentry_full_flow_create_edit_submit_and_verify(app_ctx):
    from cacao_accounting.database import ComprobanteContable, GLEntry, database

    seeded = _seed_journal_catalog()
    client = app_ctx.test_client()
    _login(client, seeded["user_id"])

    get_response = client.get("/accounting/journal/new")
    assert get_response.status_code == 200

    payload = {
        "company": "cacao",
        "posting_date": "2026-05-09",
        "books": ["FISC", "IFRS"],
        "transaction_currency": "NIO",
        "memo": "E2E borrador inicial",
        "lines": [
            {"account": seeded["debit"], "debit": "100.00", "credit": "0", "cost_center": "CC-01"},
            {"account": seeded["credit"], "debit": "0", "credit": "100.00", "unit": "UNIT-01"},
        ],
    }

    post_response = _post_new_journal(client, payload)
    journal = database.session.execute(
        database.select(ComprobanteContable).filter_by(memo="E2E borrador inicial")
    ).scalar_one()

    view_response = client.get(f"/accounting/journal/{journal.id}")
    edit_get_response = client.get(f"/accounting/journal/edit/{journal.id}")
    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()

    assert post_response.status_code == 302
    assert view_response.status_code == 200
    assert edit_get_response.status_code == 200
    assert f"/accounting/journal/{journal.id}" in edit_get_response.get_data(as_text=True)
    assert journal.status == "draft"
    assert journal.entity == "cacao"
    assert journal.book == "FISC"
    assert journal.transaction_currency == "NIO"
    assert gl_entries == []

    update_payload = {
        "company": "cacao",
        "posting_date": "2026-05-10",
        "books": ["IFRS"],
        "transaction_currency": "NIO",
        "memo": "E2E borrador actualizado",
        "lines": [
            {"account": seeded["debit"], "debit": "140.00", "credit": "0", "project": "PRJ-E2E"},
            {
                "account": seeded["credit"],
                "debit": "0",
                "credit": "140.00",
                "party_type": "supplier",
                "party": "SUP-E2E",
            },
        ],
    }
    edit_post_response = client.post(
        f"/accounting/journal/edit/{journal.id}",
        data={"journal_payload": json.dumps(update_payload)},
        follow_redirects=False,
    )
    assert edit_post_response.status_code == 302

    updated = database.session.get(ComprobanteContable, journal.id)
    assert updated.memo == "E2E borrador actualizado"
    assert updated.book == "IFRS"
    assert updated.status == "draft"

    verify_update_response = client.get(f"/accounting/journal/{journal.id}")
    assert verify_update_response.status_code == 200
    assert "E2E borrador actualizado" in verify_update_response.get_data(as_text=True)

    submit_response = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=False)
    assert submit_response.status_code == 302

    submitted = database.session.get(ComprobanteContable, journal.id)
    posted_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    assert submitted.status == "submitted"
    assert posted_entries

    final_view_response = client.get(f"/accounting/journal/{journal.id}")
    assert final_view_response.status_code == 200
    assert "/cancel" in final_view_response.get_data(as_text=True)


def test_e2e_journalentry_reject_draft_does_not_touch_ledger(app_ctx):
    from cacao_accounting.database import ComprobanteContable, GLEntry, database

    seeded = _seed_journal_catalog()
    client = app_ctx.test_client()
    _login(client, seeded["user_id"])

    payload = {
        "company": "cacao",
        "posting_date": "2026-05-09",
        "books": ["FISC"],
        "memo": "E2E draft reject",
        "lines": [
            {"account": seeded["debit"], "debit": "60.00", "credit": "0"},
            {"account": seeded["credit"], "debit": "0", "credit": "60.00"},
        ],
    }

    _post_new_journal(client, payload)
    journal = database.session.execute(database.select(ComprobanteContable).filter_by(memo="E2E draft reject")).scalar_one()
    reject_response = client.post(f"/accounting/journal/{journal.id}/reject", follow_redirects=False)

    rejected = database.session.get(ComprobanteContable, journal.id)
    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()

    assert reject_response.status_code == 302
    assert rejected.status == "rejected"
    assert gl_entries == []


def test_e2e_journalentry_cancel_submitted_creates_reversal_entries(app_ctx):
    from cacao_accounting.database import ComprobanteContable, GLEntry, database

    seeded = _seed_journal_catalog()
    client = app_ctx.test_client()
    _login(client, seeded["user_id"])

    payload = {
        "company": "cacao",
        "posting_date": "2026-05-09",
        "books": ["FISC"],
        "memo": "E2E submitted cancel",
        "lines": [
            {"account": seeded["debit"], "debit": "90.00", "credit": "0"},
            {"account": seeded["credit"], "debit": "0", "credit": "90.00"},
        ],
    }
    _post_new_journal(client, payload)

    journal = database.session.execute(
        database.select(ComprobanteContable).filter_by(memo="E2E submitted cancel")
    ).scalar_one()
    submit_response = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=False)
    assert submit_response.status_code == 302

    cancel_response = client.post(f"/accounting/journal/{journal.id}/cancel", follow_redirects=False)
    cancelled = database.session.get(ComprobanteContable, journal.id)
    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    reversal_entries = [entry for entry in entries if entry.is_reversal]
    original_entries = [entry for entry in entries if not entry.is_reversal]

    assert cancel_response.status_code == 302
    assert cancelled.status == "cancelled"
    assert reversal_entries
    assert original_entries
    assert all(entry.is_cancelled for entry in original_entries)


@pytest.mark.parametrize("origin_status", ["draft", "rejected", "submitted"])
def test_e2e_journalentry_duplicate_from_allowed_statuses_creates_draft(app_ctx, origin_status: str):
    from cacao_accounting.database import ComprobanteContable, ComprobanteContableDetalle, database

    seeded = _seed_journal_catalog()
    client = app_ctx.test_client()
    _login(client, seeded["user_id"])

    payload = {
        "company": "cacao",
        "posting_date": "2026-05-09",
        "books": ["FISC"],
        "memo": f"E2E duplicate origin {origin_status}",
        "lines": [
            {"account": seeded["debit"], "debit": "80.00", "credit": "0", "cost_center": "CC-01"},
            {"account": seeded["credit"], "debit": "0", "credit": "80.00"},
        ],
    }
    _post_new_journal(client, payload)

    journal = database.session.execute(
        database.select(ComprobanteContable).filter_by(memo=f"E2E duplicate origin {origin_status}")
    ).scalar_one()

    if origin_status == "rejected":
        reject_response = client.post(f"/accounting/journal/{journal.id}/reject", follow_redirects=False)
        assert reject_response.status_code == 302
    if origin_status == "submitted":
        submit_response = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=False)
        assert submit_response.status_code == 302

    duplicate_response = client.post(f"/accounting/journal/{journal.id}/duplicate", follow_redirects=False)
    duplicated = (
        database.session.execute(database.select(ComprobanteContable).filter(ComprobanteContable.memo.like("Duplicado de%")))
        .scalars()
        .all()
    )
    duplicated_ids = {item.id for item in duplicated}
    duplicated_lines = (
        database.session.execute(
            database.select(ComprobanteContableDetalle).filter(ComprobanteContableDetalle.transaction_id.in_(duplicated_ids))
        )
        .scalars()
        .all()
        if duplicated_ids
        else []
    )

    assert duplicate_response.status_code == 302
    assert "/accounting/journal/edit/" in duplicate_response.headers.get("Location", "")
    assert duplicated
    assert all(item.status == "draft" for item in duplicated)
    assert all(item.document_no is None for item in duplicated)
    assert duplicated_lines


def test_e2e_journalentry_revert_creates_editable_reversed_draft(app_ctx):
    from cacao_accounting.database import ComprobanteContable, ComprobanteContableDetalle, database

    seeded = _seed_journal_catalog()
    client = app_ctx.test_client()
    _login(client, seeded["user_id"])

    payload = {
        "company": "cacao",
        "posting_date": "2026-05-09",
        "books": ["FISC"],
        "memo": "E2E revert origin",
        "lines": [
            {"account": seeded["debit"], "debit": "120.00", "credit": "0"},
            {"account": seeded["credit"], "debit": "0", "credit": "120.00"},
        ],
    }
    _post_new_journal(client, payload)

    journal = database.session.execute(database.select(ComprobanteContable).filter_by(memo="E2E revert origin")).scalar_one()
    submit_response = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=False)
    assert submit_response.status_code == 302

    revert_response = client.post(f"/accounting/journal/{journal.id}/revert", follow_redirects=False)
    reversed_journal = (
        database.session.execute(database.select(ComprobanteContable).filter(ComprobanteContable.memo.like("Reversión de%")))
        .scalars()
        .first()
    )
    reversed_lines = (
        database.session.execute(
            database.select(ComprobanteContableDetalle)
            .filter_by(transaction_id=reversed_journal.id)
            .order_by(ComprobanteContableDetalle.order.asc())
        )
        .scalars()
        .all()
    )

    assert revert_response.status_code == 302
    assert "/accounting/journal/edit/" in revert_response.headers.get("Location", "")
    assert reversed_journal is not None
    assert reversed_journal.status == "draft"
    assert reversed_journal.document_no is None
    assert reversed_lines[0].value == -120
    assert reversed_lines[1].value == 120


@pytest.mark.parametrize(
    "case_name,line_overrides",
    [
        ("account_cost_center", {"cost_center": "CC-01"}),
        ("account_unit", {"unit": "UNIT-01"}),
        ("account_project", {"project": "PRJ-01"}),
        ("account_party_customer", {"party_type": "customer", "party": "CUS-01"}),
        ("account_party_supplier", {"party_type": "supplier", "party": "SUP-01"}),
        ("account_party_employee", {"party_type": "employee", "party": "EMP-01"}),
        (
            "account_references_advance",
            {
                "reference_type": "purchase_invoice",
                "reference_name": "PI-01",
                "reference1": "REF-A",
                "reference2": "REF-B",
                "is_advance": True,
            },
        ),
        (
            "account_cross_dimensions",
            {
                "cost_center": "CC-01",
                "unit": "UNIT-01",
                "project": "PRJ-01",
                "party_type": "supplier",
                "party": "SUP-X",
                "reference_type": "purchase_invoice",
                "reference_name": "PI-X",
            },
        ),
    ],
)
def test_e2e_journalentry_matrix_combinations_draft_persistence(app_ctx, case_name: str, line_overrides: dict[str, Any]):
    from cacao_accounting.database import ComprobanteContable, ComprobanteContableDetalle, database

    seeded = _seed_journal_catalog()
    client = app_ctx.test_client()
    _login(client, seeded["user_id"])

    first_line = {"account": seeded["debit"], "debit": "45.00", "credit": "0"}
    first_line.update(line_overrides)
    payload = {
        "company": "cacao",
        "posting_date": "2026-05-09",
        "books": ["FISC"],
        "memo": f"E2E matrix {case_name}",
        "lines": [
            first_line,
            {"account": seeded["credit"], "debit": "0", "credit": "45.00"},
        ],
    }

    create_response = _post_new_journal(client, payload)
    assert create_response.status_code == 302

    journal = database.session.execute(
        database.select(ComprobanteContable).filter_by(memo=f"E2E matrix {case_name}")
    ).scalar_one()
    lines = (
        database.session.execute(
            database.select(ComprobanteContableDetalle)
            .filter_by(transaction_id=journal.id)
            .order_by(ComprobanteContableDetalle.order.asc())
        )
        .scalars()
        .all()
    )

    assert journal.status == "draft"
    assert len(lines) == 2
    assert lines[0].account == "EXP-E2E"
    if "cost_center" in line_overrides:
        assert lines[0].cost_center == line_overrides["cost_center"]
    if "unit" in line_overrides:
        assert lines[0].unit == line_overrides["unit"]
    if "project" in line_overrides:
        assert lines[0].project == line_overrides["project"]
    if "party_type" in line_overrides:
        assert lines[0].third_type == line_overrides["party_type"]
    if "party" in line_overrides:
        assert lines[0].third_code == line_overrides["party"]
    if "reference_type" in line_overrides:
        assert lines[0].internal_reference == line_overrides["reference_type"]
    if "reference_name" in line_overrides:
        assert lines[0].internal_reference_id == line_overrides["reference_name"]
    if "reference1" in line_overrides:
        assert lines[0].reference1 == line_overrides["reference1"]
    if "reference2" in line_overrides:
        assert lines[0].reference2 == line_overrides["reference2"]
    if "is_advance" in line_overrides:
        assert lines[0].is_advance is True
