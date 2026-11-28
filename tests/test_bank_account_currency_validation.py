# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1979: una cuenta bancaria no acepta monedas inactivas."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.bancos.services import _validate_bank_account_references
from cacao_accounting.database import Bank, Currency, database
from cacao_accounting.document_identifiers import IdentifierConfigurationError


def _banco() -> str:
    banco = Bank(name=f"Banco QA {uuid4().hex[:6]}")
    database.session.add(banco)
    database.session.commit()
    return banco.id


def test_moneda_inactiva_se_rechaza(app):
    """La guardia cubre la desactivación concurrente entre GET y POST."""
    with app.app_context():
        _inactiva = f"OFF{uuid4().hex[:4]}"
        database.session.add(Currency(code=_inactiva, name="Inactiva", decimals=2, active=False))
        database.session.commit()
        banco_id = _banco()

        with pytest.raises(IdentifierConfigurationError, match="no está activa"):
            _validate_bank_account_references(company="cacao", bank_id=banco_id, currency=_inactiva, gl_account_id=None)


def test_moneda_activa_se_acepta(app):
    """Una moneda vigente no bloquea el alta."""
    with app.app_context():
        _activa = f"NI{uuid4().hex[:4]}"
        database.session.add(Currency(code=_activa, name="Córdoba", decimals=2, active=True, default=False))
        database.session.commit()
        banco_id = _banco()

        _validate_bank_account_references(company="cacao", bank_id=banco_id, currency=_activa, gl_account_id=None)
