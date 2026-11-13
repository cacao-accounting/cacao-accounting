"""Smoke coverage for the SQLAlchemy engines enabled by the CI database matrix."""

from secrets import token_hex

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, database

pytestmark = pytest.mark.database


def test_configured_database_engine_persists_a_currency(tmp_path):
    """Persist and reload a business reference through the configured database engine."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    expected_dialect = make_url(configured_uri).get_backend_name()
    database_uri = configured_uri
    if expected_dialect == "sqlite":
        database_uri = f"sqlite:///{tmp_path / 'database-engine-smoke.sqlite'}"

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "database-engine-smoke-test",
        }
    )
    currency_code = f"QA{token_hex(2).upper()}"

    with app.app_context():
        assert database.engine.dialect.name == expected_dialect
        assert expected_dialect in {"sqlite", "postgresql", "mysql"}
        database.create_all()
        currency = Currency(code=currency_code, name="Moneda de verificación", decimals=2, active=True, default=False)
        try:
            database.session.add(currency)
            database.session.commit()
            database.session.expire_all()

            persisted = database.session.execute(select(Currency).where(Currency.code == currency_code)).scalar_one()
            assert persisted.name == "Moneda de verificación"
            assert persisted.decimals == 2
        finally:
            database.session.rollback()
            persisted = database.session.execute(select(Currency).where(Currency.code == currency_code)).scalar_one_or_none()
            if persisted is not None:
                database.session.delete(persisted)
                database.session.commit()
            database.session.remove()
            database.engine.dispose()
