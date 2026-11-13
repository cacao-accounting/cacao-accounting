# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Atomicidad del gasto y estado de reposición de caja chica.

Escenario de negocio:
- #2030: la reversa GL se confirmaba antes del subledger.
- #2032: el centro de costo obligatorio no se anunciaba al control.
- #2033: al recargar la reposición se perdían compañía y fondo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.bancos.services import cancel_petty_cash_expense
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    ComprobanteContable,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashVoucher,
    User,
    database,
)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Book(code="LIBRO", name="Libro principal", entity="cacao", currency="NIO", status="activo"),
            ]
        )
        database.session.flush()
        cuenta = Accounts(
            code="CTA-CAJA",
            name="Caja principal",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(cuenta)
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name="Caja principal",
            currency="NIO",
            float_amount=Decimal("100"),
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        voucher = PettyCashVoucher(
            company="cacao",
            petty_cash_id=fondo.id,
            voucher_no="V-1",
            voucher_status="liquidado",
            delivered_to="Ana",
            concept="Compra",
            amount=Decimal("10"),
        )
        journal = ComprobanteContable(
            document_no="J-1",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add_all([voucher, journal])
        database.session.flush()
        expense = PettyCashExpense(
            company="cacao",
            petty_cash_id=fondo.id,
            voucher_id=voucher.id,
            concept="Compra",
            expense_account_code="5201",
            amount=Decimal("10"),
            cost_center_code="CC-1",
            posting_date=date(2026, 11, 5),
            journal_id=journal.id,
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add(expense)
        database.session.flush()
        voucher.expense_id = expense.id
        database.session.commit()
        ids = {"fund": fondo.id, "expense": expense.id, "journal": journal.id, "voucher": voucher.id}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_anulacion_usa_una_sola_transaccion(monkeypatch):
    """#2030: la reversa GL no se confirma antes que el subledger."""
    import importlib

    journal_service = importlib.import_module("cacao_accounting.contabilidad.journal_service")
    application, ids = _crear_app()
    try:
        llamadas: list[bool] = []
        monkeypatch.setattr(
            journal_service,
            "cancel_submitted_journal",
            lambda *args, **kwargs: llamadas.append(kwargs.get("commit", True)),
        )
        with application.app_context():
            expense = database.session.get(PettyCashExpense, ids["expense"])
            assert expense is not None

            original_commit = database.session.commit
            monkeypatch.setattr(
                database.session,
                "commit",
                lambda: (_ for _ in ()).throw(RuntimeError("fallo de commit")),
            )
            with pytest.raises(RuntimeError):
                cancel_petty_cash_expense(expense, reason="prueba", actor_id="admin")
            database.session.rollback()
            monkeypatch.setattr(database.session, "commit", original_commit)

            assert llamadas == [False]
            expense = database.session.get(PettyCashExpense, ids["expense"])
            voucher = database.session.get(PettyCashVoucher, ids["voucher"])
            assert expense is not None and expense.docstatus == 1
            assert voucher is not None and voucher.voucher_status == "liquidado"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_centro_de_costo_anuncia_obligatoriedad():
    """#2032: el smart select de centro de costo recibe required=True."""
    template = Path("cacao_accounting/bancos/templates/bancos/caja_chica_gasto_nuevo.html").read_text(encoding="utf-8")
    bloque = template.split('doctype="cost_center"', 1)[1].split(") }}", 1)[0]
    assert "required=True" in bloque


def test_reposicion_hidrata_compania_y_fondo():
    """#2033: el GET con query params conserva la selección."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        html = client.get(f"/cash_management/petty-cash-replenishment/new?petty_cash_id={ids['fund']}&company=cacao").get_data(
            as_text=True
        )

        assert f'initialValue: "{ids["fund"]}"' in html
        assert 'initialValue: "cacao"' in html
        assert ids["fund"] in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
