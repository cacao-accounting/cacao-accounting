# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2293: cierre manual y adjudicación del comparativo se serializan."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras import purchase_sourcing_service
from cacao_accounting.compras.purchase_sourcing_service import (
    close_purchase_quotation_comparison,
    create_purchase_quotation_award,
    open_negotiation_round,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    PurchaseNegotiationRound,
    PurchaseQuotation,
    PurchaseQuotationAward,
    User,
    database,
)

pytestmark = pytest.mark.database


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'comparison-close.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2293",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str) -> tuple[str, str]:
    company = f"Q{suffix}"
    user_id = f"u-{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
                User(
                    id=user_id,
                    user=f"user_{suffix}",
                    name="Usuario",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company=company,
                ),
            ]
        )
        database.session.flush()
        rfq = PurchaseQuotation(company=company, posting_date=date(2026, 5, 15), docstatus=1, document_no=f"RFQ-{suffix}")
        database.session.add(rfq)
        database.session.commit()
        result = (str(rfq.id), user_id)
        database.session.remove()
        return result


def test_cierre_y_adjudicacion_dejan_un_solo_comparativo(tmp_path, monkeypatch):
    """Solo una de las dos transiciones puede registrar el resultado."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    rfq_id, user_id = _seed(app, suffix)
    monkeypatch.setattr(purchase_sourcing_service, "validate_award_request", lambda *_a, **_k: ([], [], set()))
    monkeypatch.setattr(purchase_sourcing_service, "is_purchase_sourcing_authorizer", lambda _user: True)
    monkeypatch.setattr(purchase_sourcing_service, "current_negotiation_round", lambda _id: None)
    barrier = Barrier(2, timeout=30)

    def close() -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                rfq = database.session.get(PurchaseQuotation, rfq_id)
                close_purchase_quotation_comparison(rfq, user_id, "Cierre concurrente")
                database.session.commit()
                return "cerrado"
            except Exception:
                database.session.rollback()
                return "rechazado"
            finally:
                database.session.remove()

    def award() -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                rfq = database.session.get(PurchaseQuotation, rfq_id)
                create_purchase_quotation_award(rfq, {}, user_id)
                database.session.commit()
                return "adjudicado"
            except Exception:
                database.session.rollback()
                return "rechazado"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda fn: fn(), (close, award)))
    assert results.count("rechazado") == 1, results
    with app.app_context():
        awards = (
            database.session.execute(database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq_id))
            .scalars()
            .all()
        )
        assert len(awards) == 1


def test_apertura_de_ronda_y_adjudicacion_serializan(tmp_path, monkeypatch):
    """Abrir ronda no puede quedar como estado abierto tras una adjudicación."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    rfq_id, user_id = _seed(app, suffix)
    monkeypatch.setattr(purchase_sourcing_service, "validate_award_request", lambda *_a, **_k: ([], [], set()))
    monkeypatch.setattr(purchase_sourcing_service, "is_purchase_sourcing_authorizer", lambda _user: True)
    barrier = Barrier(2, timeout=30)

    def open_round() -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                open_negotiation_round(rfq_id, user_id)
                database.session.commit()
                return "abierta"
            except Exception:
                database.session.rollback()
                return "rechazada"
            finally:
                database.session.remove()

    def award() -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                rfq = database.session.get(PurchaseQuotation, rfq_id)
                create_purchase_quotation_award(rfq, {}, user_id)
                database.session.commit()
                return "adjudicada"
            except Exception:
                database.session.rollback()
                return "rechazada"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda fn: fn(), (open_round, award)))
    assert "adjudicada" in results, results
    with app.app_context():
        awards = (
            database.session.execute(database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq_id))
            .scalars()
            .all()
        )
        assert len(awards) == 1
        rounds = (
            database.session.execute(database.select(PurchaseNegotiationRound).filter_by(purchase_quotation_id=rfq_id))
            .scalars()
            .all()
        )
        assert all(round_record.status == "closed" for round_record in rounds)
