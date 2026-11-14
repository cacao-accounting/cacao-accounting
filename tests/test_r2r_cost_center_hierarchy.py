# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cost center edits preserve the parent-child hierarchy contract."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.services import (
    _cost_center_descendant_codes,
    _lock_cost_center,
    _validate_cost_center_parent,
)
from cacao_accounting.database import CostCenter, Currency, Entity, Modules, database


@pytest.fixture
def cost_center_hierarchy(app):
    """Provide a real group center and a child in the same company."""
    with app.app_context():
        suffix = uuid4().hex[:7].upper()
        parent = CostCenter(
            entity="cacao",
            code=f"G{suffix}",
            name="Grupo de gastos",
            active=True,
            enabled=True,
            group=True,
        )
        child = CostCenter(
            entity="cacao",
            code=f"C{suffix}",
            name="Centro operativo",
            active=True,
            enabled=True,
            group=False,
            parent=parent.code,
        )
        database.session.add_all([parent, child])
        accounting_module = database.session.execute(
            database.select(Modules).filter_by(module="accounting")
        ).scalar_one_or_none()
        if accounting_module is None:
            accounting_module = Modules(module="accounting", default=True, enabled=True)
            database.session.add(accounting_module)
            was_enabled = True
        else:
            was_enabled = accounting_module.enabled
            accounting_module.enabled = True
        database.session.commit()
        scenario = (parent.code, child.code, parent.id, was_enabled)

    yield scenario

    with app.app_context():
        parent_code, child_code, _parent_id, was_enabled = scenario
        accounting_module = database.session.execute(
            database.select(Modules).filter_by(module="accounting")
        ).scalar_one_or_none()
        if accounting_module is not None:
            accounting_module.enabled = was_enabled
        child = database.session.execute(
            database.select(CostCenter).filter_by(entity="cacao", code=child_code)
        ).scalar_one_or_none()
        parent = database.session.execute(
            database.select(CostCenter).filter_by(entity="cacao", code=parent_code)
        ).scalar_one_or_none()
        if child:
            database.session.delete(child)
        if parent:
            database.session.delete(parent)
        database.session.commit()


