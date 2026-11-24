# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2139: las lecturas bajo lock ven el estado confirmado de la jerarquía.

MySQL REPEATABLE READ mantiene el snapshot iniciado antes del lock. Sin
``FOR UPDATE``, una transacción puede demover una cuenta padre aunque otra
sesión ya haya confirmado una cuenta hija. Estas pruebas fuerzan ese orden.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.services import _account_descendant_codes, _validate_account_parent
from cacao_accounting.database import Accounts, Currency, Entity, database
from cacao_accounting.default_scope import lock_default_scope

pytestmark = pytest.mark.database


def _motor_externo() -> str:
    """Devuelve la URI externa de CI o omite la prueba en SQLite."""
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        pytest.skip("El snapshot REPEATABLE READ solo se reproduce en MySQL o PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    return uri


def _preparar_app(uri: str):
    """Crea una aplicación aislada con el motor externo indicado."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def _sembrar_padre(app, company: str, parent_code: str) -> None:
    """Siembra la compañía y la cuenta padre de grupo."""
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True))
            database.session.flush()
        database.session.add(
            Entity(code=company, name="Cacao", company_name="Cacao SA", tax_id="J1", currency="NIO", enabled=True)
        )
        database.session.flush()
        database.session.add(Accounts(entity=company, code=parent_code, name="Grupo", group=True, active=True, enabled=True))
        database.session.commit()


def test_hija_confirmada_durante_el_lock_se_ve_con_for_update():
    """Una hija confirmada tras el snapshot bloquea la democión del padre."""
    app = _preparar_app(_motor_externo())
    sufijo = uuid4().hex[:6].upper()
    company = f"AC-{sufijo}"
    parent_code = f"PARENT-{sufijo}"
    child_code = f"CHILD-{sufijo}"
    _sembrar_padre(app, company, parent_code)

    snapshot = Event()
    confirmado = Event()

    def confirmar_hija() -> None:
        with app.app_context():
            try:
                assert snapshot.wait(timeout=15)
                lock_default_scope("account_hierarchy", company)
                database.session.add(
                    Accounts(
                        entity=company,
                        code=child_code,
                        name="Hija",
                        parent=parent_code,
                        group=False,
                        active=True,
                        enabled=True,
                    )
                )
                database.session.commit()
                confirmado.set()
            finally:
                database.session.remove()

    def leer_descendientes() -> set[str]:
        with app.app_context():
            try:
                # Establece el snapshot antes de que la otra sesión confirme la hija.
                database.session.execute(database.select(Accounts).filter_by(entity=company, code=parent_code)).scalar_one()
                snapshot.set()
                assert confirmado.wait(timeout=15)
                lock_default_scope("account_hierarchy", company)
                return _account_descendant_codes(company, parent_code, for_update=True)
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            rival = workers.submit(confirmar_hija)
            lector = workers.submit(leer_descendientes)
            rival.result(timeout=30)
            assert child_code in lector.result(timeout=30)
    finally:
        snapshot.set()
        confirmado.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_democion_confirmada_durante_el_lock_se_ve_con_for_update():
    """Una democión confirmada tras el snapshot se revalida antes de importar."""
    app = _preparar_app(_motor_externo())
    sufijo = uuid4().hex[:6].upper()
    company = f"AC-{sufijo}"
    parent_code = f"PARENT-{sufijo}"
    _sembrar_padre(app, company, parent_code)

    snapshot = Event()
    confirmado = Event()

    def demover_padre() -> None:
        with app.app_context():
            try:
                assert snapshot.wait(timeout=15)
                lock_default_scope("account_hierarchy", company)
                padre = database.session.execute(
                    database.select(Accounts).filter_by(entity=company, code=parent_code)
                ).scalar_one()
                padre.group = False
                database.session.commit()
                confirmado.set()
            finally:
                database.session.remove()

    def revalidar_padre() -> str:
        with app.app_context():
            try:
                # Snapshot previo con group=True.
                database.session.execute(database.select(Accounts).filter_by(entity=company, code=parent_code)).scalar_one()
                snapshot.set()
                assert confirmado.wait(timeout=15)
                lock_default_scope("account_hierarchy", company)
                with pytest.raises(ValueError, match="cuenta de grupo"):
                    _validate_account_parent(company, parent_code, for_update=True)
                return "rechazado"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            rival = workers.submit(demover_padre)
            lector = workers.submit(revalidar_padre)
            rival.result(timeout=30)
            assert lector.result(timeout=30) == "rechazado"
    finally:
        snapshot.set()
        confirmado.set()
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
