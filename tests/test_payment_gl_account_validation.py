# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2180: las notas bancarias exigen cuentas GL imputables de su compañía.

El selector ofrece cuentas activas, habilitadas y hoja; el servidor debe
rechazar un POST manipulado que intente usar otra cuenta antes de guardar o
postear la nota.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.bancos.services import _validate_payment_gl_accounts
from cacao_accounting.database import Accounts, Entity, database


def _account(**overrides) -> Accounts:
    """Build a GL account in the requested company and state."""
    suffix = uuid4().hex[:6].upper()
    values = {
        "entity": "cacao",
        "code": f"GL{suffix}",
        "name": "Cuenta GL del pago",
        "classification": "asset",
        "account_type": "bank",
        "active": True,
        "enabled": True,
        "group": False,
    }
    values.update(overrides)
    return Accounts(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"active": False}, "activa, habilitada"),
        ({"enabled": False}, "activa, habilitada"),
        ({"group": True}, "activa, habilitada"),
        ({"entity": "otra"}, "compañía del documento"),
    ],
)
def test_non_postable_payment_accounts_are_rejected(app, entorno_contable, overrides, message):
    """Inactiva, deshabilitada, agrupadora o de otra compañía no se acepta."""
    with app.app_context():
        if overrides.get("entity") and overrides["entity"] != "cacao":
            database.session.add(
                Entity(
                    code=overrides["entity"],
                    name="Otra compañía",
                    company_name="Otra Compañía SA",
                    tax_id=f"TAX-{overrides['entity']}",
                    currency="NIO",
                    enabled=True,
                )
            )
            database.session.flush()
        account = _account(**overrides)
        database.session.add(account)
        database.session.commit()

        with pytest.raises(ValueError, match=message):
            _validate_payment_gl_accounts(
                company="cacao",
                payment_type="pay",
                bank_account_id=None,
                target_bank_account_id=None,
                paid_from_account_id=account.id,
                paid_to_account_id=None,
            )


def test_active_leaf_payment_account_is_accepted(app, entorno_contable):
    """Una cuenta propia, activa, habilitada y hoja sigue siendo válida."""
    with app.app_context():
        account = _account()
        database.session.add(account)
        database.session.commit()

        _validate_payment_gl_accounts(
            company="cacao",
            payment_type="pay",
            bank_account_id=None,
            target_bank_account_id=None,
            paid_from_account_id=account.id,
            paid_to_account_id=None,
        )
