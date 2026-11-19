# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2161: el servicio rechaza importes negativos en plantillas recurrentes.

El JavaScript bloquea el caso en la interfaz, pero el POST entrega
`items_json` al servicio; la validación server-side debe conservar el
invariante contable sin depender del navegador.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.recurring_journal_service import (
    RecurringJournalError,
    create_recurring_template,
)
from cacao_accounting.database import Accounts, RecurringJournalItem, RecurringJournalTemplate, User, database


def _template_data(code: str) -> dict:
    """Build the minimum template header accepted by the service."""
    return {
        "code": code,
        "name": "Plantilla con importes",
        "company": "cacao",
        "ledger_id": None,
        "books": ["DEFAULT_BOOK"],
        "naming_series_id": None,
        "description": "Plantilla para validar importes negativos",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "frequency": "monthly",
        "currency": None,
    }


def _accounts() -> tuple[str, str, str]:
    """Return two real accounts and the admin user id."""
    cargo = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
    abono = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    return str(cargo.code), str(abono.code), str(admin.id)


@pytest.mark.parametrize(
    ("debit", "credit"),
    [(-10, 0), (0, -10), (-10, -10)],
)
def test_negative_template_amounts_are_rejected(app, entorno_contable, debit, credit):
    """A balanced pair with a negative side is refused before persisting."""
    code = f"NG{uuid4().hex[:6].upper()}"
    with app.app_context():
        cargo, abono, admin = _accounts()
        with pytest.raises(RecurringJournalError, match="negativos"):
            create_recurring_template(
                data=_template_data(code),
                items=[
                    {"account_code": cargo, "debit": debit, "credit": credit},
                    {"account_code": abono, "debit": abs(credit), "credit": abs(debit)},
                ],
                user_id=admin,
            )
        database.session.rollback()
        assert (
            database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=code)).scalar_one_or_none()
            is None
        )


def test_positive_balanced_template_is_still_created(app, entorno_contable):
    """The guard does not change the valid two-line contract."""
    code = f"OK{uuid4().hex[:6].upper()}"
    with app.app_context():
        cargo, abono, admin = _accounts()
        template = create_recurring_template(
            data=_template_data(code),
            items=[
                {"account_code": cargo, "debit": 50, "credit": 0},
                {"account_code": abono, "debit": 0, "credit": 50},
            ],
            user_id=admin,
        )
        assert template.code == code
        for line in database.session.execute(
            database.select(RecurringJournalItem).filter_by(template_id=template.id)
        ).scalars():
            database.session.delete(line)
        database.session.delete(template)
        database.session.commit()
