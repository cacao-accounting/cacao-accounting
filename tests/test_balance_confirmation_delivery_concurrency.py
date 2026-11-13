# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""PostgreSQL locking regression for balance confirmation delivery."""

from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.balance_confirmation_bp import (
    _active_invitation_exists,
    _claim_confirmation_delivery,
)
from cacao_accounting.database import BalanceConfirmation, BalanceConfirmationInvitation, Currency, Entity, Party, database


@pytest.mark.database
def test_respuesta_publica_espera_al_reenvio_smtp_y_rechaza_token_rotado():
    """A resend serializes responses/retries and rechecks expiry after lock waits."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL concurrency regression")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_url,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        if database.engine.dialect.name != "postgresql":
            pytest.skip("This regression verifies PostgreSQL row-lock behavior")
        database.create_all()

        suffix = uuid4().hex[:8]
        company_code = f"T{suffix}"
        if database.session.get(Currency, "NIO") is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            database.session.flush()
        company = Entity(
            code=company_code,
            name=f"Empresa {suffix}",
            company_name=f"Empresa {suffix}",
            tax_id=f"TAX-{suffix}",
            currency="NIO",
            enabled=True,
            status="default",
        )
        party = Party(code=f"CLI-{suffix}", name="Cliente", is_customer=True)
        database.session.add_all([company, party])
        database.session.flush()

        old_token = f"token-{suffix}"
        old_hash = hashlib.sha256(old_token.encode("utf-8")).hexdigest()
        confirmation = BalanceConfirmation(
            company=company_code,
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 10, 31),
            status="sent",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        database.session.add(confirmation)
        database.session.flush()
        invitation = BalanceConfirmationInvitation(
            balance_confirmation_id=confirmation.id,
            email=f"client-{suffix}@example.test",
            token_hash=old_hash,
            verification_code_hash=hashlib.sha256(b"123456").hexdigest(),
            status="viewed",
        )
        database.session.add(invitation)
        deadline_confirmation = BalanceConfirmation(
            company=company_code,
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 10, 31),
            status="sent",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=2),
        )
        database.session.add(deadline_confirmation)
        database.session.commit()
        confirmation_id = confirmation.id
        invitation_id = invitation.id
        party_id = party.id
        deadline_confirmation_id = deadline_confirmation.id
        deadline_at = deadline_confirmation.expires_at

    delivery_claimed = Event()
    smtp_release = Event()
    response_attempting = Event()
    response_finished = Event()
    second_claim_attempting = Event()
    second_claim_finished = Event()
    deadline_lock_acquired = Event()
    deadline_lock_release = Event()
    deadline_claim_attempting = Event()
    deadline_claim_finished = Event()
    response_accepted: list[bool] = []
    second_claim_result: list[bool] = []
    deadline_claim_result: list[bool] = []
    new_hash = hashlib.sha256(f"new-token-{suffix}".encode("utf-8")).hexdigest()

    def resend_while_smtp_is_paused() -> None:
        """Hold the confirmation row while the transport is in flight."""
        with app.app_context():
            current = database.session.get(BalanceConfirmation, confirmation_id)
            assert current is not None
            assert _claim_confirmation_delivery(current, ("sent", "viewed"))
            delivery_claimed.set()
            assert smtp_release.wait(timeout=10)

            current_invitation = database.session.get(BalanceConfirmationInvitation, invitation_id)
            assert current_invitation is not None
            current_invitation.token_hash = new_hash
            current_invitation.verification_code_hash = hashlib.sha256(b"654321").hexdigest()
            current_invitation.status = "pending"
            current.status = "sent"
            current.sent_at = datetime.now(timezone.utc)
            database.session.commit()
            database.session.remove()

    def public_response_loaded_before_resend_finishes() -> None:
        """Model a response that loaded its old invitation before the lock."""
        with app.app_context():
            stale_invitation = database.session.execute(
                select(BalanceConfirmationInvitation).where(BalanceConfirmationInvitation.token_hash == old_hash)
            ).scalar_one()
            response_attempting.set()
            locked_confirmation = database.session.execute(
                select(BalanceConfirmation).where(BalanceConfirmation.id == confirmation_id).with_for_update()
            ).scalar_one()
            database.session.refresh(stale_invitation)
            valid = stale_invitation.token_hash == old_hash and stale_invitation.status in ("pending", "viewed")
            if valid:
                result = database.session.execute(
                    update(BalanceConfirmation)
                    .where(
                        BalanceConfirmation.id == locked_confirmation.id,
                        BalanceConfirmation.status.in_(("draft", "sent", "viewed")),
                        _active_invitation_exists(confirmation_id, invitation_id, old_hash),
                    )
                    .values(status="confirmed")
                )
                response_accepted.append(getattr(result, "rowcount", 0) == 1)
            else:
                response_accepted.append(False)
            database.session.commit()
            database.session.remove()
            response_finished.set()

    def concurrent_resend_claim() -> None:
        """A duplicate request with the old row version must lose after SMTP."""
        with app.app_context():
            stale_confirmation = database.session.get(BalanceConfirmation, confirmation_id)
            assert stale_confirmation is not None
            second_claim_attempting.set()
            claimed = _claim_confirmation_delivery(stale_confirmation, ("sent", "viewed"))
            second_claim_result.append(claimed)
            database.session.rollback()
            database.session.remove()
            second_claim_finished.set()

    def hold_deadline_row_lock() -> None:
        """Hold a row without changing its version while its deadline passes."""
        with app.app_context():
            database.session.execute(
                select(BalanceConfirmation).where(BalanceConfirmation.id == deadline_confirmation_id).with_for_update()
            ).scalar_one()
            deadline_lock_acquired.set()
            assert deadline_lock_release.wait(timeout=10)
            database.session.commit()
            database.session.remove()

    def claim_after_deadline_lock_wait() -> None:
        """Re-evaluate the deadline only after the blocking lock is acquired."""
        with app.app_context():
            current = database.session.get(BalanceConfirmation, deadline_confirmation_id)
            assert current is not None
            deadline_claim_attempting.set()
            deadline_claim_result.append(_claim_confirmation_delivery(current, ("sent", "viewed")))
            database.session.rollback()
            database.session.remove()
            deadline_claim_finished.set()

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            resend_future = executor.submit(resend_while_smtp_is_paused)
            assert delivery_claimed.wait(timeout=5)
            response_future = executor.submit(public_response_loaded_before_resend_finishes)
            assert response_attempting.wait(timeout=5)
            assert not response_finished.wait(timeout=0.2)
            second_claim_future = executor.submit(concurrent_resend_claim)
            assert second_claim_attempting.wait(timeout=5)
            assert not second_claim_finished.wait(timeout=0.2)
            smtp_release.set()
            resend_future.result(timeout=10)
            response_future.result(timeout=10)
            second_claim_future.result(timeout=10)

        assert response_accepted == [False]
        assert second_claim_result == [False]

        with ThreadPoolExecutor(max_workers=2) as executor:
            lock_future = executor.submit(hold_deadline_row_lock)
            assert deadline_lock_acquired.wait(timeout=5)
            claim_future = executor.submit(claim_after_deadline_lock_wait)
            assert deadline_claim_attempting.wait(timeout=5)
            assert not deadline_claim_finished.wait(timeout=0.2)
            remaining = (deadline_at - datetime.now(timezone.utc)).total_seconds()
            if remaining > 0:
                time.sleep(remaining + 0.1)
            deadline_lock_release.set()
            lock_future.result(timeout=10)
            claim_future.result(timeout=10)
        assert deadline_claim_result == [False]

        with app.app_context():
            confirmation = database.session.get(BalanceConfirmation, confirmation_id)
            invitation = database.session.get(BalanceConfirmationInvitation, invitation_id)
            deadline_confirmation = database.session.get(BalanceConfirmation, deadline_confirmation_id)
            assert confirmation is not None and confirmation.status == "sent"
            assert confirmation.response_type is None
            assert invitation is not None and invitation.token_hash == new_hash
            assert invitation.status == "pending"

            database.session.delete(confirmation)
            assert deadline_confirmation is not None
            database.session.delete(deadline_confirmation)
            database.session.commit()
            party = database.session.get(Party, party_id)
            if party is not None:
                database.session.delete(party)
            company = database.session.execute(select(Entity).where(Entity.code == company_code)).scalar_one()
            database.session.delete(company)
            database.session.commit()
    finally:
        smtp_release.set()
        deadline_lock_release.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
