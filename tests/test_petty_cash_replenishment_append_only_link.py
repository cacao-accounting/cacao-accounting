# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Append-only association and transaction guarantees for petty-cash replenishments."""

from datetime import date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.bancos.services import (
    _petty_cash_reconciliation_derived_values,
    cancel_petty_cash_expense,
    create_petty_cash_replenishment,
    petty_cash_expenses_available_for_replenishment,
    petty_cash_pending_replenishment_total,
    petty_cash_replenishment_expenses,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashReplenishment,
    PettyCashReplenishmentExpense,
    database,
)


@pytest.fixture
def petty_cash_link_app(tmp_path):
    """Build a disposable SQLite company for replenishment-link behavior."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'petty-cash-link.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    company = f"L{uuid4().hex[:8]}"
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code=company,
                name=f"Empresa {company}",
                company_name=f"Empresa de prueba {company}",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        account = Accounts(
            entity=company,
            code=f"PC-{company}",
            name=f"Caja chica {company}",
            classification="asset",
            account_type="petty_cash",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(account)
        database.session.flush()
        fund = PettyCashAccount(
            company=company,
            account_id=account.id,
            name=f"Fondo {company}",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fund)
        database.session.commit()
        ids = {"company": company, "fund_id": fund.id}

    yield application, ids

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _seed_posted_expense(company: str, fund_id: str) -> PettyCashExpense:
    """Create a representative posted petty-cash expense without mutating it later."""
    expense = PettyCashExpense(
        company=company,
        petty_cash_id=fund_id,
        posting_date=date(2026, 10, 19),
        amount=Decimal("85.00"),
        concept="Consumibles de caja chica",
        expense_account_code=f"EXP-{company}",
        docstatus=1,
    )
    database.session.add(expense)
    database.session.commit()
    return expense


def _create_replenishment(company: str, fund_id: str, expense_id: str, request_day: int = 20):
    """Use the production service to create the request and its reservation."""
    return create_petty_cash_replenishment(
        company=company,
        petty_cash_id=fund_id,
        expense_ids=[expense_id],
        request_date=date(2026, 10, request_day),
    )


def test_replenishment_appends_link_and_reconciles_derived_pending_balance(petty_cash_link_app):
    """Linking posted evidence leaves it intact and removes it from pending balance exactly once."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        expense_id = expense.id
        fund = database.session.get(PettyCashAccount, ids["fund_id"])
        assert fund is not None
        assert petty_cash_pending_replenishment_total(fund) == Decimal("85.00")
        assert [row.id for row in petty_cash_expenses_available_for_replenishment(fund.id)] == [expense_id]

        application.config["INTERNAL_CONTROLS_ENFORCE"] = True
        replenishment = _create_replenishment(ids["company"], fund.id, expense_id)

        persisted_expense = database.session.get(PettyCashExpense, expense_id)
        link = database.session.execute(
            database.select(PettyCashReplenishmentExpense).filter_by(petty_cash_expense_id=expense_id)
        ).scalar_one()
        assert persisted_expense is not None and persisted_expense.replenishment_id is None
        assert link.petty_cash_replenishment_id == replenishment.id
        assert [row.id for row in petty_cash_replenishment_expenses(replenishment)] == [expense_id]
        assert petty_cash_expenses_available_for_replenishment(fund.id) == []
        assert petty_cash_pending_replenishment_total(fund) == Decimal("0")

        with pytest.raises(ValueError, match="gasto reservado en una reposición"):
            cancel_petty_cash_expense(persisted_expense)
        database.session.rollback()
        with pytest.raises(ValueError, match="no estan disponibles"):
            _create_replenishment(ids["company"], fund.id, expense_id, request_day=21)
        database.session.rollback()
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishmentExpense.id)).filter_by(
                    petty_cash_expense_id=expense_id
                )
            ).scalar_one()
            == 1
        )


