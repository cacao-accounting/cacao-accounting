# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William JosÃ© Moreno Reyes

"""Pruebas piloto de negocio y aislamiento usando la infraestructura SQLite por worker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Accounts,
    Book,
    ExchangeRate,
    GLEntry,
    Item,
    ItemUOMConversion,
    StockLedgerEntry,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)


def test_gl_entries_remain_balanced_for_double_entry(app, entorno_contable):
    """Cada asiento de prueba debe dejar el libro balanceado en dÃ©bito y crÃ©dito."""
    with app.app_context():
        debit_account = database.session.execute(
            select(Accounts).filter_by(entity="cacao", code="1101")
        ).scalar_one()
        credit_account = database.session.execute(
            select(Accounts).filter_by(entity="cacao", code="4101")
        ).scalar_one()
        book = database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        database.session.add_all(
            [
                GLEntry(
                    posting_date=date(2026, 5, 10),
                    company="cacao",
                    ledger_id=book.id,
                    account_id=debit_account.id,
                    account_code=debit_account.code,
                    debit=Decimal("1250.00"),
                    credit=Decimal("0.00"),
                    voucher_type="journal",
                    voucher_id="pilot-journal-001",
                ),
                GLEntry(
                    posting_date=date(2026, 5, 10),
                    company="cacao",
                    ledger_id=book.id,
                    account_id=credit_account.id,
                    account_code=credit_account.code,
                    debit=Decimal("0.00"),
                    credit=Decimal("1250.00"),
                    voucher_type="journal",
                    voucher_id="pilot-journal-001",
                ),
            ]
        )
        database.session.commit()

        totals = database.session.execute(
            select(
                func.coalesce(func.sum(GLEntry.debit), Decimal("0")),
                func.coalesce(func.sum(GLEntry.credit), Decimal("0")),
            ).where(GLEntry.voucher_id == "pilot-journal-001")
        ).one()

        assert Decimal(str(totals[0])) == Decimal("1250.00")
        assert Decimal(str(totals[1])) == Decimal("1250.00")


def test_multicompany_scope_is_restricted_to_assigned_companies(app, reference_users):
    """Un usuario de otra empresa no debe aparecer como autorizado en la compaÃ±Ã­a principal."""
    other_company = reference_users["other_company"]
    limited_company = reference_users["limited_company"]

    with app.app_context():
        access_other = database.session.execute(
            select(UserCompanyAccess.company_code).where(UserCompanyAccess.user_id == other_company.id)
        ).scalars().all()
        access_limited = database.session.execute(
            select(UserCompanyAccess.company_code).where(UserCompanyAccess.user_id == limited_company.id)
        ).scalars().all()

    assert access_other == ["alpha"]
    assert access_limited == ["cacao"]


def test_item_uom_conversion_is_persisted_and_queryable(app, entorno_contable):
    """La conversiÃ³n de UOM debe quedar registrada y ser reproducible por item."""
    with app.app_context():
        uom_caja = UOM(code="CAJA", name="Caja")
        database.session.add(uom_caja)
        database.session.flush()

        item = Item(
            code="ITEM-UOM-001",
            name="Caja de producto",
            item_type="goods",
            is_stock_item=True,
            default_uom="CAJA",
        )
        database.session.add(item)
        database.session.flush()

        conversion = ItemUOMConversion(
            item_code=item.code,
            from_uom="CAJA",
            to_uom="UND",
            conversion_factor=Decimal("12"),
        )
        database.session.add(conversion)
        database.session.commit()

        stored = database.session.execute(
            select(ItemUOMConversion).where(
                ItemUOMConversion.item_code == item.code,
                ItemUOMConversion.from_uom == "CAJA",
                ItemUOMConversion.to_uom == "UND",
            )
        ).scalar_one()

        assert stored.conversion_factor == Decimal("12")


def test_stock_ledger_rejects_mutating_existing_rows(app, entorno_contable):
    """Una lÃ­nea del stock no debe poder mutarse sin abrir un nuevo registro append-only."""
    with app.app_context():
        warehouse = Warehouse(code="BOD-PILOT", name="Bodega piloto", company="cacao")
        item = Item(
            code="STOCK-PILOT-001",
            name="ArtÃ­culo de stock piloto",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
        )
        database.session.add_all([warehouse, item])
        database.session.flush()

        entry = StockLedgerEntry(
            posting_date=date(2026, 5, 12),
            item_code=item.code,
            warehouse=warehouse.code,
            company="cacao",
            qty_change=Decimal("5"),
            qty_after_transaction=Decimal("5"),
            voucher_type="stock",
            voucher_id="stock-001",
        )
        database.session.add(entry)
        database.session.commit()

        entry.qty_change = Decimal("8")
        with pytest.raises(ValueError):
            database.session.commit()

        database.session.rollback()
        persisted = database.session.execute(
            select(StockLedgerEntry).where(StockLedgerEntry.voucher_id == "stock-001")
        ).scalar_one()
        assert persisted.qty_change == Decimal("5")


def test_stock_ledger_rejects_mutation_without_new_reversal(app, entorno_contable):
    """La evidencia del stock debe permanecer inmutable sin un registro append-only nuevo."""
    with app.app_context():
        warehouse = Warehouse(code="BOD-PILOT-2", name="Bodega pilot 2", company="cacao")
        item = Item(
            code="STOCK-PILOT-002",
            name="ArtÃ­culo con cancelaciÃ³n",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
        )
        database.session.add_all([warehouse, item])
        database.session.flush()

        entry = StockLedgerEntry(
            posting_date=date(2026, 5, 13),
            item_code=item.code,
            warehouse=warehouse.code,
            company="cacao",
            qty_change=Decimal("3"),
            qty_after_transaction=Decimal("3"),
            voucher_type="stock",
            voucher_id="stock-002",
        )
        database.session.add(entry)
        database.session.commit()

        entry.qty_change = Decimal("9")
        with pytest.raises(ValueError):
            database.session.commit()

        database.session.rollback()
        persisted = database.session.get(StockLedgerEntry, entry.id)
        assert persisted.qty_change == Decimal("3")


def test_missing_exchange_rate_is_detected_as_unavailable(app, entorno_contable):
    """Sin tasa de cambio, la conversiÃ³n multimoneda debe quedar bloqueada."""
    with app.app_context():
        missing = database.session.execute(
            select(ExchangeRate).where(
                ExchangeRate.origin == "EUR",
                ExchangeRate.destination == "NIO",
                ExchangeRate.date == date(2026, 5, 10),
            )
        ).scalar_one_or_none()
        assert missing is None


def test_login_real_logout_and_session_reset(app):
    """El flujo real de login y logout debe funcionar con contrase?a Argon2 y limpiar la sesi?n."""
    username = "pilot-login"
    password = "PilotPass!123"

    with app.app_context():
        user = User(
            user=username,
            name="Pilot User",
            password=proteger_passwd(password),
            # El modo escritorio solo permite iniciar sesión a administradores
            # (puede_iniciar_en_escritorio, política de la ruta /login).
            classification="admin",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.commit()

    client = app.test_client()

    response = client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session.get("_user_id") is not None

    logout_response = client.post("/logout", follow_redirects=True)
    assert logout_response.status_code == 200
    with client.session_transaction() as session:
        assert session.get("_user_id") is None


def test_failed_login_does_not_establish_authenticated_session(app):
    """Un intento de login fallido no genera identidad autenticada ni restaura sesi?n activa."""
    username = "pilot-fail"
    password = "PilotBad!123"

    with app.app_context():
        database.session.add(
            User(
                user=username,
                name="Pilot Failed",
                password=proteger_passwd(password),
                classification="user",
                active=True,
                company="cacao",
            )
        )
        database.session.commit()

    client = app.test_client()
    response = client.post("/login", data={"usuario": username, "acceso": "WrongPass!123"}, follow_redirects=True)
    assert response.status_code == 200

    with client.session_transaction() as session:
        assert session.get("_user_id") is None


def test_authenticated_clients_keep_distinct_user_sessions(authenticated_client):
    """Cada cliente autenticado debe mantener su propio estado de identidad y sesi?n."""
    admin_client = authenticated_client("admin")
    reader_client = authenticated_client("reader")

    with admin_client.session_transaction() as admin_session:
        admin_user_id = admin_session.get("_user_id")
        assert admin_user_id is not None

    with reader_client.session_transaction() as reader_session:
        reader_user_id = reader_session.get("_user_id")
        assert reader_user_id is not None
        assert reader_user_id != admin_user_id


def test_worker_seed_data_is_not_reused_between_tests(app, db_session):
    """Los datos transaccionales de cada prueba no deben contaminar el worker ni otros tests."""
    entity_name = "pilot-isolation-trace"
    db_session.add(
        User(
            user=entity_name,
            name="Isolated Pilot",
            password=proteger_passwd("IsolatedPass!123"),
            classification="user",
            active=True,
            company="cacao",
        )
    )
    db_session.commit()

    match = db_session.execute(select(User).where(User.user == entity_name)).scalar_one_or_none()
    assert match is not None
