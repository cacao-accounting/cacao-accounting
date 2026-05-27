# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Document printing and QR validation subsystem."""

from sqlalchemy.exc import SQLAlchemyError

from cacao_accounting.printing.registry import init_printing_registry
from cacao_accounting.printing.seed import seed_print_templates


def init_printing() -> None:
    """Register printable documents and seed templates when tables exist."""
    init_printing_registry()
    try:
        seed_print_templates()
    except SQLAlchemyError:
        pass
