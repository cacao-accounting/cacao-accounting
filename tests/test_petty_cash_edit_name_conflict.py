# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1646: el conflicto concurrente de nombre se traduce sin ocultar otros errores."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting.bancos import services as bank_services
from cacao_accounting.bancos.services import update_petty_cash_account
from cacao_accounting.database import Accounts, PettyCashAccount, database


def _fondo(company: str, account_id: str, name: str) -> PettyCashAccount:
    fondo = PettyCashAccount(
        company=company,
        account_id=account_id,
        name=name,
        currency="NIO",
        float_amount=Decimal("100"),
        is_default=False,
        is_active=True,
    )
    database.session.add(fondo)
    database.session.flush()
    return fondo


def test_conflicto_de_unicidad_se_traduce_y_libera_la_sesion(app, entorno_contable, monkeypatch):
    """La carrera que supera el prechequeo recibe ValueError y permite reintentar."""
    del entorno_contable
    sufijo = uuid4().hex[:8]
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        existente = _fondo("cacao", cuenta.id, f"Caja existente {sufijo}")
        a_renombrar = _fondo("cacao", cuenta.id, f"Caja a renombrar {sufijo}")
        database.session.commit()
        existente_id, a_renombrar_id = existente.id, a_renombrar.id

        monkeypatch.setattr(bank_services, "_petty_cash_name_exists", lambda *args, **kwargs: False)

        with pytest.raises(ValueError, match="Ya existe una caja chica con ese nombre"):
            update_petty_cash_account(
                database.session.get(PettyCashAccount, a_renombrar_id),
                name=f"Caja existente {sufijo}",
            )

        actualizado = update_petty_cash_account(
            database.session.get(PettyCashAccount, a_renombrar_id),
            name=f"Caja recuperada {sufijo}",
        )
        assert actualizado.name == f"Caja recuperada {sufijo}"

        database.session.execute(
            database.delete(PettyCashAccount).where(PettyCashAccount.id.in_([existente_id, a_renombrar_id]))
        )
        database.session.commit()


def test_error_de_integridad_ajeno_no_se_confunde_con_duplicado():
    """Una violación de FK no se presenta como nombre duplicado."""
    error = IntegrityError("INSERT", {}, Exception("FOREIGN KEY constraint failed"))

    assert bank_services._is_petty_cash_name_conflict(error) is False
    assert bank_services._is_petty_cash_name_conflict(
        IntegrityError(
            "INSERT", {}, Exception("UNIQUE constraint failed: petty_cash_account.company, petty_cash_account.name")
        )
    )