def test_legacy_replenishment_foreign_key_remains_readable(petty_cash_link_app):
    """Pre-existing links remain reserved and visible without rewriting legacy expense rows."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        replenishment = PettyCashReplenishment(
            company=ids["company"],
            petty_cash_id=ids["fund_id"],
            request_date=date(2026, 10, 20),
            amount=expense.amount,
            status="reembolsado",
            docstatus=1,
        )
        database.session.add(replenishment)
        database.session.flush()
        expense.replenishment_id = replenishment.id
        database.session.commit()
        application.config["INTERNAL_CONTROLS_ENFORCE"] = True

        assert petty_cash_pending_replenishment_total(database.session.get(PettyCashAccount, ids["fund_id"])) == 0
        assert petty_cash_expenses_available_for_replenishment(ids["fund_id"]) == []
        assert [row.id for row in petty_cash_replenishment_expenses(replenishment)] == [expense.id]
        with pytest.raises(ValueError, match="después de reponer"):
            cancel_petty_cash_expense(expense)
        database.session.rollback()


def test_replenishment_link_failure_rolls_back_and_allows_retry(petty_cash_link_app):
    """A failed relation insert rolls back its request and leaves the expense claimable."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        existing_replenishments = database.session.execute(
            database.select(database.func.count(PettyCashReplenishment.id)).filter_by(company=ids["company"])
        ).scalar_one()
        application.config["INTERNAL_CONTROLS_ENFORCE"] = True

        def reject_link_insert(connection, cursor, statement, parameters, context, executemany):
            """Inject a real persistence-boundary failure before the relation INSERT."""
            del connection, cursor, parameters, context, executemany
            if statement.lstrip().upper().startswith("INSERT INTO PETTY_CASH_REPLENISHMENT_EXPENSE"):
                raise IntegrityError(statement, {}, RuntimeError("injected relation failure"))

        event.listen(database.engine, "before_cursor_execute", reject_link_insert)
        try:
            with pytest.raises(IntegrityError, match="injected relation failure"):
                _create_replenishment(ids["company"], ids["fund_id"], expense.id)
        finally:
            event.remove(database.engine, "before_cursor_execute", reject_link_insert)

        assert database.session.get(PettyCashExpense, expense.id).replenishment_id is None
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishment.id)).filter_by(company=ids["company"])
            ).scalar_one()
            == existing_replenishments
        )
        assert (
            database.session.execute(database.select(database.func.count(PettyCashReplenishmentExpense.id))).scalar_one() == 0
        )

        retry = _create_replenishment(ids["company"], ids["fund_id"], expense.id, request_day=21)
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishmentExpense.id)).filter_by(
                    petty_cash_replenishment_id=retry.id,
                    petty_cash_expense_id=expense.id,
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("channel", ["orm", "core", "text"])
def test_replenishment_link_cannot_be_inserted_outside_its_service(petty_cash_link_app, channel):
    """Only the service can append a reservation through the ORM or SQL channels."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        replenishment = PettyCashReplenishment(
            company=ids["company"],
            petty_cash_id=ids["fund_id"],
            request_date=date(2026, 10, 20),
            amount=expense.amount,
            status="borrador",
            docstatus=0,
        )
        database.session.add(replenishment)
        database.session.commit()
        application.config["INTERNAL_CONTROLS_ENFORCE"] = True
        with pytest.raises(ValueError, match="servicio"):
            if channel == "orm":
                database.session.add(
                    PettyCashReplenishmentExpense(
                        company=ids["company"],
                        petty_cash_replenishment_id=replenishment.id,
                        petty_cash_expense_id=expense.id,
                    )
                )
                database.session.flush()
            elif channel == "core":
                database.session.execute(
                    database.insert(PettyCashReplenishmentExpense).values(
                        company=ids["company"],
                        petty_cash_replenishment_id=replenishment.id,
                        petty_cash_expense_id=expense.id,
                    )
                )
            else:
                database.session.execute(
                    text(
                        "INSERT INTO petty_cash_replenishment_expense "
                        "(id, company, petty_cash_replenishment_id, petty_cash_expense_id) "
                        "VALUES (:id, :company, :replenishment_id, :expense_id)"
                    ),
                    {
                        "id": f"L{uuid4().hex[:25]}",
                        "company": ids["company"],
                        "replenishment_id": replenishment.id,
                        "expense_id": expense.id,
                    },
                )
        database.session.rollback()

        assert (
            database.session.execute(database.select(database.func.count(PettyCashReplenishmentExpense.id))).scalar_one() == 0
        )
        assert database.session.get(PettyCashExpense, expense.id).replenishment_id is None


def test_concurrent_replenishments_reserve_one_posted_expense_once(petty_cash_link_app):
    """Concurrent requests serialize and leave one append-only reservation."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        expense_id = expense.id
    start = Barrier(2)

    def request_replenishment():
        """Run one request using its own Flask and SQLAlchemy session."""
        with application.app_context():
            try:
                start.wait(timeout=5)
                return _create_replenishment(ids["company"], ids["fund_id"], expense_id)
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request_replenishment) for _ in range(2)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=15))
            except ValueError as error:
                assert "no estan disponibles" in str(error)

    assert len(outcomes) == 1
    with application.app_context():
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishmentExpense.id)).filter_by(
                    petty_cash_expense_id=expense_id
                )
            ).scalar_one()
            == 1
        )
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishment.id)).filter_by(company=ids["company"])
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("desktop", [True, False])
@pytest.mark.parametrize("channel", ["orm", "core", "text"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_replenishment_link_rejects_update_and_delete_in_both_modes(petty_cash_link_app, desktop, channel, operation):
    """No application SQL channel can rewrite or remove the association evidence."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        application.config["MODO_ESCRITORIO"] = desktop
        application.config["INTERNAL_CONTROLS_ENFORCE"] = True
        replenishment = _create_replenishment(ids["company"], ids["fund_id"], expense.id)
        link_id = database.session.execute(
            database.select(PettyCashReplenishmentExpense.id).filter_by(
                petty_cash_replenishment_id=replenishment.id,
                petty_cash_expense_id=expense.id,
            )
        ).scalar_one()

        with pytest.raises(ValueError):
            if channel == "orm":
                link = database.session.get(PettyCashReplenishmentExpense, link_id)
                assert link is not None
                if operation == "update":
                    link.company = "invalid"
                else:
                    database.session.delete(link)
                database.session.flush()
            elif channel == "core":
                if operation == "update":
                    statement = (
                        database.update(PettyCashReplenishmentExpense)
                        .where(PettyCashReplenishmentExpense.id == link_id)
                        .values(company="invalid")
                    )
                else:
                    statement = database.delete(PettyCashReplenishmentExpense).where(
                        PettyCashReplenishmentExpense.id == link_id
                    )
                database.session.execute(statement)
            else:
                sql = (
                    "UPDATE petty_cash_replenishment_expense SET company = 'invalid' WHERE id = :id"
                    if operation == "update"
                    else "DELETE FROM petty_cash_replenishment_expense WHERE id = :id"
                )
                database.session.execute(text(sql), {"id": link_id})
        database.session.rollback()
        persisted = database.session.get(PettyCashReplenishmentExpense, link_id)
        assert persisted is not None and persisted.company == ids["company"]


def test_corte_anterior_conserva_el_gasto_como_pendiente(petty_cash_link_app):
    """Un corte previo a la reposicion no descuenta el gasto reservado despues (#1987)."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        expense_id = expense.id
        fund = database.session.get(PettyCashAccount, ids["fund_id"])
        _create_replenishment(ids["company"], fund.id, expense_id, request_day=20)

        assert petty_cash_pending_replenishment_total(fund, date(2026, 10, 19)) == Decimal("85.00")
        assert [row.id for row in petty_cash_expenses_available_for_replenishment(fund.id, date(2026, 10, 19))] == [expense_id]
        assert petty_cash_pending_replenishment_total(fund, date(2026, 10, 20)) == Decimal("0")
        assert petty_cash_expenses_available_for_replenishment(fund.id, date(2026, 10, 20)) == []
        assert petty_cash_pending_replenishment_total(fund, date(2026, 10, 21)) == Decimal("0")

        database.session.add(
            Book(
                entity=ids["company"],
                code="DEFAULT_BOOK",
                name="Libro principal",
                status="activo",
                currency="NIO",
                default=True,
                is_primary=True,
            )
        )
        database.session.commit()
        derived = _petty_cash_reconciliation_derived_values(fund, date(2026, 10, 19))
        assert derived["pending_expenses"] == Decimal("85.00")


def test_reposicion_anterior_al_gasto_se_rechaza_sin_reserva(petty_cash_link_app):
    """Una reposicion fechada antes del gasto no crea solicitud ni vinculo parcial (#1987)."""
    application, ids = petty_cash_link_app
    with application.app_context():
        expense = _seed_posted_expense(ids["company"], ids["fund_id"])
        fund = database.session.get(PettyCashAccount, ids["fund_id"])
        with pytest.raises(ValueError, match="anterior"):
            _create_replenishment(ids["company"], fund.id, expense.id, request_day=18)
        database.session.rollback()

        assert database.session.get(PettyCashExpense, expense.id).replenishment_id is None
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishment.id)).filter_by(company=ids["company"])
            ).scalar_one()
            == 0
        )
        assert (
            database.session.execute(database.select(database.func.count(PettyCashReplenishmentExpense.id))).scalar_one() == 0
        )
        assert [row.id for row in petty_cash_expenses_available_for_replenishment(fund.id)] == [expense.id]
