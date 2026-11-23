# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2188: dos cambios jerárquicos concurrentes no pueden crear un ciclo.

Dos transacciones sobre ramas distintas de la misma compañía validaban su
nuevo padre antes de que la otra confirmara. La validación y la escritura se
serializan por compañía para que la segunda observe el cambio de la primera y
rechace el ciclo.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Unit, database
from cacao_accounting.database.helpers import check_hierarchy_cycle, get_descendant_ids

pytestmark = pytest.mark.database


def test_concurrent_unit_moves_cannot_form_a_cycle():
    """Solo un traslado prospera; el segundo detecta el ciclo tras el lock."""
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
    company_code = f"U{suffix}"
    currency_code = f"U{suffix}"
    codes = {name: f"{name}{suffix}" for name in ("A", "B", "C", "D")}
    ids: dict[str, str] = {}

    with app.app_context():
        database.create_all()
        currency = Currency(code=currency_code, name="Moneda jerarquía", decimals=2, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa jerarquía {suffix}",
            company_name=f"Empresa jerarquía {suffix} SA",
            tax_id=f"U{suffix}",
            currency=currency_code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        units = {
            "A": Unit(entity=company_code, code=codes["A"], name="Grupo A", enabled=True),
            "B": Unit(entity=company_code, code=codes["B"], name="Grupo B", enabled=True),
            "C": Unit(entity=company_code, code=codes["C"], name="Grupo C", enabled=True),
            "D": Unit(entity=company_code, code=codes["D"], name="Grupo D", enabled=True),
        }
        database.session.add_all(units.values())
        database.session.flush()
        units["B"].parent_id = units["A"].id
        units["D"].parent_id = units["C"].id
        database.session.commit()
        ids = {name: unit.id for name, unit in units.items()}

    first_validated = Event()
    second_validated = Event()
    release_first = Event()
    allow_second_commit = Event()
    first_committed = Event()

    def move(source: str, target: str, first: bool) -> str:
        with app.app_context():
            try:
                unit = database.session.get(Unit, ids[source])
                assert unit is not None
                check_hierarchy_cycle(Unit, unit.id, ids[target], entity=company_code)
                if first:
                    first_validated.set()
                    assert release_first.wait(timeout=10)
                else:
                    second_validated.set()
                    if not first_committed.is_set():
                        assert allow_second_commit.wait(timeout=10)
                unit.parent_id = ids[target]
                database.session.commit()
                if first:
                    first_committed.set()
                return "moved"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            move_first = workers.submit(move, "A", "D", True)
            assert first_validated.wait(timeout=10)
            move_second = workers.submit(move, "C", "B", False)
            validated_before_first_commit = second_validated.wait(timeout=0.5)
            release_first.set()
            assert move_first.result(timeout=10) == "moved"
            allow_second_commit.set()
            second_outcome = move_second.result(timeout=10)

        assert validated_before_first_commit is False
        assert second_outcome == "rejected"
        with app.app_context():
            for unit_id in ids.values():
                descendants = get_descendant_ids(Unit, unit_id)
                assert unit_id not in descendants
    finally:
        release_first.set()
        allow_second_commit.set()
        with app.app_context():
            database.session.rollback()
            stored = database.session.execute(database.select(Unit).filter_by(entity=company_code)).scalars().all()
            for unit in stored:
                unit.parent_id = None
            database.session.flush()
            for unit in stored:
                database.session.delete(unit)
            database.session.flush()
            database.session.delete(company)
            database.session.flush()
            database.session.delete(currency)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()


def test_la_enumeracion_de_descendientes_usa_lectura_bloqueante(app, monkeypatch):
    """La validación de ciclos enumera descendientes con FOR UPDATE (#2188)."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        raiz = Unit(entity="cacao", code=f"RA{sufijo}", name="Raíz", enabled=True)
        database.session.add(raiz)
        database.session.flush()
        hijo = Unit(entity="cacao", code=f"HI{sufijo}", name="Hijo", enabled=True, parent_id=raiz.id)
        database.session.add(hijo)
        database.session.flush()
        nieto = Unit(entity="cacao", code=f"NI{sufijo}", name="Nieto", enabled=True, parent_id=hijo.id)
        database.session.add(nieto)
        database.session.commit()
        raiz_id, hijo_id, nieto_id = raiz.id, hijo.id, nieto.id

    capturados: list[object] = []
    original = database.session.execute

    def tracking(statement, *args, **kwargs):
        capturados.append(statement)
        return original(statement, *args, **kwargs)

    monkeypatch.setattr(database.session, "execute", tracking)
    try:
        con_lock = get_descendant_ids(Unit, raiz_id, for_update=True)
        assert capturados and all(getattr(stmt, "_for_update_arg", None) is not None for stmt in capturados)

        capturados.clear()
        sin_lock = get_descendant_ids(Unit, raiz_id)
        assert capturados and all(getattr(stmt, "_for_update_arg", None) is None for stmt in capturados)

        assert set(con_lock) == set(sin_lock) == {hijo_id, nieto_id}
    finally:
        with app.app_context():
            database.session.rollback()
            for unit_id in (nieto_id, hijo_id, raiz_id):
                registro = database.session.get(Unit, unit_id)
                if registro is not None:
                    database.session.delete(registro)
            database.session.commit()
