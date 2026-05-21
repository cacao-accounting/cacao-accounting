# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validation utilities for accounting."""

from datetime import date
from sqlalchemy import select
from cacao_accounting.database import database, AccountingPeriod


def is_period_open(company: str, posting_date: date) -> bool:
    """Check if the accounting period for the given company and date is open."""
    period = (
        database.session.execute(
            select(AccountingPeriod)
            .filter_by(entity=company, is_closed=False, enabled=True)
            .where(AccountingPeriod.start <= posting_date)
            .where(AccountingPeriod.end >= posting_date)
        )
        .scalars()
        .first()
    )
    return period is not None
