# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2140: dos adjudicaciones concurrentes no crean awards duplicados."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from uuid import uuid4

from cacao_accounting import create_app
from cacao_accounting.compras import purchase_sourcing_service
from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    create_purchase_quotation_award,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    PurchaseQuotation,
    PurchaseQuotationAward,
    database,
)
from cacao_accounting.default_scope import lock_default_scope


def test_concurrent_awards_keep_one_finalized_row(tmp_path, monkeypatch):
    """La segunda adjudicación espera el lock y detecta la fila confirmada."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'award-race.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6].upper()
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=f"A{suffix}",
                    name="Compras",
                    company_name="Compras SA",
                    tax_id=f"A{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        rfq = PurchaseQuotation(
            company=f"A{suffix}",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"RFQ-{suffix}",
        )
        database.session.add(rfq)
        database.session.commit()
        rfq_id = rfq.id
        company = rfq.company
        database.session.remove()

    monkeypatch.setattr(
        purchase_sourcing_service,
        "validate_award_request",
        lambda *_args, **_kwargs: ([], [], set()),
    )
    monkeypatch.setattr(purchase_sourcing_service, "current_negotiation_round", lambda _id: None)

    inserted = Event()
    release_first = Event()

    def insert_first():
        with app.app_context():
            try:
                lock_default_scope("purchase_quotation_award", rfq_id)
                database.session.add(
                    PurchaseQuotationAward(
                        purchase_quotation_id=rfq_id,
                        company=company,
                        status="finalized",
                    )
                )
                database.session.flush()
                inserted.set()
                assert release_first.wait(timeout=10)
                database.session.commit()
            finally:
                database.session.remove()

    def award_second() -> str:
        with app.app_context():
            try:
                rfq = database.session.get(PurchaseQuotation, rfq_id)
                create_purchase_quotation_award(rfq, {}, None)
                database.session.commit()
                return "created"
            except PurchaseSourcingError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(insert_first)
            assert inserted.wait(timeout=10)
            second = workers.submit(award_second)
            finished_before_commit = False
            try:
                second.result(timeout=0.5)
                finished_before_commit = True
            except TimeoutError:
                pass
            release_first.set()
            first.result(timeout=10)
            second_outcome = second.result(timeout=10)

        assert finished_before_commit is False
        assert second_outcome == "rejected"
        with app.app_context():
            rows = (
                database.session.execute(database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq_id))
                .scalars()
                .all()
            )
            assert len(rows) == 1
    finally:
        release_first.set()
        with app.app_context():
            database.session.rollback()
            for row in database.session.execute(
                database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq_id)
            ).scalars():
                database.session.delete(row)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
