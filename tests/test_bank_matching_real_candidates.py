# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresiones del importe de candidatos reales de conciliación (#1644)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask_login import login_user
from sqlalchemy import inspect, select
import pytest

from cacao_accounting.bancos.reconciliation_service import (
    BankCandidate,
    BankReconciliationError,
    BankReconciliationMatch,
    BankReconciliationRequest,
    find_bank_reconciliation_candidates,
    reconcile_bank_items,
)
from cacao_accounting.bancos.statement_service import _accumulate_exact_candidate, auto_reconcile_bank_transaction
from cacao_accounting.database import (
    AuditTrail,
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    Entity,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    User,
    database,
)


def _escenario():
    """Crea dos reglas reales y un pago para una transacción bancaria."""
    suffix = uuid4().hex[:8]
    bank = Bank(name=f"Banco {suffix}", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(bank_id=bank.id, company="cacao", account_name=f"Cuenta {suffix}", account_no=suffix, currency="NIO")
    database.session.add(account)
    database.session.flush()
    transaction = BankTransaction(
        bank_account_id=account.id, posting_date=date(2026, 5, 15), deposit=Decimal("100"), withdrawal=Decimal("0")
    )
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=1,
        payment_type="receive",
        bank_account_id=account.id,
        currency="NIO",
        received_amount=Decimal("102"),
    )
    database.session.add_all([transaction, payment])
    database.session.add_all(
        [
            BankMatchingRule(
                company="cacao",
                bank_account_id=account.id,
                name=f"Regla {n}",
                days_tolerance=0,
                amount_tolerance=Decimal(str(tol)),
                priority=n,
                is_active=True,
                auto_reconcile=True,
            )
            for n, tol in ((1, 2), (2, 5))
        ]
    )
    database.session.commit()
    return account, transaction, payment


def test_reglas_reales_obtienen_mismo_importe_y_concilian(entorno_contable_aislado):
    """Dos tolerancias reales conservan el importe del mismo destino.

    El importe del candidato se calcula desde el saldo pendiente del pago y del
    importe bancario, sin intervención de la tolerancia. Esta prueba aporta la
    evidencia de que la discrepancia de importes para un mismo destino no es
    alcanzable en una evaluación real del motor sobre la misma transacción.
    """
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        _, transaction, payment = _escenario()

        candidates = [
            find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal(tol))
            for tol in ("2", "5")
        ]
        for result in candidates:
            assert len(result) == 1
            assert result[0].reference_id == payment.id
            assert result[0].status == "exact"
            assert result[0].amount == Decimal("100")

        regla_prioritaria = database.session.execute(
            select(BankMatchingRule).where(BankMatchingRule.priority == 1)
        ).scalar_one()

        result = auto_reconcile_bank_transaction(transaction.id)
        assert result.reconciled is True
        assert result.allocated_amount == Decimal("100")
        assert result.candidate_reference_id == payment.id
        assert result.rule_id == regla_prioritaria.id
        rows = (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].target_id == payment.id
        assert rows[0].allocated_amount == Decimal("100")
        evento = database.session.execute(
            select(AuditTrail).where(
                AuditTrail.document_id == transaction.id,
                AuditTrail.action == "reconciled",
            )
        ).scalar_one()
        assert regla_prioritaria.name in evento.comment
        assert payment.id in evento.comment


def test_importes_distintos_para_mismo_destino_son_ambiguos(entorno_contable_aislado):
    """El consenso rechaza importes dispares para un mismo destino real.

    El candidato y las reglas salen del escenario persistido; solo se modela
    directamente la revisión de estado entre evaluaciones que representaría un
    saldo modificado, sin sustituir funciones del servicio.
    """
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        cuenta, transaction, _ = _escenario()
        candidato = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal("2"))[0]
        reglas = (
            database.session.execute(
                select(BankMatchingRule)
                .where(BankMatchingRule.company == "cacao", BankMatchingRule.bank_account_id == cuenta.id)
                .order_by(BankMatchingRule.priority)
            )
            .scalars()
            .all()
        )

        vistos: dict[tuple[str, str], tuple[BankCandidate, BankMatchingRule]] = {}
        assert _accumulate_exact_candidate(vistos, candidato, reglas[0]) is True
        revisado = replace(candidato, amount=candidato.amount - Decimal("10"), score=candidato.score + 10)
        assert _accumulate_exact_candidate(vistos, revisado, reglas[1]) is False

        assert len(vistos) == 1
        assert next(iter(vistos.values()))[0].amount == candidato.amount


