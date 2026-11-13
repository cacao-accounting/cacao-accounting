# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Business authorization, reservation and status invariants for petty cash replenishment."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.bancos.services import (
    cancel_petty_cash_expense,
    create_petty_cash_replenishment,
    replenish_petty_cash,
    set_petty_cash_replenishment_status,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CacaoConfig,
    Currency,
    Entity,
    Modules,
    PaymentEntry,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashReplenishment,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

PASSWORD = "cash-approval-test-2026"


@pytest.fixture
def replenishment_app(tmp_path):
    """Build Cloud roles and real replenishment rows in an isolated database."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'replenishment-approval.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        company = f"E{uuid4().hex[:8]}"
        currency = f"N{company[1:]}"
        user_ids = {role: f"{role[:4]}-{uuid4().hex[:8]}" for role in ("preparer", "editor", "approver")}
        cash_module = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one_or_none()
        if cash_module is None:
            try:
                with database.session.begin_nested():
                    cash_module = Modules(module="cash", default=False, enabled=True)
                    database.session.add(cash_module)
                    database.session.flush()
            except IntegrityError:
                cash_module = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        cash_module.enabled = True
        database.session.add_all(
            [
                Currency(code=currency, name="Córdoba", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {company}",
                    company_name=f"Empresa {company} SA",
                    tax_id=f"TAX-{company}",
                    currency=currency,
                    enabled=True,
                    status="activo",
                ),
                User(
                    id=user_ids["preparer"],
                    user=user_ids["preparer"],
                    name="Solicitante",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id=user_ids["editor"],
                    user=user_ids["editor"],
                    name="Editor",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id=user_ids["approver"],
                    user=user_ids["approver"],
                    name="Autorizador",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                CacaoConfig(key=f"approval_require_different_approver_{company}", value="true"),
            ]
        )
        database.session.flush()
        module_id = cash_module.id
        editor_role = Roles(name=f"cash-editor-{company}", note="Editar reposiciones")
        approver_role = Roles(name=f"cash-approver-{company}", note="Autorizar reposiciones")
        database.session.add_all([editor_role, approver_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=editor_role.id, module_id=module_id, access=True, edit=True),
                RolesAccess(rol_id=approver_role.id, module_id=module_id, access=True, approve=True),
                RolesUser(user_id=user_ids["editor"], role_id=editor_role.id, active=True),
                RolesUser(user_id=user_ids["approver"], role_id=approver_role.id, active=True),
                UserCompanyAccess(user_id=user_ids["preparer"], company_code=company),
                UserCompanyAccess(user_id=user_ids["editor"], company_code=company),
                UserCompanyAccess(user_id=user_ids["approver"], company_code=company),
            ]
        )
        account = Accounts(
            code=f"PC-{company}",
            name=f"Caja chica {company}",
            entity=company,
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(account)
        database.session.flush()
        fund = PettyCashAccount(
            company=company,
            account_id=account.id,
            name=f"Fondo {company}",
            currency=currency,
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fund)
        database.session.flush()
        rows = {
            requester: PettyCashReplenishment(
                company=company,
                petty_cash_id=fund.id,
                request_date=date(2026, 10, 20),
                amount=Decimal("100"),
                status="solicitado",
                requested_by=user_ids[requester],
                docstatus=1,
            )
            for requester in ("preparer", "approver")
        }
        database.session.add_all(rows.values())
        database.session.commit()
        ids = {
            "company": company,
            "preparer_user": user_ids["preparer"],
            "editor_user": user_ids["editor"],
            "approver_user": user_ids["approver"],
            "replenishment_by_preparer": rows["preparer"].id,
            "replenishment_by_approver": rows["approver"].id,
        }

    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(application, user_id: str):
    """Return a Flask test client authenticated as one seeded role holder."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_replenishment_approval_requires_authority_and_different_actor(replenishment_app):
    """An editor cannot approve; separation applies only when company policy asks."""
    application, ids = replenishment_app
    editor_response = _authenticated_client(application, ids["editor_user"]).post(
        f"/cash_management/petty-cash-replenishment/{ids['replenishment_by_preparer']}/status",
        data={"status": "aprobado"},
    )
    assert editor_response.status_code == 403
    with application.app_context():
        permissions = Permisos(obtener_id_modulo_por_nombre("cash"), ids["approver_user"])
        assert permissions.autorizar is True
        assert permissions.tiene_acceso_compania(ids["company"]) is True

    approver_response = _authenticated_client(application, ids["approver_user"]).post(
        f"/cash_management/petty-cash-replenishment/{ids['replenishment_by_preparer']}/status",
        data={"status": "aprobado"},
    )
    assert approver_response.status_code == 302
    with application.app_context():
        approved_replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert approved_replenishment is not None
        assert approved_replenishment.status == "aprobado"
        assert approved_replenishment.approved_by == ids["approver_user"]

        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"])
        assert replenishment is not None
        with pytest.raises(ValueError, match="autorización de Caja Chica"):
            set_petty_cash_replenishment_status(replenishment, "aprobado", actor_id=ids["editor_user"])
        database.session.rollback()
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"])
        assert replenishment is not None
        assert replenishment.status == "solicitado"
        assert replenishment.approved_by is None

        with pytest.raises(ValueError, match="persona distinta"):
            set_petty_cash_replenishment_status(
                database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"]),
                "aprobado",
                actor_id=ids["approver_user"],
            )
        database.session.rollback()
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"])
        assert replenishment is not None
        assert replenishment.status == "solicitado"
        assert replenishment.approved_by is None

        database.session.execute(
            database.update(CacaoConfig)
            .where(CacaoConfig.key == f"approval_require_different_approver_{ids['company']}")
            .values(value="false")
        )
        database.session.commit()
        approved = set_petty_cash_replenishment_status(
            database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"]),
            "aprobado",
            actor_id=ids["approver_user"],
        )
        assert approved.status == "aprobado"
        assert approved.approved_by == ids["approver_user"]


