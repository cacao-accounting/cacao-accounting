# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""El matching automático respeta el filtro de referencia de la regla (#1509)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user
from sqlalchemy import inspect, select

from cacao_accounting.bancos.statement_service import apply_bank_matching_rule, auto_reconcile_bank_transaction
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    User,
    database,
)


def _escenario_referencia(referencia: str | None, *, filtro: str | None = "INV-", regla_global: bool = False):
    """Crea una regla con filtro y un candidato exacto real para la transacción."""
    sufijo = uuid4().hex[:8]
    banco = Bank(name=f"Banco Referencia {sufijo}", is_active=True)
    database.session.add(banco)
    database.session.flush()
    cuenta = BankAccount(
        bank_id=banco.id,
        company="cacao",
        account_name=f"Cuenta Referencia {sufijo}",
        account_no=sufijo,
        currency="NIO",
    )
    database.session.add(cuenta)
    database.session.flush()
    transaccion = BankTransaction(
        bank_account_id=cuenta.id,
        posting_date=date(2026, 5, 15),
        deposit=Decimal("100"),
        withdrawal=Decimal("0"),
        reference_number=referencia,
    )
    pago = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=1,
        payment_type="receive",
        bank_account_id=cuenta.id,
        currency="NIO",
        received_amount=Decimal("100"),
        reference_no=f"INV-{sufijo}",
    )
    regla = BankMatchingRule(
        company="cacao",
        bank_account_id=None if regla_global else cuenta.id,
        name=f"Regla Referencia {sufijo}",
        days_tolerance=0,
        amount_tolerance=Decimal("0"),
        reference_contains=filtro,
        priority=1,
        is_active=True,
        auto_reconcile=True,
    )
    database.session.add_all([transaccion, pago, regla])
    database.session.commit()
    return transaccion, pago, regla


@pytest.mark.parametrize("referencia", [None, "", "UNRELATED-REF"])
def test_transaccion_fuera_del_filtro_no_se_concilia(entorno_contable_aislado, referencia):
    """Una regla con filtro no participa si la referencia falta o no contiene el texto."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        transaccion, _, _ = _escenario_referencia(referencia)

        resultado = auto_reconcile_bank_transaction(transaccion.id)

        assert resultado.reconciled is False
        assert resultado.reason == "no_active_rule"
        assert resultado.rule_id is None
        assert database.session.get(BankTransaction, transaccion.id).is_reconciled is False
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaccion.id)).scalars().all()
            == []
        )
        assert database.session.execute(select(Reconciliation).filter_by(company="cacao")).scalars().all() == []


@pytest.mark.parametrize("referencia", ["PAGO INV-2026-05", "pago inv-2026-05"])
def test_transaccion_dentro_del_filtro_se_concilia_con_su_regla(entorno_contable_aislado, referencia):
    """La coincidencia literal insensible a mayúsculas conserva regla, candidato y evidencia."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        transaccion, pago, regla = _escenario_referencia(referencia)

        resultado = auto_reconcile_bank_transaction(transaccion.id)

        assert resultado.reconciled is True
        assert resultado.reason is None
        assert resultado.rule_id == regla.id
        assert resultado.candidate_reference_id == pago.id
        assert resultado.allocated_amount == Decimal("100")
        filas = (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaccion.id)).scalars().all()
        )
        assert len(filas) == 1
        assert filas[0].target_id == pago.id
        assert database.session.get(BankTransaction, transaccion.id).payment_entry_id == pago.id


def test_regla_global_respeta_el_mismo_filtro(entorno_contable_aislado):
    """Una regla de compañía sin cuenta específica respeta `reference_contains`."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        transaccion, pago, regla = _escenario_referencia("PAGO inv-2026-05", regla_global=True)

        assert regla.bank_account_id is None
        assert auto_reconcile_bank_transaction(transaccion.id).rule_id == regla.id
        assert database.session.get(BankTransaction, transaccion.id).payment_entry_id == pago.id


def test_regla_sin_filtro_acepta_referencia_ausente(entorno_contable_aislado):
    """Una regla sin `reference_contains` no excluye transacciones sin referencia."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        transaccion, pago, regla = _escenario_referencia(None, filtro=None)

        resultado = auto_reconcile_bank_transaction(transaccion.id)

        assert resultado.reconciled is True
        assert resultado.rule_id == regla.id
        assert resultado.candidate_reference_id == pago.id


def test_filtro_manual_y_automatico_comparten_semantica(entorno_contable_aislado):
    """Ambos modos usan substring literal e insensible a mayúsculas (#1509)."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        transaccion, _, regla = _escenario_referencia("PAGO inv-2026-05")
        ajena = BankTransaction(
            bank_account_id=transaccion.bank_account_id,
            posting_date=date(2026, 5, 15),
            deposit=Decimal("100"),
            withdrawal=Decimal("0"),
            reference_number="UNRELATED-REF",
        )
        sin_referencia = BankTransaction(
            bank_account_id=transaccion.bank_account_id,
            posting_date=date(2026, 5, 15),
            deposit=Decimal("100"),
            withdrawal=Decimal("0"),
            reference_number=None,
        )
        database.session.add_all([ajena, sin_referencia])
        database.session.commit()

        corrida = apply_bank_matching_rule(
            regla.id,
            transaccion.bank_account_id,
            (date(2026, 5, 1), date(2026, 5, 31)),
        )

        assert set(corrida.candidates_by_transaction) == {transaccion.id}


def test_comodines_sql_no_alteran_el_filtro_compartido(entorno_contable_aislado):
    """`%` se trata como carácter literal, no como comodín SQL."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        transaccion, _, regla = _escenario_referencia("INV-100", filtro="INV-%")

        resultado = auto_reconcile_bank_transaction(transaccion.id)
        corrida = apply_bank_matching_rule(
            regla.id,
            transaccion.bank_account_id,
            (date(2026, 5, 1), date(2026, 5, 31)),
        )

        assert resultado.reconciled is False
        assert resultado.reason == "no_active_rule"
        assert corrida.candidates_by_transaction == {}
