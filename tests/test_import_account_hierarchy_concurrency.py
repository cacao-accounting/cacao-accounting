# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Importing an account serializes parent validation with hierarchy edits."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Currency, Entity, database
from cacao_accounting.default_scope import lock_default_scope
from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter


def test_import_waits_for_parent_demotion_and_rejects_child(tmp_path):
    """A second transaction must observe a committed demotion before import."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'accounts.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True))
        database.session.flush()
        database.session.add(
            Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J1", currency="NIO", enabled=True)
        )
        database.session.flush()
        database.session.add(Accounts(entity="cacao", code="PARENT", name="Grupo", group=True, active=True, enabled=True))
        database.session.commit()

    demoted = Event()
    release = Event()
    started = Event()

    def demote_parent():
        with app.app_context():
            try:
                lock_default_scope("account_hierarchy", "cacao")
                parent = database.session.execute(database.select(Accounts).filter_by(code="PARENT")).scalar_one()
                parent.group = False
                database.session.flush()
                demoted.set()
                assert release.wait(timeout=10)
                database.session.commit()
            finally:
                database.session.remove()

    def import_child():
        with app.app_context():
            try:
                child = Accounts(entity="cacao", code="CHILD", name="Hija", parent="PARENT", group=False)
                started.set()
                ChartOfAccountsAdapter().persist_document(child)
                database.session.commit()
                return "created"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(demote_parent)
            assert demoted.wait(timeout=10)
            second = workers.submit(import_child)
            assert started.wait(timeout=10)
            try:
                second.result(timeout=0.5)
                finished_early = True
            except TimeoutError:
                finished_early = False
            release.set()
            first.result(timeout=10)
            assert second.result(timeout=10) == "rejected"
        assert not finished_early
        with app.app_context():
            assert database.session.execute(database.select(Accounts).filter_by(code="CHILD")).scalar_one_or_none() is None
            assert database.session.execute(database.select(Accounts).filter_by(code="PARENT")).scalar_one().group is False
    finally:
        release.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