def test_destinos_reales_distintos_quedan_ambiguos(entorno_contable_aislado):
    """Dos pagos reales elegibles no producen conciliación automática."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        account, transaction, _ = _escenario()
        database.session.add(
            PaymentEntry(
                company="cacao",
                posting_date=date(2026, 5, 15),
                docstatus=1,
                payment_type="receive",
                bank_account_id=account.id,
                currency="NIO",
                received_amount=Decimal("102"),
            )
        )
        database.session.commit()
        result = auto_reconcile_bank_transaction(transaction.id)
        assert result.reconciled is False
        assert result.reason == "ambiguous"
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )


def test_saldo_cambiado_rechaza_candidato_obsoleto(entorno_contable_aislado):
    """La validación final rechaza un saldo consumido tras buscar candidatos."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        account, transaction, payment = _escenario()
        candidate = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal("2"))[0]
        other = BankTransaction(
            bank_account_id=account.id, posting_date=date(2026, 5, 15), deposit=Decimal("40"), withdrawal=Decimal("0")
        )
        database.session.add(other)
        database.session.flush()
        reconcile_bank_items(
            BankReconciliationRequest(
                company="cacao",
                reconciliation_date=date(2026, 5, 15),
                matches=[BankReconciliationMatch(other.id, "payment_entry", payment.id, Decimal("40"))],
            )
        )
        database.session.commit()
        with pytest.raises(BankReconciliationError, match="saldo pendiente"), database.session.begin_nested():
            reconcile_bank_items(
                BankReconciliationRequest(
                    company="cacao",
                    reconciliation_date=date(2026, 5, 15),
                    matches=[
                        BankReconciliationMatch(
                            transaction.id, candidate.reference_type, candidate.reference_id, candidate.amount
                        )
                    ],
                )
            )
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )
        assert auto_reconcile_bank_transaction(transaction.id).reason == "no_unique_exact_match"


def _escenario_reglas_disjuntas():
    """Crea dos reglas reales cuyos únicos exactos son pagos distintos (#1644)."""
    suffix = uuid4().hex[:8]
    bank = Bank(name=f"Banco Disjunto {suffix}", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name=f"Cuenta Disjunta {suffix}",
        account_no=suffix,
        currency="NIO",
    )
    database.session.add(account)
    database.session.flush()
    transaction = BankTransaction(
        bank_account_id=account.id,
        posting_date=date(2026, 5, 15),
        deposit=Decimal("100"),
        withdrawal=Decimal("0"),
    )
    pago_cercano = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=1,
        payment_type="receive",
        bank_account_id=account.id,
        currency="NIO",
        received_amount=Decimal("102"),
        reference_no=f"CERCANO-{suffix}",
    )
    pago_lejano = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 18),
        docstatus=1,
        payment_type="receive",
        bank_account_id=account.id,
        currency="NIO",
        received_amount=Decimal("100"),
        reference_no=f"LEJANO-{suffix}",
    )
    database.session.add_all([transaction, pago_cercano, pago_lejano])
    database.session.add_all(
        [
            BankMatchingRule(
                company="cacao",
                bank_account_id=account.id,
                name=f"Ventana estrecha {suffix}",
                days_tolerance=0,
                amount_tolerance=Decimal("5"),
                priority=1,
                is_active=True,
                auto_reconcile=True,
            ),
            BankMatchingRule(
                company="cacao",
                bank_account_id=account.id,
                name=f"Ventana amplia {suffix}",
                days_tolerance=5,
                amount_tolerance=Decimal("0"),
                priority=2,
                is_active=True,
                auto_reconcile=True,
            ),
        ]
    )
    database.session.commit()
    return account, transaction, pago_cercano, pago_lejano


def _ids_exactos(bank_transaction_id: str, *, days_tolerance: int, amount_tolerance: Decimal) -> set[str]:
    """Devuelve los destinos exactos que el motor real encuentra con esas tolerancias."""
    candidatos = find_bank_reconciliation_candidates(
        bank_transaction_id,
        days_tolerance=days_tolerance,
        amount_tolerance=amount_tolerance,
    )
    return {candidato.reference_id for candidato in candidatos if candidato.status == "exact"}


