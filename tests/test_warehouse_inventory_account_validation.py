# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2174: la configuración de bodega exige una cuenta imputable vigente.

El selector solo ofrece cuentas activas, habilitadas y hoja. El validador de
servidor debe aplicar los mismos criterios antes de persistir la configuración
de inventario por compañía.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, database
from cacao_accounting.inventario.services import _validate_warehouse_company_rows


def _inventory_account(**overrides) -> Accounts:
    """Build a company inventory account with the requested state."""
    suffix = uuid4().hex[:6].upper()
    values = {
        "entity": "cacao",
        "code": f"INV{suffix}",
        "name": "Cuenta de inventario",
        "classification": "asset",
        "account_type": "inventory",
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
        ({"account_type": "expense"}, "tipo inventario"),
    ],
)
def test_non_postable_inventory_accounts_are_rejected(app, entorno_contable, overrides, message):
    """Inactiva, deshabilitada, agrupadora o de otro tipo no se persiste."""
    with app.app_context():
        account = _inventory_account(**overrides)
        database.session.add(account)
        database.session.commit()
        account_id = account.id

        with pytest.raises(ValueError, match=message):
            _validate_warehouse_company_rows([{"company": "cacao", "inventory_account_id": account_id}])


def test_active_leaf_inventory_account_is_accepted(app, entorno_contable):
    """Una cuenta activa, habilitada, hoja y de inventario sigue siendo válida."""
    with app.app_context():
        account = _inventory_account()
        database.session.add(account)
        database.session.commit()

        _validate_warehouse_company_rows([{"company": "cacao", "inventory_account_id": account.id}])
