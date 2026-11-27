# SPDX-License-Identifier: Apache-2.0
"""#2314: vistas de caja chica responden controladamente sin libro activo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import Accounts, Book, Modules, PettyCashAccount, database


@pytest.fixture
def cash_module(app):
    with app.app_context():
        row = database.session.execute(select(Modules).filter_by(module="cash")).scalar_one_or_none()
        if row is None:
            database.session.add(Modules(module="cash", default=False, enabled=True))
        else:
            row.enabled = True
        database.session.commit()
    yield app


def _disable_active_books(company: str = "cacao") -> None:
    books = database.session.execute(select(Book).filter_by(entity=company, status="activo")).scalars().all()
    for book in books:
        book.status = "suspendido"
    database.session.commit()


def _create_fund(*, company: str = "cacao") -> PettyCashAccount:
    suffix = uuid4().hex[:8]
    account = Accounts(
        entity=company,
        code=f"PCNB{suffix[:5]}",
        name=f"Caja sin libro {suffix}",
        classification="asset",
        account_type="cash",
        active=True,
    )
    database.session.add(account)
    database.session.flush()
    fund = PettyCashAccount(
        company=company,
        account_id=account.id,
        name=f"Fondo sin libro {suffix}",
        currency="NIO",
        float_amount=Decimal("100.00"),
        is_active=True,
        status="activo",
    )
    database.session.add(fund)
    database.session.commit()
    return fund


def test_lista_caja_chica_sin_libro_activo_no_falla(cash_module, authenticated_client):
    app = cash_module
    client = authenticated_client("admin")
    with app.app_context():
        _create_fund()
        _disable_active_books("cacao")

    resp = client.get("/cash_management/petty-cash/list")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Cajas Chicas" in body or "Caja" in body
    assert "Internal Server Error" not in body


def test_detalle_caja_chica_sin_libro_activo_no_falla(cash_module, authenticated_client):
    app = cash_module
    client = authenticated_client("admin")
    with app.app_context():
        fund = _create_fund()
        fund_id = fund.id
        _disable_active_books("cacao")

    resp = client.get(f"/cash_management/petty-cash/{fund_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Saldo contable" in body
    assert "Internal Server Error" not in body


def test_crear_conciliacion_sin_libro_activo_rechaza_controlado(cash_module, authenticated_client):
    app = cash_module
    client = authenticated_client("admin")
    with app.app_context():
        fund = _create_fund()
        fund_id = fund.id
        company = fund.company
        _disable_active_books(company)

    resp = client.post(
        "/cash_management/petty-cash-reconciliation/new",
        data={
            "company": company,
            "petty_cash_id": fund_id,
            "reconciliation_date": date.today().isoformat(),
            "counted_cash": "100.00",
            "explanation": "prueba",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True).lower()
    assert "libro contable activo" in body or "no existe un libro" in body
    with app.app_context():
        from cacao_accounting.database import PettyCashReconciliation

        count = database.session.execute(select(PettyCashReconciliation).filter_by(petty_cash_id=fund_id)).scalars().all()
        assert count == []


def test_editar_conciliacion_sin_libro_activo_rechaza_controlado(cash_module, authenticated_client):
    app = cash_module
    client = authenticated_client("admin")
    with app.app_context():
        fund = _create_fund()
        from cacao_accounting.database import PettyCashReconciliation

        rec = PettyCashReconciliation(
            company=fund.company,
            petty_cash_id=fund.id,
            posting_date=date.today(),
            reconciliation_date=date.today(),
            ledger_balance=Decimal("100.00"),
            open_vouchers=Decimal("0"),
            expected_cash=Decimal("100.00"),
            counted_cash=Decimal("100.00"),
            explained_amount=Decimal("100.00"),
            difference=Decimal("0"),
            status="borrador",
            docstatus=0,
            transaction_currency=fund.currency,
        )
        database.session.add(rec)
        database.session.commit()
        rec_id = rec.id
        company = fund.company
        _disable_active_books(company)

    resp = client.post(
        f"/cash_management/petty-cash-reconciliation/{rec_id}/edit",
        data={
            "reconciliation_date": date.today().isoformat(),
            "counted_cash": "90.00",
            "explanation": "edit",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True).lower()
    assert "libro contable activo" in body or "no existe un libro" in body
    with app.app_context():
        from cacao_accounting.database import PettyCashReconciliation

        saved = database.session.get(PettyCashReconciliation, rec_id)
        assert saved is not None
        assert Decimal(str(saved.counted_cash)) == Decimal("100.00")
