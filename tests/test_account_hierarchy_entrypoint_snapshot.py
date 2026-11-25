# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2139: los puntos de entrada reales ven el estado confirmado tras el lock.

Las regresiones de helpers demostraron el ``FOR UPDATE`` de las consultas,
pero no que la ruta HTTP de alta/edición ni el adaptador de importación lo
cableen. Aquí se establece un snapshot anterior al lock y se confirma la
operación rival antes de que continúe la petición o la persistencia.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import routes as contabilidad_routes
from cacao_accounting.database import Accounts, Currency, Entity, Modules, User, database
from cacao_accounting.default_scope import lock_default_scope
from cacao_accounting.imports.adapters import chart_of_accounts

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
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def _sembrar(app, company: str, parent_code: str) -> tuple[str, str]:
    """Siembra compañía, usuario administrador y cuenta padre de grupo."""
    sufijo = uuid4().hex[:6]
    user_id = f"admin-{sufijo}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True))
            database.session.flush()
        database.session.add(
            Entity(code=company, name="Cacao", company_name="Cacao SA", tax_id=f"J-{sufijo}", currency="NIO", enabled=True)
        )
        if database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one_or_none() is None:
            database.session.add(Modules(module="accounting", default=False, enabled=True))
        database.session.add(
            User(
                id=user_id,
                user=f"admin-{sufijo}",
                name="Administrador",
                password=b"x",
                active=True,
                classification="admin",
            )
        )
        database.session.flush()
        database.session.add(Accounts(entity=company, code=parent_code, name="Grupo", group=True, active=True, enabled=True))
        database.session.commit()
        parent_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity=company, code=parent_code)
        ).scalar_one()
    return user_id, parent_id


