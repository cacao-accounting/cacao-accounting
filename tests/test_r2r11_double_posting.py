# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""R2R-11: proteccion contra doble posting en funciones post_* individuales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Crea una aplicacion Flask aislada en sqlite en memoria para las pruebas."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao",
                tax_id="J0001",
                currency="NIO",
            )
        )
        database.session.commit()
        yield app


def test_post_comprobante_contable_rejects_double_posting(app_ctx):
    """El segundo posting de un comprobante ya contabilizado debe fallar."""
    from cacao_accounting.contabilidad.posting import PostingError, post_comprobante_contable
    from cacao_accounting.database import (
        Accounts,
        ComprobanteContable,
        ComprobanteContableDetalle,
        GLEntry,
        database,
    )

    receivable_account = Accounts(
        entity="cacao",
        code="AR-001",
        name="Cuentas por cobrar",
        active=True,
        enabled=True,
        classification="asset",
    )
    revenue_account = Accounts(
        entity="cacao",
        code="REV-001",
        name="Ingresos",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([receivable_account, revenue_account])
    database.session.flush()

    journal = ComprobanteContable(
        entity="cacao",
        date=date(2026, 5, 4),
        memo="Comprobante doble posting",
    )
    database.session.add(journal)
    database.session.flush()

    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="cacao",
                account=receivable_account.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("100.00"),
                memo="Cliente por cobrar",
                third_type="customer",
                third_code="CUST-001",
            ),
            ComprobanteContableDetalle(
                entity="cacao",
                account=revenue_account.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("-100.00"),
                memo="Venta manual",
            ),
        ]
    )
    database.session.commit()

    first_entries = post_comprobante_contable(journal)
    database.session.commit()

    assert len(first_entries) == 2

    with pytest.raises(PostingError):
        post_comprobante_contable(journal)

    database.session.rollback()

    posted_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=journal.id))
        .scalars()
        .all()
    )
    assert len(posted_entries) == 2