def test_parent_hierarchy_changes_are_rejected_and_child_remains_editable(app, authenticated_client, cost_center_hierarchy):
    """Reject invalid parent changes, then allow normal edits to the child."""
    parent_code, child_code, parent_id, _was_enabled = cost_center_hierarchy
    client = authenticated_client()

    response = client.post(
        f"/accounting/costs_center/{parent_code}/edit",
        data={"id": parent_code, "nombre": "Grupo de gastos", "entidad": "cacao", "activo": "y"},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    with app.app_context():
        parent = database.session.execute(database.select(CostCenter).filter_by(entity="cacao", code=parent_code)).scalar_one()
        assert parent.group is True

    company_response = client.post(
        f"/accounting/costs_center/{parent_code}/edit",
        data={
            "id": parent_code,
            "nombre": "Grupo de gastos",
            "entidad": "alpha",
            "activo": "y",
            "grupo": "y",
        },
    )

    assert company_response.status_code == 200
    with app.app_context():
        parent = database.session.execute(database.select(CostCenter).filter_by(entity="cacao", code=parent_code)).scalar_one()
        assert parent.group is True
        assert parent.entity == "cacao"

    child_response = client.post(
        f"/accounting/costs_center/{child_code}/edit",
        data={
            "id": child_code,
            "nombre": "Centro operativo actualizado",
            "entidad": "cacao",
            "activo": "y",
            "padre": str(parent_id),
        },
    )

    assert child_response.status_code == 302
    with app.app_context():
        child = database.session.execute(database.select(CostCenter).filter_by(entity="cacao", code=child_code)).scalar_one()
        assert child.name == "Centro operativo actualizado"
        assert child.parent == parent_code


def test_cost_center_with_children_cannot_be_deleted(app, authenticated_client, cost_center_hierarchy):
    """Keep the parent row while child centers still reference its code."""
    parent_code, child_code, _parent_id, _was_enabled = cost_center_hierarchy
    response = authenticated_client().post(f"/accounting/costs_center/{parent_code}/delete")

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        parent = database.session.execute(
            database.select(CostCenter).filter_by(entity="cacao", code=parent_code)
        ).scalar_one_or_none()
        child = database.session.execute(
            database.select(CostCenter).filter_by(entity="cacao", code=child_code)
        ).scalar_one_or_none()
        assert parent is not None and parent.group is True
        assert child is not None and child.parent == parent_code


@pytest.mark.database
def test_concurrent_cross_reparenting_cannot_create_a_cycle():
    """Concurrent moves of separate branches cannot create a cyclic cost center tree."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if configured_uri.startswith("sqlite"):
        pytest.skip("Este caso requiere locking reads de PostgreSQL o MySQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    suffix = uuid4().hex[:6].upper()
    company_code = f"H{suffix}"
    currency_code = f"H{suffix}"
    center_codes = {name: f"{name}{suffix}" for name in ("A", "B", "C", "D")}
    center_ids: dict[str, str] = {}

    with app.app_context():
        database.create_all()
        currency = Currency(code=currency_code, name="Moneda jerarquía", decimals=2, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa jerarquía {suffix}",
            company_name=f"Empresa jerarquía {suffix} SA",
            tax_id=f"J{suffix}",
            currency=currency_code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        centers = {
            "A": CostCenter(
                entity=company_code, code=center_codes["A"], name="Grupo A", group=True, active=True, enabled=True
            ),
            "B": CostCenter(
                entity=company_code,
                code=center_codes["B"],
                name="Grupo B",
                group=True,
                active=True,
                enabled=True,
                parent=center_codes["A"],
            ),
            "C": CostCenter(
                entity=company_code, code=center_codes["C"], name="Grupo C", group=True, active=True, enabled=True
            ),
            "D": CostCenter(
                entity=company_code,
                code=center_codes["D"],
                name="Grupo D",
                group=True,
                active=True,
                enabled=True,
                parent=center_codes["C"],
            ),
        }
        database.session.add_all(centers.values())
        database.session.commit()
        center_ids = {name: center.id for name, center in centers.items()}

    first_validated = Event()
    second_attempted = Event()
    second_validated = Event()
    release_first = Event()
    allow_second_commit = Event()
    first_committed = Event()

    def move_center(source: str, target: str) -> str:
        with app.app_context():
            try:
                center = _lock_cost_center(company_code, center_codes[source])
                assert center is not None
                new_parent = _validate_cost_center_parent(
                    company_code,
                    center_ids[target],
                    current_code=center_codes[source],
                )
                stale_validation = not first_committed.is_set()
                if source == "A":
                    first_validated.set()
                    assert release_first.wait(timeout=10)
                else:
                    second_validated.set()
                    assert allow_second_commit.wait(timeout=10)
                    if stale_validation:
                        return "validated_before_first_commit"
                center.parent = new_parent
                database.session.commit()
                if source == "A":
                    first_committed.set()
                return "moved"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    def move_second_branch() -> str:
        second_attempted.set()
        return move_center("C", "B")

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            move_first = workers.submit(move_center, "A", "D")
            assert first_validated.wait(timeout=10)
            move_second = workers.submit(move_second_branch)
            assert second_attempted.wait(timeout=10)
            validated_before_first_commit = second_validated.wait(timeout=0.5)
            release_first.set()
            assert move_first.result(timeout=10) == "moved"
            allow_second_commit.set()
            second_outcome = move_second.result(timeout=10)

        with app.app_context():
            assert validated_before_first_commit is False
            assert second_outcome == "rejected"
            for center_code in center_codes.values():
                assert center_code not in _cost_center_descendant_codes(company_code, center_code)
    finally:
        release_first.set()
        allow_second_commit.set()
        with app.app_context():
            database.session.rollback()
            for center in database.session.execute(database.select(CostCenter).filter_by(entity=company_code)).scalars():
                database.session.delete(center)
            database.session.delete(company)
            database.session.flush()
            database.session.delete(currency)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
