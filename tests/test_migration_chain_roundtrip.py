"""Check the pre-Alpha baseline revision remains a harmless no-op."""

from cacao_accounting import alembic, create_app
from cacao_accounting.database import database
from sqlalchemy import inspect


def test_dummy_baseline_migration_round_trips_without_building_the_schema(tmp_path):
    """Round-trip the sole dummy revision while schema creation stays with database initialization."""
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
        assert tuple(script.revision for script in alembic.current()) == ("20260809_0001",)
        assert not inspect(database.engine).has_table("user")

        alembic.downgrade("base")
        assert alembic.current() == ()
        assert not inspect(database.engine).has_table("user")

        alembic.upgrade("head")
        assert tuple(script.revision for script in alembic.current()) == ("20260809_0001",)

        database.session.remove()
        database.engine.dispose()
