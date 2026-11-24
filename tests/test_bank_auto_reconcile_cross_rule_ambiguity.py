# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1721: distintas reglas no pueden aportar candidatos exactos en conflicto."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.bancos import statement_service
from cacao_accounting.bancos.reconciliation_service import BankCandidate
from cacao_accounting.database import Bank, BankAccount, BankMatchingRule, BankTransaction, database


def _escenario_con_dos_reglas() -> tuple[str, str]:
    """Transacción bancaria y dos reglas con tolerancias distintas."""
    sufijo = uuid4().hex[:8]
    banco = Bank(name=f"Banco {sufijo}", is_active=True)
    database.session.add(banco)
    database.session.flush()
    cuenta = BankAccount(
        bank_id=banco.id,
        company="cacao",
        account_name=f"Cuenta {sufijo}",
        account_no=f"ACC-{sufijo}",
    )
    database.session.add(cuenta)
    database.session.flush()
    transaccion = BankTransaction(
        identity_key=f"identity-{sufijo}",
        bank_account_id=cuenta.id,
        posting_date=date(2026, 10, 15),
        deposit=Decimal("100"),
        withdrawal=Decimal("0"),
        description="Depósito",
        is_reconciled=False,
    )
    database.session.add(transaccion)
    primera = BankMatchingRule(
        company="cacao",
        bank_account_id=cuenta.id,
        name=f"Cercana {sufijo}",
        days_tolerance=7,
        amount_tolerance=Decimal("0"),
        priority=1,
        is_active=True,
        auto_reconcile=True,
    )
    segunda = BankMatchingRule(
        company="cacao",
        bank_account_id=cuenta.id,
        name=f"Amplia {sufijo}",
        days_tolerance=30,
        amount_tolerance=Decimal("5"),
        priority=2,
        is_active=True,
        auto_reconcile=True,
    )
    database.session.add_all([primera, segunda])
    database.session.commit()
    return transaccion.id, primera.id


def _candidato(reference_id: str, importe: str) -> BankCandidate:
    return BankCandidate(
        reference_type="payment_entry",
        reference_id=reference_id,
        amount=Decimal(importe),
        posting_date=date(2026, 10, 15),
        reference_no=reference_id.upper(),
        score=100,
        status="exact",
    )


def test_candidatos_exactos_de_reglas_distintas_no_se_autoconcilian(app, monkeypatch):
    """Dos candidatos exactos distintos dejan la transacción para revisión manual."""
    with app.app_context():
        transaction_id, _ = _escenario_con_dos_reglas()

    candidato_a = _candidato("pe-cercana", "100")
    candidato_b = _candidato("pe-amplia", "105")

    def candidatos(_transaction_id, *, days_tolerance, amount_tolerance):
        if days_tolerance == 7:
            return [candidato_a]
        return [candidato_b]

    conciliaciones: list[object] = []
    monkeypatch.setattr(statement_service, "find_bank_reconciliation_candidates", candidatos)
    monkeypatch.setattr(
        statement_service,
        "reconcile_bank_items",
        lambda request: conciliaciones.append(request) or SimpleNamespace(id="rec-1"),
    )

    with app.app_context():
        resultado = statement_service.auto_reconcile_bank_transaction(transaction_id)

    assert resultado.reconciled is False
    assert resultado.reason == "ambiguous"
    assert resultado.candidate_reference_id is None
    assert conciliaciones == []


def test_mismo_candidato_en_dos_reglas_si_se_autoconcilia(app, monkeypatch):
    """El mismo candidato exacto repetido por varias reglas no es ambiguo."""
    with app.app_context():
        transaction_id, regla_id = _escenario_con_dos_reglas()

    candidato = _candidato("pe-unico", "100")
    conciliaciones: list[object] = []
    monkeypatch.setattr(statement_service, "find_bank_reconciliation_candidates", lambda *_a, **_k: [candidato])
    monkeypatch.setattr(
        statement_service,
        "reconcile_bank_items",
        lambda request: conciliaciones.append(request) or SimpleNamespace(id="rec-1"),
    )

    with app.app_context():
        resultado = statement_service.auto_reconcile_bank_transaction(transaction_id)

    assert resultado.reconciled is True
    assert resultado.rule_id == regla_id
    assert resultado.candidate_reference_id == "pe-unico"
    assert len(conciliaciones) == 1
