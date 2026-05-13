# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import json
from datetime import date
import pytest
from cacao_accounting import create_app
from cacao_accounting.database import ComprobanteContable, GLEntry, Book, database

@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test_secret_key",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.database.helpers import inicia_base_de_datos
        inicia_base_de_datos(app, "admin", "admin", with_examples=True)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def login(client, username, password):
    client.get("/logout")
    resp = client.post(
        "/login",
        data={"usuario": username, "acceso": password, "inicio_sesion": "True"},
        follow_redirects=True,
    )
    if b"Inicio de Sesion Incorrecto" in resp.data:
        raise RuntimeError(f"Login failed for {username}")
    if b"Solo un usuario administrador puede iniciar sesion" in resp.data:
        raise RuntimeError(f"Login forbidden for {username} (Desktop Mode?)")
    return resp

def test_journal_entry_full_lifecycle_exhaustive(client, app):
    """
    Exhaustive test for Journal Entry lifecycle:
    Draft -> Submit (Post to 3 Books) -> Cancel (Reversal).
    """
    with app.app_context():
        login(client, "admin", "admin")

        # 1. Create Draft
        payload = {
            "company": "cacao",
            "posting_date": date.today().isoformat(),
            "memo": "Exhaustive Test Journal",
            "lines": [
                {"account": "11.01.001.001", "debit": "500.00", "credit": "0.00"},
                {"account": "31.01", "debit": "0.00", "credit": "500.00"},
            ]
        }
        resp = client.post(
            "/accounting/journal/new",
            data={"journal_payload": json.dumps(payload)},
            follow_redirects=True
        )
        assert resp.status_code == 200

        journal = database.session.execute(
            database.select(ComprobanteContable).filter_by(memo="Exhaustive Test Journal")
        ).scalar_one()
        assert journal.status == "draft"

        # 2. Submit (Posting)
        # Should post to FISC, FIN, MGMT books (as defined in demo data)
        resp = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=True)
        assert resp.status_code == 200

        database.session.refresh(journal)
        assert journal.status == "submitted"

        # Verify GL Entries.
        # 2 lines per book * 3 books = 6 lines.
        gl_entries_rows = database.session.execute(
            database.select(GLEntry, Book.code)
            .join(Book, GLEntry.ledger_id == Book.id)
            .filter(GLEntry.voucher_id == journal.id)
        ).all()
        assert len(gl_entries_rows) == 6

        books_posted = {row.code for row in gl_entries_rows}
        assert "FISC" in books_posted
        assert "FIN" in books_posted
        assert "MGMT" in books_posted

        # 3. Cancel (Reversal)
        resp = client.post(f"/accounting/journal/{journal.id}/cancel", follow_redirects=True)
        assert resp.status_code == 200

        database.session.refresh(journal)
        assert journal.status == "cancelled"

        # Verify Reversal GL Entries
        # Should have another 6 lines with inverted values
        reversal_entries = database.session.execute(
            database.select(GLEntry).filter_by(voucher_id=journal.id)
        ).scalars().all()
        assert len(reversal_entries) == 12

        total_balance = sum(e.debit - e.credit for e in reversal_entries)
        assert total_balance == 0

def test_rbac_manager_vs_auxiliar_vs_user(client, app):
    with app.app_context():
        # manager (accounting_manager) can do most things
        # contaj (accounting_auxiliar) can create but not submit/cancel
        # usuario (accounting_user) can only view

        from cacao_accounting.database import User, database

        for uname in ["conta", "contaj", "usuario"]:
            u = database.session.execute(database.select(User).filter_by(user=uname)).scalar_one()
            u.active = True
            if u.user != "admin":
                u.classification = "system"
        database.session.commit()

        # 1. Auxiliar (contaj) creates draft
        login(client, "contaj", "contaj")
        payload = {
            "company": "cacao",
            "posting_date": date.today().isoformat(),
            "memo": "Auxiliar Draft",
            "lines": [
                {"account": "11.01.001.001", "debit": "100", "credit": "0"},
                {"account": "31.01", "debit": "0", "credit": "100"},
            ]
        }
        client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})
        journal = database.session.execute(
            database.select(ComprobanteContable).filter_by(memo="Auxiliar Draft")
        ).scalar_one()

        # Auxiliar tries to submit -> Should be forbidden (403)
        resp = client.post(f"/accounting/journal/{journal.id}/submit")
        assert resp.status_code == 403

        # 2. Manager (conta) submits it
        login(client, "conta", "conta")
        resp = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Comprobante contable contabilizado" in resp.data

        # 3. Regular user (usuario) tries to cancel -> Forbidden
        login(client, "usuario", "usuario")
        resp = client.post(f"/accounting/journal/{journal.id}/cancel")
        assert resp.status_code == 403

def test_negative_direct_access_bypassing_ui(client, app):
    """Try to access accounting resources with a non-accounting user."""
    with app.app_context():
        from cacao_accounting.database import User, database
        # 'compras' user has access to purchases but not accounting
        u = database.session.execute(database.select(User).filter_by(user="compras")).scalar_one()
        u.active = True
        database.session.commit()

        login(client, "compras", "compras")

        # Try to access accounting home
        resp = client.get("/accounting/")
        assert resp.status_code == 403

        # Try to list journals
        resp = client.get("/accounting/journal/list")
        assert resp.status_code == 403

def test_journal_validation_unbalanced(client, app):
    with app.app_context():
        login(client, "admin", "admin")
        payload = {
            "company": "cacao",
            "posting_date": date.today().isoformat(),
            "memo": "Unbalanced Journal",
            "lines": [
                {"account": "11.01.001.001", "debit": "100.00", "credit": "0.00"},
                {"account": "31.01", "debit": "0.00", "credit": "50.00"},
            ]
        }
        resp = client.post(
            "/accounting/journal/new",
            data={"journal_payload": json.dumps(payload)},
            follow_redirects=True
        )
        assert b"El comprobante contable no esta balanceado" in resp.data

def test_journal_validation_missing_cost_center(client, app):
    with app.app_context():
        login(client, "admin", "admin")
        # 52.01.001 is an expense account and requires cost center
        # We need to ensure account 52.01.001 exists and is set as expense in DB
        from cacao_accounting.database import Accounts, database
        acc = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="52.01.001")).scalar_one()
        acc.account_type = "expense"
        database.session.commit()

        payload = {
            "company": "cacao",
            "posting_date": date.today().isoformat(),
            "memo": "Missing Cost Center",
            "lines": [
                {"account": "52.01.001", "debit": "100.00", "credit": "0.00"}, # No cost center
                {"account": "11.01.001.001", "debit": "0.00", "credit": "100.00"},
            ]
        }
        resp = client.post(
            "/accounting/journal/new",
            data={"journal_payload": json.dumps(payload)},
            follow_redirects=True
        )
        # In current implementation, JournalValidationError results in 200 with flash message
        # We check for the specific validation error message in the response data.
        assert b"Las cuentas de gasto requieren centro de costo" in resp.data
