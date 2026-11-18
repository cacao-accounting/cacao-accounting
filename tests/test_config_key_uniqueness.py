# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1697: cada clave de configuración identifica una sola fila.

La clave es única en el esquema y la escritura usa upsert, de modo que dos
escritores no dejan valores divergentes ni rompen los lectores escalares.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.config_values import set_config_value
from cacao_accounting.database import CacaoConfig, database
from cacao_accounting.setup.repository import set_setup_value


@pytest.fixture
def config_key_scenario():
    """Create an in-memory app with the configuration table."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_schema_rejects_two_rows_with_the_same_key(config_key_scenario):
    """The database constraint is the last line of defense."""
    app = config_key_scenario
    key = f"duplicate-{uuid4().hex[:8]}"

    with app.app_context():
        database.session.add_all([CacaoConfig(key=key, value="1"), CacaoConfig(key=key, value="2")])
        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()


def test_config_writer_updates_in_place(config_key_scenario):
    """Repeated writes keep one deterministic value."""
    app = config_key_scenario
    key = f"setting-{uuid4().hex[:8]}"

    with app.app_context():
        set_config_value(key, "first")
        database.session.commit()
        set_config_value(key, "second")
        database.session.commit()
        rows = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalars().all()

    assert len(rows) == 1
    assert rows[0].value == "second"


def test_setup_value_writer_is_idempotent(config_key_scenario):
    """The setup repository uses the same atomic writer."""
    app = config_key_scenario
    key = f"setup-{uuid4().hex[:8]}"

    with app.app_context():
        set_setup_value(key, "a")
        database.session.commit()
        set_setup_value(key, "b")
        database.session.commit()
        rows = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalars().all()

    assert len(rows) == 1
    assert rows[0].value == "b"
