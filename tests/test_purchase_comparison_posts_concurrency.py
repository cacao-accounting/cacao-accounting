# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2293: POST reales de cierre y adjudicación del comparativo."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseNegotiationRound,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

pytestmark = pytest.mark.database


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'comparison-posts.sqlite'}"
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
            "SECRET_KEY": "test-2293-posts",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str) -> tuple[str, str, str, str]:
    company = f"P{suffix}"
    user_id = f"u-{suffix}"
    with app.app_context():
        database.create_all()
        for module in ("purchases", "admin"):
            if database.session.execute(database.select(Modules).filter_by(module=module)).scalar_one_or_none() is None:
                database.session.add(Modules(module=module, default=False, enabled=True))
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
                UOM(code=f"U{suffix}", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        supplier = Party(code=f"PRV{suffix}", name="Proveedor", is_supplier=True, is_active=True)
        item = Item(code=f"IT{suffix}", name="Artículo", item_type="service", is_stock_item=False, default_uom=f"U{suffix}")
        user = User(
            id=user_id,
            user=f"user_{suffix}",
            name="Admin",
            password=b"x",
            classification="admin",
            active=True,
            company=company,
        )
        database.session.add_all([supplier, item, user])
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=user_id, company_code=company))
        rfq = PurchaseQuotation(company=company, posting_date=date(2026, 5, 15), docstatus=1, document_no=f"RFQ-{suffix}")
        database.session.add(rfq)
        database.session.flush()
        rfq_item = PurchaseQuotationItem(
            purchase_quotation_id=rfq.id,
            item_code=item.code,
            qty=Decimal("1"),
            uom=f"U{suffix}",
            qty_in_base_uom=Decimal("1"),
        )
        database.session.add(rfq_item)
        database.session.flush()
        quotation = SupplierQuotation(
            company=company,
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SQ-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_quotation_id=rfq.id,
            transaction_currency=f"C{suffix}",
        )
        database.session.add(quotation)
        database.session.flush()
        database.session.add(
            SupplierQuotationItem(
                supplier_quotation_id=quotation.id,
                item_code=item.code,
                qty=Decimal("1"),
                uom=f"U{suffix}",
                qty_in_base_uom=Decimal("1"),
                rate=Decimal("10"),
            )
        )
        database.session.commit()
        result = (str(rfq.id), str(rfq_item.id), str(quotation.id), user_id)
        database.session.remove()
        return result


def _client(app, user_id: str):
    client = app.test_client()
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def test_posts_reales_cierre_y_adjudicacion(tmp_path):
    """Los POST reales dejan un comparativo y ninguna ronda parcial."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6].upper()
    rfq_id, item_id, quotation_id, user_id = _seed(app, suffix)
    barrier = Barrier(2, timeout=30)

    def close() -> int:
        client = _client(app, user_id)
        barrier.wait(timeout=10)
        return client.post(
            f"/buying/request-for-quotation/{rfq_id}/close",
            data={"authorization_reason": "Cierre concurrente de prueba"},
        ).status_code

    def award() -> int:
        client = _client(app, user_id)
        barrier.wait(timeout=10)
        return client.post(
            f"/buying/request-for-quotation/{rfq_id}/award",
            data={
                f"award_item_{item_id}": quotation_id,
                "authorization_reason": "Adjudicación concurrente de prueba",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(lambda fn: fn(), (close, award)))
    assert statuses == [302, 302], statuses

    with app.app_context():
        awards = (
            database.session.execute(database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq_id))
            .scalars()
            .all()
        )
        assert len(awards) == 1
        award = awards[0]
        lines = (
            database.session.execute(database.select(PurchaseQuotationAwardItem).filter_by(award_id=award.id)).scalars().all()
        )
        if award.status == "closed":
            assert lines == []
        else:
            assert len(lines) == 1
            assert lines[0].purchase_quotation_item_id == item_id
        rounds = (
            database.session.execute(database.select(PurchaseNegotiationRound).filter_by(purchase_quotation_id=rfq_id))
            .scalars()
            .all()
        )
        assert all(round_record.status == "closed" for round_record in rounds)
        database.session.remove()
