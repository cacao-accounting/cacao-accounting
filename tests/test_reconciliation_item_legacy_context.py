# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1318: las asignaciones sin contexto resuelven cuenta, moneda y compañía.

El backfill sin consumidores se retiró (`40453d45`). Los consumidores deben
seguir resolviendo las partidas legacy por su transacción fuente y omitir las
irreconocibles, además de rechazar monedas incompatibles.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    _allocated_for_target,
    _validate_target_allocation_currency,
)
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    Reconciliation,
    ReconciliationItem,
    database,
)


@pytest.fixture
def conciliacion_legacy(app, entorno_contable):
    """Crea una transacción bancaria con asignaciones legacy y huérfanas."""
    del entorno_contable
    sufijo = uuid4().hex[:8]
    with app.app_context():
        banco = Bank(name=f"Banco {sufijo}", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            bank_id=banco.id,
            company="cacao",
            account_name=f"Cuenta {sufijo}",
            account_no=f"ACC-{sufijo}",
            currency="NIO",
        )
        database.session.add(cuenta)
        database.session.flush()
        transaccion = BankTransaction(
            identity_key=f"legacy-{sufijo}",
            bank_account_id=cuenta.id,
            posting_date=date(2026, 5, 15),
            deposit=Decimal("0"),
            withdrawal=Decimal("100"),
            is_reconciled=False,
        )
        database.session.add(transaccion)
        database.session.flush()
        conciliacion = Reconciliation(company="cacao", recon_date=date(2026, 5, 15), recon_type="bank")
        database.session.add(conciliacion)
        database.session.flush()
        target_id = f"target-{sufijo}"
        database.session.add_all(
            [
                ReconciliationItem(
                    reconciliation_id=conciliacion.id,
                    reference_type="payment_entry",
                    reference_id=target_id,
                    amount=Decimal("100"),
                    allocated_amount=Decimal("40"),
                    status="reconciled",
                    source_type="bank_transaction",
                    source_id=transaccion.id,
                    target_type="payment_entry",
                    target_id=target_id,
                    bank_account_id=None,
                    currency=None,
                ),
                ReconciliationItem(
                    reconciliation_id=conciliacion.id,
                    reference_type="payment_entry",
                    reference_id=target_id,
                    amount=Decimal("100"),
                    allocated_amount=Decimal("60"),
                    status="reconciled",
                    source_type="bank_transaction",
                    source_id=f"inexistente-{sufijo}",
                    target_type="payment_entry",
                    target_id=target_id,
                    bank_account_id=cuenta.id,
                    currency=None,
                ),
            ]
        )
        database.session.commit()
        ids = {"cuenta": cuenta.id, "transaccion": transaccion.id, "target": target_id, "reconciliacion": conciliacion.id}
    yield ids
    with app.app_context():
        database.session.execute(
            database.delete(ReconciliationItem).where(ReconciliationItem.reconciliation_id == ids["reconciliacion"])
        )
        conciliacion = database.session.get(Reconciliation, ids["reconciliacion"])
        if conciliacion is not None:
            database.session.delete(conciliacion)
        transaccion = database.session.get(BankTransaction, ids["transaccion"])
        if transaccion is not None:
            database.session.delete(transaccion)
        cuenta = database.session.get(BankAccount, ids["cuenta"])
        if cuenta is not None:
            database.session.delete(cuenta)
        database.session.commit()


def test_backfill_sin_consumidores_permanece_retirado():
    """El único mecanismo activo es la resolución en los consumidores."""
    from cacao_accounting.bancos import reconciliation_service

    assert not hasattr(reconciliation_service, "backfill_reconciliation_item_context")


def test_allocated_for_target_resuelve_contexto_ausente(app, conciliacion_legacy):
    """La partida legacy cae a su transacción y la huérfana usa la pierna guardada."""
    with app.app_context():
        total = _allocated_for_target(
            "payment_entry", conciliacion_legacy["target"], bank_account_id=conciliacion_legacy["cuenta"]
        )

    assert total == Decimal("100")


def test_validacion_de_moneda_admite_legacy_y_rechaza_incompatibles(app, conciliacion_legacy):
    """Sin moneda guardada se resuelve por la fuente; con moneda distinta se rechaza."""
    with app.app_context():
        transaccion = database.session.get(BankTransaction, conciliacion_legacy["transaccion"])

        _validate_target_allocation_currency("payment_entry", conciliacion_legacy["target"], transaccion)

        primera = (
            database.session.execute(
                database.select(ReconciliationItem).filter_by(reconciliation_id=conciliacion_legacy["reconciliacion"])
            )
            .scalars()
            .first()
        )
        primera.currency = "USD"
        database.session.commit()

        with pytest.raises(BankReconciliationError, match="otra moneda"):
            _validate_target_allocation_currency("payment_entry", conciliacion_legacy["target"], transaccion)
