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
from threading import Event, local
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Unit, database, helpers
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


def test_las_anclas_se_bloquean_antes_que_los_nodos(monkeypatch):
    """Ninguna transacción retiene un nodo mientras espera el ancla (#2188)."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith("postgresql"):
        pytest.skip("Este caso valida el orden de locks de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    schema_name = f"jerarquia_locks_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri)
    with bootstrap_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    engine_options: Any = {
        "pool_size": 2,
        "max_overflow": 0,
        "connect_args": {"options": f"-csearch_path={schema_name}"},
    }
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": cast(Any, engine_options),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    sufijo = uuid4().hex[:6].upper()
    company_code = f"H{sufijo}"
    currency_code = f"H{sufijo}"
    codes = {name: f"{name}{sufijo}" for name in ("A", "B")}
    ids: dict[str, str] = {}
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code=currency_code, name="Moneda bloqueos", decimals=2, active=True, default=False))
        database.session.add(
            Entity(
                code=company_code,
                name=f"Empresa bloqueos {sufijo}",
                company_name=f"Empresa bloqueos {sufijo} SA",
                tax_id=f"H{sufijo}",
                currency=currency_code,
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        units = {
            "A": Unit(entity=company_code, code=codes["A"], name="Grupo A", enabled=True),
            "B": Unit(entity=company_code, code=codes["B"], name="Grupo B", enabled=True),
        }
        database.session.add_all(units.values())
        database.session.commit()
        ids = {name: unit.id for name, unit in units.items()}

    estado = local()
    node_locks: dict[str, list[str]] = {"first": [], "second": []}
    ancla_primero = Event()
    liberar_primero = Event()
    segundo_en_ancla = Event()
    segundo_salio_ancla = Event()
    original_lock_companies = helpers._lock_hierarchy_companies
    original_fetch_node = helpers._fetch_hierarchy_node_locked

    def tracking_fetch(node_class, node_id):
        """Registra cada lectura bloqueante de un nodo por hilo."""
        node_locks[estado.rol].append(str(node_id))
        return original_fetch_node(node_class, node_id)

    def tracking_anchor(company_codes):
        """Mantiene el ancla del primero y observa al segundo antes de esperar."""
        if estado.rol == "first":
            original_lock_companies(company_codes)
            ancla_primero.set()
            if not liberar_primero.wait(timeout=20):
                raise RuntimeError("El primer traslado no fue liberado a tiempo.")
            return
        segundo_en_ancla.set()
        if node_locks["second"]:
            raise RuntimeError("El nodo se bloqueó antes que el ancla.")
        original_lock_companies(company_codes)
        segundo_salio_ancla.set()

    def move(source: str, target: str, rol: str) -> str:
        estado.rol = rol
        with app.app_context():
            try:
                unit = database.session.get(Unit, ids[source])
                assert unit is not None
                check_hierarchy_cycle(Unit, unit.id, ids[target], entity=company_code, current_entity=company_code)
                unit.parent_id = ids[target]
                database.session.commit()
                return "moved"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    monkeypatch.setattr(helpers, "_lock_hierarchy_companies", tracking_anchor)
    monkeypatch.setattr(helpers, "_fetch_hierarchy_node_locked", tracking_fetch)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            primero = workers.submit(move, "A", "B", "first")
            assert ancla_primero.wait(timeout=15)
            segundo = workers.submit(move, "B", "A", "second")
            assert segundo_en_ancla.wait(timeout=15)
            assert not segundo_salio_ancla.wait(timeout=0.5)
            assert node_locks["second"] == []
            liberar_primero.set()
            assert primero.result(timeout=30) == "moved"
            assert segundo.result(timeout=30) == "rejected"

        with app.app_context():
            moved = database.session.get(Unit, ids["A"])
            assert moved is not None and moved.parent_id == ids["B"]
            root = database.session.get(Unit, ids["B"])
            assert root is not None and root.parent_id is None
    finally:
        liberar_primero.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        bootstrap_engine.dispose()


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
