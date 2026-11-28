# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contrato mínimo de cadena Alembic (#1898/#1849)."""

from __future__ import annotations

import sqlalchemy as sa

from cacao_accounting import alembic, create_app
from cacao_accounting.database import database


def test_alembic_head_round_trip_without_building_schema(tmp_path):
    """upgrade head registra revisiones sin crear esquema de aplicación."""
    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'baseline-migration.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "baseline-migration-test",
        }
    )

    with app.app_context():
        alembic.upgrade("head")
        revisions = {script.revision for script in alembic.current()}
        assert "20261127_0001" in revisions
        inspector = sa.inspect(database.engine)
        assert not inspector.has_table("user")

        alembic.downgrade("base")
        assert alembic.current() == ()
        alembic.upgrade("head")
        database.session.remove()
        database.engine.dispose()
