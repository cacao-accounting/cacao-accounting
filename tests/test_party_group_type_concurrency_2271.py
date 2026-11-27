# SPDX-License-Identifier: Apache-2.0

"""#2271: cambio de tipo de grupo y asignaci?n no deben cruzarse."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Party, PartyGroup, database
from cacao_accounting.party_management import _lock_party_group_for_write, apply_party_group


def _app(tmp_path, name):
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / name}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "test-2271",
        }
    )


def test_assignment_serializes_with_group_type_change(tmp_path):
    """La asignaci?n y el cambio de tipo no pueden producir estado incompatible."""
    app = _app(tmp_path, "2271-race.sqlite")
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        group = PartyGroup(group_type="customer", name=f"G-{suffix}", is_active=True)
        party = Party(code=f"P-{suffix}", name="Cliente", is_customer=True, is_supplier=False)
        database.session.add_all([group, party])
        database.session.commit()
        group_id, party_id = group.id, party.id
        database.session.remove()

    assign_locked = Barrier(2, timeout=10)
    release_assign = Barrier(2, timeout=10)

    def assign_customer() -> str:
        with app.app_context():
            try:
                _lock_party_group_for_write(group_id)
                assign_locked.wait()
                p = database.session.get(Party, party_id)
                apply_party_group(p, group_id, role="customer")
                database.session.flush()
                release_assign.wait()
                database.session.commit()
                return "assigned"
            except Exception:
                database.session.rollback()
                raise
            finally:
                database.session.remove()

    def change_to_supplier() -> str:
        assign_locked.wait()
        with app.app_context():
            try:
                _lock_party_group_for_write(group_id)
                g = database.session.get(PartyGroup, group_id, with_for_update=True)
                incompatible = database.session.execute(
                    database.select(Party.id).where(
                        Party.party_group_id == g.id,
                        database.or_(Party.is_supplier.is_(False), Party.is_customer.is_(True)),
                    )
                ).first()
                if incompatible:
                    database.session.rollback()
                    return "blocked"
                g.group_type = "supplier"
                database.session.commit()
                return "changed"
            except Exception:
                database.session.rollback()
                raise
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_assign = ex.submit(assign_customer)
        fut_change = ex.submit(change_to_supplier)
        # Let change attempt proceed once assignment holds lock; release assignment after change waits.
        release_assign.wait()
        assert fut_assign.result(timeout=20) == "assigned"
        assert fut_change.result(timeout=20) == "blocked"

    with app.app_context():
        g = database.session.get(PartyGroup, group_id)
        p = database.session.get(Party, party_id)
        assert g.group_type == "customer"
        assert p.party_group_id == group_id
        database.session.remove()


def test_type_change_serializes_before_incompatible_assignment(tmp_path):
    """Si el tipo cambia primero, la asignaci?n posterior ve el tipo vigente y falla."""
    app = _app(tmp_path, "2271-race2.sqlite")
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        group = PartyGroup(group_type="customer", name=f"G2-{suffix}", is_active=True)
        party = Party(code=f"P2-{suffix}", name="Cliente", is_customer=True, is_supplier=False)
        database.session.add_all([group, party])
        database.session.commit()
        group_id, party_id = group.id, party.id
        database.session.remove()

    change_locked = Barrier(2, timeout=10)
    release_change = Barrier(2, timeout=10)

    def change_to_supplier() -> str:
        with app.app_context():
            try:
                _lock_party_group_for_write(group_id)
                g = database.session.get(PartyGroup, group_id, with_for_update=True)
                incompatible = database.session.execute(
                    database.select(Party.id).where(
                        Party.party_group_id == g.id,
                        database.or_(Party.is_supplier.is_(False), Party.is_customer.is_(True)),
                    )
                ).first()
                assert incompatible is None
                g.group_type = "supplier"
                g.name = g.name
                database.session.flush()
                change_locked.wait()
                release_change.wait()
                database.session.commit()
                return "changed"
            except Exception:
                database.session.rollback()
                raise
            finally:
                database.session.remove()

    def assign_customer() -> str:
        change_locked.wait()
        with app.app_context():
            try:
                p = database.session.get(Party, party_id)
                apply_party_group(p, group_id, role="customer")
                database.session.commit()
                return "assigned"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_change = ex.submit(change_to_supplier)
        fut_assign = ex.submit(assign_customer)
        release_change.wait()
        assert fut_change.result(timeout=20) == "changed"
        assert fut_assign.result(timeout=20) == "rejected"

    with app.app_context():
        g = database.session.get(PartyGroup, group_id)
        p = database.session.get(Party, party_id)
        assert g.group_type == "supplier"
        assert p.party_group_id is None
        database.session.remove()


def test_apply_party_group_rejects_incompatible_type(tmp_path):
    """La asignaci?n con bloqueo rechaza grupo incompatible y no muta."""
    app = _app(tmp_path, "2271-compat.sqlite")
    with app.app_context():
        database.create_all()
        group = PartyGroup(group_type="supplier", name="Sup", is_active=True)
        party = Party(code="C1", name="Cliente", is_customer=True, is_supplier=False)
        database.session.add_all([group, party])
        database.session.commit()
        with pytest.raises(ValueError):
            apply_party_group(party, group.id, role="customer")
        database.session.rollback()
        refreshed = database.session.get(Party, party.id)
        assert refreshed.party_group_id is None
        database.session.remove()