def _cliente(app, user_id: str):
    """Devuelve un cliente autenticado como administrador de la prueba."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _cerrar(app) -> None:
    """Libera la sesión y el pool de la aplicación aislada."""
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _confirmar_hija(app, company: str, parent_code: str, child_code: str, snapshot: Event, confirmado: Event) -> None:
    """Confirma una hija bajo el lock compartido de jerarquía."""
    with app.app_context():
        try:
            assert snapshot.wait(timeout=15)
            lock_default_scope("account_hierarchy", company)
            database.session.add(
                Accounts(
                    entity=company,
                    code=child_code,
                    name="Hija Concurrente",
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


def _confirmar_democion(app, company: str, parent_code: str, snapshot: Event, confirmado: Event) -> None:
    """Confirma la democión del padre bajo el lock compartido de jerarquía."""
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


def _cuenta(app, company: str, code: str):
    """Devuelve la cuenta indicada en una sesión independiente."""
    with app.app_context():
        try:
            return database.session.execute(
                database.select(Accounts).filter_by(entity=company, code=code)
            ).scalar_one_or_none()
        finally:
            database.session.remove()


def test_edicion_ve_hija_confirmada_durante_su_snapshot(monkeypatch):
    """El POST de edición rechaza demover un padre con hija ya confirmada."""
    app = _preparar_app(_motor_externo())
    sufijo = uuid4().hex[:6].upper()
    company = f"AC-{sufijo}"
    parent_code = f"PARENT-{sufijo}"
    child_code = f"CHILD-{sufijo}"
    user_id, parent_id = _sembrar(app, company, parent_code)
    snapshot = Event()
    confirmado = Event()
    validar = contabilidad_routes._validate_active_entity_submission

    def con_snapshot(entity):
        """Fija el snapshot de la petición antes de adquirir el lock."""
        validar(entity)
        database.session.execute(database.select(Accounts).filter_by(entity=company, code=parent_code)).scalar_one()
        snapshot.set()
        assert confirmado.wait(timeout=15)

    monkeypatch.setattr(contabilidad_routes, "_validate_active_entity_submission", con_snapshot)
    try:
        cliente = _cliente(app, user_id)
        with ThreadPoolExecutor(max_workers=2) as workers:
            rival = workers.submit(_confirmar_hija, app, company, parent_code, child_code, snapshot, confirmado)
            respuesta = cliente.post(
                f"/accounting/account/{parent_id}/edit",
                data={
                    "code": parent_code,
                    "name": "Demovida",
                    "entidad": company,
                    "activo": "y",
                },
            )
            rival.result(timeout=30)
        assert respuesta.status_code == 200
        padre = _cuenta(app, company, parent_code)
        assert padre.group is True
        assert padre.name == "Grupo"
        assert _cuenta(app, company, child_code) is not None
    finally:
        snapshot.set()
        confirmado.set()
        _cerrar(app)


def test_alta_ve_democion_confirmada_durante_su_snapshot(monkeypatch):
    """El POST de alta rechaza una hija cuyo padre se demueve antes del lock."""
    app = _preparar_app(_motor_externo())
    sufijo = uuid4().hex[:6].upper()
    company = f"AC-{sufijo}"
    parent_code = f"PARENT-{sufijo}"
    child_code = f"CHILD-{sufijo}"
    user_id, _ = _sembrar(app, company, parent_code)
    snapshot = Event()
    confirmado = Event()
    validar = contabilidad_routes._validate_active_entity_submission

    def con_snapshot(entity):
        """Fija el snapshot de la petición antes de adquirir el lock."""
        validar(entity)
        database.session.execute(database.select(Accounts).filter_by(entity=company, code=parent_code)).scalar_one()
        snapshot.set()
        assert confirmado.wait(timeout=15)

    monkeypatch.setattr(contabilidad_routes, "_validate_active_entity_submission", con_snapshot)
    try:
        cliente = _cliente(app, user_id)
        with ThreadPoolExecutor(max_workers=2) as workers:
            rival = workers.submit(_confirmar_democion, app, company, parent_code, snapshot, confirmado)
            respuesta = cliente.post(
                "/accounting/account/new",
                data={
                    "code": child_code,
                    "name": "Hija Concurrente",
                    "entidad": company,
                    "padre": parent_code,
                    "clasificacion": "asset",
                    "activo": "y",
                },
            )
            rival.result(timeout=30)
        assert respuesta.status_code == 200
        assert _cuenta(app, company, child_code) is None
        padre = _cuenta(app, company, parent_code)
        assert padre.group is False
    finally:
        snapshot.set()
        confirmado.set()
        _cerrar(app)


def test_importacion_ve_democion_confirmada_durante_su_snapshot(monkeypatch):
    """El adaptador real revalida el padre confirmado tras su snapshot."""
    app = _preparar_app(_motor_externo())
    sufijo = uuid4().hex[:6].upper()
    company = f"AC-{sufijo}"
    parent_code = f"PARENT-{sufijo}"
    child_code = f"CHILD-{sufijo}"
    _sembrar(app, company, parent_code)
    snapshot = Event()
    confirmado = Event()
    adquirir = chart_of_accounts.lock_default_scope

    def con_snapshot(categoria, *partes):
        """Fija el snapshot de la importación antes de adquirir el lock."""
        database.session.execute(database.select(Accounts).filter_by(entity=company, code=parent_code)).scalar_one()
        snapshot.set()
        assert confirmado.wait(timeout=15)
        adquirir(categoria, *partes)

    monkeypatch.setattr(chart_of_accounts, "lock_default_scope", con_snapshot)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            rival = workers.submit(_confirmar_democion, app, company, parent_code, snapshot, confirmado)
            with app.app_context():
                hija = Accounts(entity=company, code=child_code, name="Hija", parent=parent_code, group=False)
                with pytest.raises(ValueError, match="cuenta de grupo"):
                    chart_of_accounts.ChartOfAccountsAdapter().persist_document(hija)
                database.session.rollback()
            rival.result(timeout=30)
        assert _cuenta(app, company, child_code) is None
        padre = _cuenta(app, company, parent_code)
        assert padre.group is False
    finally:
        snapshot.set()
        confirmado.set()
        _cerrar(app)
