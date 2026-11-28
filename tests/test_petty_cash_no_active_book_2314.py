# SPDX-License-Identifier: Apache-2.0
"""#2314: vistas de caja chica responden controladamente sin libro activo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import Accounts, Book, Modules, PettyCashAccount, PettyCashReconciliation, database


@pytest.fixture
def cash_module(app):
    """Activa el módulo de caja y restaura su estado original al finalizar."""
    with app.app_context():
        row = database.session.execute(select(Modules).filter_by(module="cash")).scalar_one_or_none()
        if row is None:
            database.session.add(Modules(module="cash", default=False, enabled=True))
            database.session.commit()
            creado = True
            anterior = None
        else:
            creado = False
            anterior = bool(row.enabled)
            row.enabled = True
            database.session.commit()
    yield app
    with app.app_context():
        row = database.session.execute(select(Modules).filter_by(module="cash")).scalar_one_or_none()
        if row is not None:
            if creado:
                database.session.delete(row)
            else:
                row.enabled = anterior
            database.session.commit()


@pytest.fixture
def isolated_no_active_book(app, cash_module):
    """Desactiva libros activos de cacao y restaura estado al finalizar."""
    del cash_module
    created: dict[str, list[str]] = {"funds": [], "accounts": [], "recs": []}
    with app.app_context():
        books = database.session.execute(select(Book).filter_by(entity="cacao")).scalars().all()
        snapshot = [(book.id, book.status) for book in books]
        for book in books:
            if book.status == "activo":
                book.status = "suspendido"
        database.session.commit()
    try:
        yield created
    finally:
        with app.app_context():
            for rec_id in created["recs"]:
                rec = database.session.get(PettyCashReconciliation, rec_id)
                if rec is not None:
                    database.session.delete(rec)
            for fund_id in created["funds"]:
                fund = database.session.get(PettyCashAccount, fund_id)
                if fund is not None:
                    database.session.delete(fund)
            database.session.commit()
            for account_id in created["accounts"]:
                account = database.session.get(Accounts, account_id)
                if account is not None:
                    database.session.delete(account)
            for book_id, status in snapshot:
                book = database.session.get(Book, book_id)
                if book is not None:
                    book.status = status
            database.session.commit()


def _create_fund(created: dict[str, list[str]], *, company: str = "cacao") -> PettyCashAccount:
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
    created["accounts"].append(account.id)
    created["funds"].append(fund.id)
    return fund


def test_lista_caja_chica_sin_libro_activo_no_falla(app, authenticated_client, isolated_no_active_book):
    client = authenticated_client("admin")
    with app.app_context():
        _create_fund(isolated_no_active_book)

    resp = client.get("/cash_management/petty-cash/list")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Cajas Chicas" in body or "Caja" in body
    assert "Internal Server Error" not in body


def test_detalle_caja_chica_sin_libro_activo_no_falla(app, authenticated_client, isolated_no_active_book):
    client = authenticated_client("admin")
    with app.app_context():
        fund = _create_fund(isolated_no_active_book)
        fund_id = fund.id

    resp = client.get(f"/cash_management/petty-cash/{fund_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Saldo contable" in body
    assert "Internal Server Error" not in body


def test_crear_conciliacion_sin_libro_activo_rechaza_controlado(app, authenticated_client, isolated_no_active_book):
    client = authenticated_client("admin")
    with app.app_context():
        fund = _create_fund(isolated_no_active_book)
        fund_id = fund.id
        company = fund.company

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
        count = database.session.execute(select(PettyCashReconciliation).filter_by(petty_cash_id=fund_id)).scalars().all()
        assert count == []


def test_editar_conciliacion_sin_libro_activo_rechaza_controlado(app, authenticated_client, isolated_no_active_book):
    client = authenticated_client("admin")
    with app.app_context():
        fund = _create_fund(isolated_no_active_book)
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
        isolated_no_active_book["recs"].append(rec.id)
        rec_id = rec.id

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
        saved = database.session.get(PettyCashReconciliation, rec_id)
        assert saved is not None
        assert Decimal(str(saved.counted_cash)) == Decimal("100.00")


def test_cash_module_restaura_modulo_previamente_deshabilitado(app, request):
    """El fixture no deja el módulo de caja activo en la base compartida."""
    with app.app_context():
        row = database.session.execute(select(Modules).filter_by(module="cash")).scalar_one()
        original = bool(row.enabled)
        row.enabled = False
        database.session.commit()

    def _verificar_restauracion() -> None:
        with app.app_context():
            row = database.session.execute(select(Modules).filter_by(module="cash")).scalar_one()
            assert bool(row.enabled) is False, "El fixture debe restaurar el valor previo"
            row.enabled = original
            database.session.commit()

    # El finalizador agregado antes corre después del teardown del fixture.
    request.addfinalizer(_verificar_restauracion)
    request.getfixturevalue("cash_module")
    with app.app_context():
        row = database.session.execute(select(Modules).filter_by(module="cash")).scalar_one()
        assert bool(row.enabled) is True
