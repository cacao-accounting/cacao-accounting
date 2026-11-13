# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Schema compatibility for the Cloud email queue."""

from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

migration = importlib.import_module("cacao_accounting.migrations.20261113_0005_email_queue_html")


def test_upgrade_preserves_queued_messages_and_defaults_to_plain_text(monkeypatch):
    """Existing retry rows remain readable after adding their MIME format."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE email_queue (id VARCHAR(26) PRIMARY KEY, recipient VARCHAR(255) NOT NULL, "
            "subject VARCHAR(255) NOT NULL, body TEXT NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO email_queue (id, recipient, subject, body) VALUES "
            "('queue-1', 'customer@example.com', 'Factura disponible', 'Notificación original')"
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        columns = {column["name"] for column in sa.inspect(connection).get_columns("email_queue")}
        assert "is_html" in columns
        assert connection.exec_driver_sql("SELECT id, body, is_html FROM email_queue").one() == (
            "queue-1",
            "Notificación original",
            False,
        )
    engine.dispose()