def test_reglas_reales_con_exactos_disjuntos_quedan_ambiguos(entorno_contable_aislado):
    """Cada regla ve un pago exacto distinto y el servicio no concilia ninguno."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        _, transaction, pago_cercano, pago_lejano = _escenario_reglas_disjuntas()

        assert _ids_exactos(transaction.id, days_tolerance=0, amount_tolerance=Decimal("5")) == {pago_cercano.id}
        assert _ids_exactos(transaction.id, days_tolerance=5, amount_tolerance=Decimal("0")) == {pago_lejano.id}

        resultado = auto_reconcile_bank_transaction(transaction.id)

        assert resultado.reconciled is False
        assert resultado.reason == "ambiguous"
        assert resultado.rule_id is None
        assert resultado.candidate_reference_id is None
        assert resultado.allocated_amount is None
        assert database.session.get(BankTransaction, transaction.id).is_reconciled is False
        assert database.session.get(BankTransaction, transaction.id).payment_entry_id is None
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )
        assert database.session.execute(database.select(Reconciliation).filter_by(company="cacao")).scalars().all() == []


def test_asignacion_real_no_crea_segundo_exacto_para_mismo_destino(entorno_contable_aislado):
    """Una conciliación real consume saldo y deja el candidato como parcial.

    Esto documenta por qué un cambio de saldo append-only no puede producir un
    segundo candidato ``exact`` con distinto importe para el mismo destino: el
    importe pendiente deja de coincidir con el importe del documento y el motor
    clasifica el candidato como ``partial``.
    """
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        account, transaction, payment = _escenario()

        primeros = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal("5"))
        assert len(primeros) == 1
        assert primeros[0].status == "exact"
        assert primeros[0].amount == Decimal("100")

        otra_transaccion = BankTransaction(
            bank_account_id=account.id,
            posting_date=date(2026, 5, 15),
            deposit=Decimal("40"),
            withdrawal=Decimal("0"),
        )
        database.session.add(otra_transaccion)
        database.session.flush()
        reconcile_bank_items(
            BankReconciliationRequest(
                company="cacao",
                reconciliation_date=date(2026, 5, 15),
                matches=[BankReconciliationMatch(otra_transaccion.id, "payment_entry", payment.id, Decimal("40"))],
            )
        )
        database.session.commit()

        segundos = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=Decimal("5"))
        assert len(segundos) == 1
        assert segundos[0].reference_id == payment.id
        assert segundos[0].status == "partial"
        assert segundos[0].amount == Decimal("62")
        assert (
            database.session.execute(database.select(ReconciliationItem).filter_by(source_id=transaction.id)).scalars().all()
            == []
        )


def test_cambio_persistido_de_importe_para_mismo_destino_es_ambiguo(entorno_contable_aislado):
    """Dos lecturas reales del mismo pago con importe modificado no se consolidan."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        _, transaction, pago, _ = _escenario_reglas_disjuntas()
        regla = database.session.execute(select(BankMatchingRule).where(BankMatchingRule.priority == 1)).scalar_one()
        tolerancia = Decimal("5")

        primeros = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=tolerancia)
        assert len(primeros) == 1
        assert primeros[0].status == "exact"
        assert primeros[0].amount == Decimal("100")

        pago.received_amount = Decimal("98")
        database.session.commit()
        segundos = find_bank_reconciliation_candidates(transaction.id, days_tolerance=0, amount_tolerance=tolerancia)
        assert len(segundos) == 1
        assert segundos[0].status == "exact"
        assert segundos[0].amount == Decimal("98")

        vistos = {}
        assert _accumulate_exact_candidate(vistos, primeros[0], regla) is True
        assert _accumulate_exact_candidate(vistos, segundos[0], regla) is False
        assert next(iter(vistos.values()))[0].amount == Decimal("100")


@pytest.mark.parametrize("alcance", ["inactiva", "otra_cuenta", "otra_compania"])
def test_reglas_fuera_de_alcance_no_habilitan_matching_automatico(entorno_contable_aislado, alcance):
    """Solo aplican reglas activas de la compañía y la cuenta de la transacción."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.test_request_context("/"):
        login_user(database.session.get(User, actor_id))
        account, transaction, _, _ = _escenario_reglas_disjuntas()

        if alcance == "inactiva":
            database.session.execute(database.update(BankMatchingRule).values(is_active=False))
        elif alcance == "otra_cuenta":
            otra_cuenta = BankAccount(
                bank_id=account.bank_id,
                company="cacao",
                account_name=f"Otra cuenta {uuid4().hex[:8]}",
                account_no=uuid4().hex[:8],
                currency="NIO",
            )
            database.session.add(otra_cuenta)
            database.session.flush()
            database.session.execute(database.update(BankMatchingRule).values(bank_account_id=otra_cuenta.id))
        else:
            database.session.add(
                Entity(code="otra", name="Otra", company_name="Otra SA", tax_id="OTRA-1", currency="NIO", enabled=True)
            )
            database.session.flush()
            database.session.execute(database.update(BankMatchingRule).values(company="otra"))
        database.session.commit()

        resultado = auto_reconcile_bank_transaction(transaction.id)
        assert resultado.reconciled is False
        assert resultado.reason == "no_active_rule"
        assert database.session.get(BankTransaction, transaction.id).is_reconciled is False
