# SPDX-License-Identifier: Apache-2.0
"""Tests for Balance Confirmation (Confirmación de Saldos) features."""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    database,
    Entity,
    Party,
    CompanyParty,
    Modules,
    User,
    SalesInvoice,
    PaymentEntry,
    DocumentRelation,
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    AuditTrail,
)
from cacao_accounting.contabilidad.balance_confirmation import (
    get_open_documents_at_cutoff,
    create_balance_confirmation,
)


@pytest.fixture()
def app_ctx():
    """Create an isolated app with database in-memory."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "balance-confirmation-tests",
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        _seed_test_data()
        yield app
        database.session.remove()
        database.drop_all()


def _seed_test_data() -> None:
    # Entities
    database.session.add_all(
        [
            Entity(
                id="ent-1", code="cacao", name="Cacao", company_name="Cacao S.A.", tax_id="J1001", currency="NIO", enabled=True
            ),
            Modules(id="mod-acc", module="accounting", default=True, enabled=True),
            Modules(id="mod-sales", module="sales", default=True, enabled=True),
            Modules(id="mod-purchases", module="purchases", default=True, enabled=True),
            User(id="user-admin", user="admin", name="Admin", password=b"x", classification="admin", active=True),
            # Parties
            Party(id="cust-1", code="CLI-01", is_customer=True, is_supplier=False, name="Cliente Uno", is_active=True),
            Party(id="supp-1", code="PROV-01", is_customer=False, is_supplier=True, name="Proveedor Uno", is_active=True),
            Party(id="cust-2", code="CLI-02", is_customer=True, is_supplier=False, name="Cliente Inactivo", is_active=True),
            # Activation by company
            CompanyParty(company="cacao", party_id="cust-1", is_active=True),
            CompanyParty(company="cacao", party_id="supp-1", is_active=True),
            CompanyParty(company="cacao", party_id="cust-2", is_active=False),
        ]
    )
    database.session.commit()

    # Sales Invoices: some before cutoff, some after
    database.session.add_all(
        [
            # Before Cutoff
            SalesInvoice(
                id="inv-1",
                company="cacao",
                customer_id="cust-1",
                posting_date=date(2026, 5, 10),
                grand_total=Decimal("5000.00"),
                outstanding_amount=Decimal("5000.00"),
                transaction_currency="USD",
                base_currency="NIO",
                docstatus=1,
                document_no="FV-00123",
            ),
            SalesInvoice(
                id="inv-2",
                company="cacao",
                customer_id="cust-1",
                posting_date=date(2026, 5, 15),
                document_type="sales_credit_note",
                grand_total=Decimal("500.00"),
                outstanding_amount=Decimal("500.00"),
                transaction_currency="USD",
                base_currency="NIO",
                docstatus=1,
                document_no="NC-00012",
            ),
            # After Cutoff
            SalesInvoice(
                id="inv-3",
                company="cacao",
                customer_id="cust-1",
                posting_date=date(2026, 9, 5),
                grand_total=Decimal("2000.00"),
                outstanding_amount=Decimal("2000.00"),
                transaction_currency="USD",
                base_currency="NIO",
                docstatus=1,
                document_no="FV-00124",
            ),
        ]
    )
    database.session.commit()

    # Document Relations for credit notes applied before cutoff
    database.session.add_all(
        [
            DocumentRelation(
                id="rel-1",
                source_type="sales_invoice",
                source_id="inv-1",
                target_type="sales_credit_note",
                target_id="inv-2",
                qty=Decimal("1"),
                amount=Decimal("500.00"),
                relation_type="invoice_reversal",
                status="active",
            )
        ]
    )
    database.session.commit()

    # Payment Entries
    database.session.add_all(
        [
            PaymentEntry(
                id="pay-1",
                company="cacao",
                party_type="customer",
                party_id="cust-1",
                payment_type="receive",
                posting_date=date(2026, 5, 20),
                paid_amount=Decimal("1000.00"),
                received_amount=Decimal("1000.00"),
                currency="USD",
                docstatus=1,
                document_no="PG-00451",
                is_advance=False,
            )
        ]
    )
    database.session.commit()


def _login(client, user_id: str = "user-admin") -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_outstanding_balance_calculation_at_cutoff(app_ctx) -> None:
    """Reconstructs outstanding balances exactly up to the cutoff date, excluding future events."""
    cutoff = date(2026, 5, 31)

    # Customer open documents at cutoff
    items = get_open_documents_at_cutoff(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
    )

    # We expect:
    # 1. FV-00123: original +5000, outstanding 4500 (NC aplicada neteada)
    # 2. NC-00012: excluded (saldo 500 - monto aplicado 500 = 0)
    # 3. PG-00451: unapplied payment -1000, outstanding -1000
    # Total sum should be 3500
    assert len(items) == 2

    fvs = [i for i in items if i["document_no"] == "FV-00123"]
    ncs = [i for i in items if i["document_no"] == "NC-00012"]
    pgs = [i for i in items if i["document_no"] == "PG-00451"]

    assert len(fvs) == 1
    assert len(ncs) == 0
    assert len(pgs) == 1

    # Outstanding totals checking
    totals: dict[str, Decimal] = {}
    for i in items:
        totals[i["currency"]] = totals.get(i["currency"], Decimal("0")) + Decimal(i["outstanding_amount"])

    assert totals["USD"] == Decimal("3500.00")


def test_balance_confirmation_uses_canonical_ar_ap_ledger(app_ctx) -> None:
    """La confirmación toma el saldo documental del ledger, no el cache de factura."""
    from cacao_accounting.database import ARAPLedgerEntry

    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR",
            party_type="customer",
            party_id="cust-1",
            document_type="sales_invoice",
            document_id="inv-1",
            posting_date=date(2026, 5, 10),
            event_type="opening",
            currency="USD",
            document_amount=Decimal("4200"),
            economic_line_id="inv-1",
        )
    )
    database.session.commit()

    items = get_open_documents_at_cutoff("cacao", "cust-1", "customer", date(2026, 5, 31))
    invoice = next(item for item in items if item["document_no"] == "FV-00123")
    assert invoice["outstanding_amount"] == "4200.0000"


def test_desktop_mode_rejection(app_ctx) -> None:
    """Desktop mode must completely reject any backend endpoints and hide buttons."""
    app_ctx.config["MODO_ESCRITORIO"] = True
    client = app_ctx.test_client()
    _login(client)

    # Internal API create confirmation
    res1 = client.post(
        "/accounting/balance-confirmations/new?party_id=cust-1&party_type=customer",
        data={"company_id": "cacao", "cutoff_date": "2026-05-31", "emails": ["user@example.com"]},
    )
    assert res1.status_code == 403


def test_create_and_send_balance_confirmation(app_ctx, monkeypatch) -> None:
    """Tests balance confirmation draft creation, snapshotting, and secure email sending."""
    sent_emails = []

    def mock_send_email(to_email, subject, body, is_html=False):
        sent_emails.append(
            {
                "to_email": to_email,
                "subject": subject,
                "body": body,
            }
        )

    from cacao_accounting.contabilidad import balance_confirmation_bp

    monkeypatch.setattr(balance_confirmation_bp, "send_email", mock_send_email)

    client = app_ctx.test_client()
    _login(client)

    res = client.post(
        "/accounting/balance-confirmations/new?party_id=cust-1&party_type=customer",
        data={"company_id": "cacao", "cutoff_date": "2026-05-31", "emails_text": "contact1@example.com, contact2@example.com"},
    )
    assert res.status_code == 302  # Redirects to detail view

    # Check confirmation and invitations created
    conf = database.session.execute(select(BalanceConfirmation).filter_by(party_id="cust-1")).scalar_one_or_none()
    assert conf is not None
    assert conf.status == "draft"
    assert conf.company == "cacao"

    invitations = (
        database.session.execute(
            select(BalanceConfirmationInvitation).where(BalanceConfirmationInvitation.balance_confirmation_id == conf.id)
        )
        .scalars()
        .all()
    )
    assert len(invitations) == 2

    # Test send endpoint
    # Since we can obtain raw tokens/codes before the commit in create view, but wait, the view has already committed.
    # We can retrieve the tokens/codes from the transient attributes of the objects still in the identity map,
    # or even simpler, we can extract them when the emails are sent!
    res_send = client.post(f"/accounting/balance-confirmations/{conf.id}/send")
    assert res_send.status_code == 302
    assert conf.status == "sent"

    # Verify emails were captured
    assert len(sent_emails) == 2
    for email in sent_emails:
        assert "Código de verificación:" in email["body"]
        assert "confirm-balance" in email["body"]

    # Verify AuditTrail logs
    actions = database.session.execute(select(AuditTrail.action).where(AuditTrail.document_id == conf.id)).scalars().all()
    assert "balance_confirmation_created" in actions
    assert "balance_confirmation_sent" in actions


def test_public_verification_and_response_flow(app_ctx) -> None:
    """Verifies third-party secure access, identity verification, authorization agreement, and final response."""
    # Create draft and get details
    cutoff = date(2026, 5, 31)
    conf = create_balance_confirmation(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
        emails=["auth@client.com"],
        created_by_user_id="user-admin",
    )

    # Extract the token and code before committing!
    inv = [i for i in database.session.new if isinstance(i, BalanceConfirmationInvitation)][0]
    raw_token = inv._raw_token
    raw_code = inv._raw_code

    database.session.commit()

    client = app_ctx.test_client()

    # Access public link (must render verification screen since not verified yet)
    res_view = client.get(f"/confirm-balance/{raw_token}")
    assert res_view.status_code == 200
    assert "Verificación" in res_view.get_data(as_text=True)

    # Post verification with incorrect code
    res_verify_fail = client.post(
        f"/confirm-balance/{raw_token}/verify",
        data={"first_name": "John", "last_name": "Doe", "email": "auth@client.com", "code": "999999", "authorized": "on"},
    )
    assert res_verify_fail.status_code == 302
    assert inv.failed_attempts == 1

    # Post verification with correct code
    res_verify_success = client.post(
        f"/confirm-balance/{raw_token}/verify",
        data={"first_name": "John", "last_name": "Doe", "email": "auth@client.com", "code": raw_code, "authorized": "on"},
    )
    assert res_verify_success.status_code == 302
    assert inv.failed_attempts == 0
    assert inv.status == "viewed"

    # Access public link again (must now show items since verified)
    res_items = client.get(f"/confirm-balance/{raw_token}")
    assert res_items.status_code == 200
    assert "FV-00123" in res_items.get_data(as_text=True)
    assert "NC-00012" not in res_items.get_data(as_text=True)

    # Submit positive confirmation
    res_respond = client.post(
        f"/confirm-balance/{raw_token}/respond",
        data={"response_type": "confirmed", "response_comment": "Todo concilia perfectamente"},
    )
    assert res_respond.status_code == 200
    assert "¡Respuesta Recibida con Éxito!" in res_respond.get_data(as_text=True)

    # Verify DB state has changed and is closed/immutable
    assert conf.status == "confirmed"
    assert conf.response_type == "confirmed"
    assert conf.response_comment == "Todo concilia perfectamente"
    assert conf.respondent_first_name == "John"
    assert conf.respondent_last_name == "Doe"
    assert conf.respondent_email == "auth@client.com"

    # Assert AuditTrail records the final response
    audit_events = database.session.execute(select(AuditTrail.action).where(AuditTrail.document_id == conf.id)).scalars().all()
    assert "balance_confirmation_confirmed" in audit_events


def test_expired_confirmation_rejects_public_verify_and_respond(app_ctx) -> None:
    """Expired confirmations must reject POST verify and respond, not only the GET view."""
    cutoff = date(2026, 5, 31)
    conf = create_balance_confirmation(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
        emails=["expired@client.com"],
        created_by_user_id="user-admin",
    )
    inv = [i for i in database.session.new if isinstance(i, BalanceConfirmationInvitation)][0]
    raw_token = inv._raw_token
    raw_code = inv._raw_code

    conf.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    database.session.commit()

    client = app_ctx.test_client()

    # POST verify on an expired confirmation must be rejected
    res_verify = client.post(
        f"/confirm-balance/{raw_token}/verify",
        data={"first_name": "Jane", "last_name": "Roe", "email": "expired@client.com", "code": raw_code, "authorized": "on"},
    )
    assert res_verify.status_code == 302
    assert conf.status == "expired"
    assert inv.status == "expired"
    assert inv.failed_attempts == 0

    # Expiry must be recorded in the audit trail
    audit_events = database.session.execute(select(AuditTrail.action).where(AuditTrail.document_id == conf.id)).scalars().all()
    assert "balance_confirmation_expired" in audit_events

    # POST respond on an expired confirmation must be rejected
    with client.session_transaction() as session:
        session[f"verified_confirmation_{conf.id}"] = inv.id
    res_respond = client.post(
        f"/confirm-balance/{raw_token}/respond",
        data={"response_type": "confirmed", "response_comment_optional": "todo en orden"},
    )
    assert res_respond.status_code == 302
    assert conf.status == "expired"
    assert conf.response_type is None

    # GET shows the expired status page
    res_view = client.get(f"/confirm-balance/{raw_token}")
    assert res_view.status_code == 200
    assert "ha expirado y ya no se permiten respuestas" in res_view.get_data(as_text=True)


def test_invitation_emails_are_unique_per_confirmation(app_ctx) -> None:
    """The unique constraint rejects duplicate emails for the same confirmation."""
    cutoff = date(2026, 5, 31)
    conf = create_balance_confirmation(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
        emails=["dup@client.com"],
        created_by_user_id="user-admin",
    )
    database.session.commit()

    duplicate = BalanceConfirmationInvitation(
        balance_confirmation_id=conf.id,
        email="dup@client.com",
        token_hash="a" * 64,
        verification_code_hash="b" * 64,
        status="pending",
    )
    database.session.add(duplicate)
    with pytest.raises(IntegrityError):
        database.session.commit()
    database.session.rollback()


def test_create_confirmation_rejects_party_not_active_in_company(app_ctx) -> None:
    """The party must be active in the company to receive a confirmation."""
    cutoff = date(2026, 5, 31)
    with pytest.raises(ValueError, match="no está activo"):
        create_balance_confirmation(
            company_id="cacao",
            party_id="cust-2",
            party_type="customer",
            cutoff_date=cutoff,
            emails=["inactive@client.com"],
            created_by_user_id="user-admin",
        )
    database.session.rollback()


def test_create_confirmation_rejects_wrong_party_type(app_ctx) -> None:
    """The party_type must match the party classification and be allowed."""
    cutoff = date(2026, 5, 31)
    with pytest.raises(ValueError, match="no está clasificado"):
        create_balance_confirmation(
            company_id="cacao",
            party_id="cust-1",
            party_type="supplier",
            cutoff_date=cutoff,
            emails=["wrong-type@client.com"],
            created_by_user_id="user-admin",
        )
    database.session.rollback()

    with pytest.raises(ValueError, match="Tipo de tercero no válido"):
        create_balance_confirmation(
            company_id="cacao",
            party_id="cust-1",
            party_type="vendor",
            cutoff_date=cutoff,
            emails=["bad-type@client.com"],
            created_by_user_id="user-admin",
        )
    database.session.rollback()


def test_snapshot_tampering_is_detected_on_view_and_respond(app_ctx) -> None:
    """The immutable snapshot hash is verified before showing or responding."""
    cutoff = date(2026, 5, 31)
    conf = create_balance_confirmation(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
        emails=["tamper@client.com"],
        created_by_user_id="user-admin",
    )
    inv = [i for i in database.session.new if isinstance(i, BalanceConfirmationInvitation)][0]
    raw_token = inv._raw_token

    # Tamper with the stored snapshot without recomputing the hash
    snapshot = json.loads(conf.snapshot_json)
    snapshot["party_name"] = "Cliente Manipulado"
    conf.snapshot_json = json.dumps(snapshot, ensure_ascii=False)
    database.session.commit()

    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session[f"verified_confirmation_{conf.id}"] = inv.id
        session[f"verified_confirmation_name_{conf.id}"] = ("Eve", "Tamper")

    # View must refuse to render the tampered items
    res_view = client.get(f"/confirm-balance/{raw_token}")
    assert res_view.status_code == 200
    assert "verificación de integridad" in res_view.get_data(as_text=True)

    # Respond must be rejected as well
    res_respond = client.post(
        f"/confirm-balance/{raw_token}/respond",
        data={"response_type": "confirmed", "response_comment": "todo en orden"},
    )
    assert res_respond.status_code == 302
    assert conf.response_type is None


def test_second_response_is_rejected_after_first_response(app_ctx) -> None:
    """Only the first valid response is registered."""
    cutoff = date(2026, 5, 31)
    conf = create_balance_confirmation(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
        emails=["first@client.com", "second@client.com"],
        created_by_user_id="user-admin",
    )
    invitations = [i for i in database.session.new if isinstance(i, BalanceConfirmationInvitation)]
    inv1 = next(i for i in invitations if i.email == "first@client.com")
    inv2 = next(i for i in invitations if i.email == "second@client.com")
    token_1, code_1 = inv1._raw_token, inv1._raw_code
    token_2 = inv2._raw_token
    database.session.commit()

    client = app_ctx.test_client()

    client.post(
        f"/confirm-balance/{token_1}/verify",
        data={"first_name": "Alice", "last_name": "Uno", "email": "first@client.com", "code": code_1, "authorized": "on"},
    )
    res_1 = client.post(
        f"/confirm-balance/{token_1}/respond",
        data={"response_type": "confirmed", "response_comment": "Todo concilia correctamente"},
    )
    assert res_1.status_code == 200
    assert conf.status == "confirmed"

    # The second invitation must not be able to respond anymore
    with client.session_transaction() as session:
        session[f"verified_confirmation_{conf.id}"] = inv2.id
        session[f"verified_confirmation_name_{conf.id}"] = ("Bob", "Dos")
    res_2 = client.post(
        f"/confirm-balance/{token_2}/respond",
        data={"response_type": "disputed", "response_comment": "Hay diferencias sin explicar en la factura"},
    )
    assert res_2.status_code == 302
    assert conf.status == "confirmed"
    assert conf.response_type == "confirmed"

    audit_actions = (
        database.session.execute(select(AuditTrail.action).where(AuditTrail.document_id == conf.id)).scalars().all()
    )
    assert audit_actions.count("balance_confirmation_confirmed") == 1


def test_atomic_status_update_prevents_double_response(app_ctx) -> None:
    """The conditional UPDATE only wins for the first concurrent responder."""
    cutoff = date(2026, 5, 31)
    conf = create_balance_confirmation(
        company_id="cacao",
        party_id="cust-1",
        party_type="customer",
        cutoff_date=cutoff,
        emails=["race@client.com"],
        created_by_user_id="user-admin",
    )
    database.session.commit()

    # Simulate the first concurrent responder
    first = database.session.execute(
        update(BalanceConfirmation)
        .where(BalanceConfirmation.id == conf.id, BalanceConfirmation.status.in_(("draft", "sent", "viewed")))
        .values(status="confirmed", response_type="confirmed", responded_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    assert first.rowcount == 1

    # Simulate a second responder arriving at the same time
    second = database.session.execute(
        update(BalanceConfirmation)
        .where(BalanceConfirmation.id == conf.id, BalanceConfirmation.status.in_(("draft", "sent", "viewed")))
        .values(status="disputed", response_type="disputed", responded_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    assert second.rowcount == 0
    database.session.rollback()