def test_replenishment_cannot_skip_payment_to_reimbursed_status(replenishment_app):
    """Only the posted bank debit note can complete a replenishment."""
    application, ids = replenishment_app
    with application.app_context():
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        replenishment.status = "aprobado"
        database.session.commit()

        with pytest.raises(ValueError, match="Transición de reposición no válida"):
            set_petty_cash_replenishment_status(replenishment, "reembolsado", actor_id=ids["approver_user"])

        database.session.rollback()
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        assert replenishment.status == "aprobado"
        assert replenishment.bank_debit_note_id is None
        assert (
            database.session.execute(database.select(PaymentEntry.id).where(PaymentEntry.company == ids["company"])).first()
            is None
        )


def test_replenishment_waits_for_sqlite_writer_and_rechecks_committed_status(replenishment_app):
    """A waiting SQLite writer sees a completed reimbursement before creating another payment."""
    application, ids = replenishment_app
    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La prueba verifica la reserva de escritor específica de SQLite.")

        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        replenishment.status = "aprobado"
        database.session.commit()
        database.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        replenishment.status = "reembolsado"
        database.session.flush()
        started = Event()

        def second_replenishment_attempt():
            with application.app_context():
                started.set()
                current = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
                assert current is not None
                replenish_petty_cash(current, bank_account_id="unused")

        with ThreadPoolExecutor(max_workers=1) as executor:
            attempt = executor.submit(second_replenishment_attempt)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                attempt.result(timeout=0.1)

            database.session.commit()
            with pytest.raises(ValueError, match="Solo se puede reponer una solicitud aprobada"):
                attempt.result(timeout=5)

    with application.app_context():
        assert (
            database.session.execute(database.select(PaymentEntry.id).where(PaymentEntry.company == ids["company"])).first()
            is None
        )
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        assert replenishment.status == "reembolsado"


def test_replenishment_waits_for_sqlite_writer_and_rechecks_claimed_expense(replenishment_app):
    """A competing request sees the first reservation after its SQLite transaction commits."""
    application, ids = replenishment_app
    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La intercalación verifica la reserva de escritor específica de SQLite.")
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"])).scalar_one()
        expense = PettyCashExpense(
            company=ids["company"],
            petty_cash_id=fund.id,
            posting_date=date(2026, 10, 19),
            amount=Decimal("100"),
            concept="Compra operativa",
            expense_account_code=f"EXP-{ids['company']}",
            docstatus=1,
        )
        previous_request = PettyCashReplenishment(
            company=ids["company"],
            petty_cash_id=fund.id,
            request_date=date(2026, 10, 20),
            amount=Decimal("100"),
            status="borrador",
            docstatus=0,
        )
        database.session.add_all([expense, previous_request])
        database.session.commit()
        expense_id = expense.id
        previous_request_id = previous_request.id
        fund_id = fund.id

        database.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        expense.replenishment_id = previous_request_id
        database.session.flush()
        started = Event()

        def competing_request():
            with application.app_context():
                stale_expense = database.session.get(PettyCashExpense, expense_id)
                assert stale_expense is not None
                assert stale_expense.replenishment_id is None
                started.set()
                create_petty_cash_replenishment(
                    company=ids["company"],
                    petty_cash_id=fund_id,
                    expense_ids=[expense_id],
                    request_date=date(2026, 10, 21),
                    actor_id=ids["preparer_user"],
                )

        with ThreadPoolExecutor(max_workers=1) as executor:
            request = executor.submit(competing_request)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                request.result(timeout=0.1)

            database.session.commit()
            with pytest.raises(ValueError, match="no estan disponibles"):
                request.result(timeout=5)

        assert expense.replenishment_id == previous_request_id
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishment.id)).filter_by(company=ids["company"])
            ).scalar_one()
            == 3
        )


def test_expense_cancellation_waits_for_sqlite_reservation(replenishment_app):
    """A cancellation that loaded an unreserved expense must see a concurrent claim."""
    application, ids = replenishment_app
    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La intercalación verifica la reserva de escritor específica de SQLite.")
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"])).scalar_one()
        expense = PettyCashExpense(
            company=ids["company"],
            petty_cash_id=fund.id,
            posting_date=date(2026, 10, 19),
            amount=Decimal("100"),
            concept="Compra operativa",
            expense_account_code=f"EXP-{ids['company']}",
            docstatus=1,
        )
        prior_request = PettyCashReplenishment(
            company=ids["company"],
            petty_cash_id=fund.id,
            request_date=date(2026, 10, 20),
            amount=Decimal("100"),
            status="borrador",
            docstatus=0,
        )
        database.session.add_all([expense, prior_request])
        database.session.commit()
        expense_id = expense.id

        database.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        expense.replenishment_id = prior_request.id
        database.session.flush()
        started = Event()

        def competing_cancellation():
            with application.app_context():
                stale_expense = database.session.get(PettyCashExpense, expense_id)
                assert stale_expense is not None
                assert stale_expense.replenishment_id is None
                started.set()
                cancel_petty_cash_expense(stale_expense, actor_id=ids["preparer_user"])

        with ThreadPoolExecutor(max_workers=1) as executor:
            cancellation = executor.submit(competing_cancellation)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                cancellation.result(timeout=0.1)

            database.session.commit()
            with pytest.raises(ValueError, match="gasto reservado en una reposición"):
                cancellation.result(timeout=5)

        assert expense.docstatus == 1
        assert expense.replenishment_id == prior_request.id
