# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las jerarquías validan formulario, padre existente y democión de grupos.

Escenario de negocio (paraguas #1717):
- #1772: el alta de unidad persistía aunque WTForms fallara.
- #1579: un padre inexistente quedaba como huérfano.
- #2139: una cuenta grupo podía perder el flag teniendo hijas.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    Modules,
    Project,
    Unit,
    User,
    database,
)
from cacao_accounting.database.helpers import check_hierarchy_cycle


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Accounts(
                    entity="cacao",
                    code="1100",
                    name="Cuentas de activo",
                    group=True,
                    active=True,
                    enabled=True,
                ),
                Accounts(
                    entity="cacao",
                    code="1101",
                    name="Caja",
                    group=False,
                    active=True,
                    enabled=True,
                    parent="1100",
                ),
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_unidad_no_persiste_si_el_formulario_falla():
    """#1772: un POST con código/nombre vacíos vuelve al formulario."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/accounting/unit/new",
            data={"id": "", "nombre": "", "entidad": "cacao", "habilitado": "on"},
        )

        assert respuesta.status_code == 200
        with application.app_context():
            assert database.session.execute(database.select(Unit)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("url", ["/accounting/unit/new"])
def test_unidad_rechaza_padre_inexistente(url):
    """#1579: el padre debe existir antes de crear la jerarquía."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            url,
            data={"id": "U001", "nombre": "Unidad", "entidad": "cacao", "parent_id": "NO-EXISTE", "habilitado": "on"},
        )

        assert respuesta.status_code == 200
        assert "El registro padre seleccionado no existe." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(Unit)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_de_unidad_conserva_el_padre_ante_un_id_ajeno():
    """#1579: editar con un padre inexistente no muta la unidad."""
    application = _crear_app()
    try:
        with application.app_context():
            database.session.add(Unit(code="U001", name="Unidad", entity="cacao", status="activo", enabled=True))
            database.session.commit()

        client = _cliente(application)
        respuesta = client.post(
            "/accounting/unit/U001/edit",
            data={"id": "U001", "nombre": "Unidad", "entidad": "cacao", "parent_id": "NO-EXISTE", "habilitado": "on"},
        )

        assert respuesta.status_code == 200
        assert "El registro padre seleccionado no existe." in respuesta.get_data(as_text=True)
        with application.app_context():
            unidad = database.session.execute(database.select(Unit).filter_by(code="U001")).scalar_one()
            assert unidad.parent_id is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_helper_rechaza_padres_inexistentes_en_proyectos():
    """#1579: la misma guardia cubre unit y project."""
    application = _crear_app()
    try:
        with application.app_context():
            database.session.add(Project(code="P1", name="Proyecto", entity="cacao"))
            database.session.commit()
            with pytest.raises(ValueError, match="El registro padre seleccionado no existe."):
                check_hierarchy_cycle(Project, None, "NO-EXISTE")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_no_demueve_una_cuenta_grupo_con_hijas(monkeypatch):
    """#2139: el flag grupo se conserva mientras existan descendientes."""
    application = _crear_app()
    try:
        import importlib

        contabilidad_routes = importlib.import_module("cacao_accounting.contabilidad.routes")
        capturado: list[str] = []
        monkeypatch.setattr(
            contabilidad_routes,
            "flash_error",
            lambda exc, *args, **kwargs: capturado.append(str(exc)),
        )
        client = _cliente(application)
        respuesta = client.post(
            "/accounting/account/cacao/1100/edit",
            data={"code": "1100", "name": "Renombrada", "entidad": "cacao", "activo": "on"},
        )

        assert respuesta.status_code == 200
        assert any("cuentas hijas" in mensaje for mensaje in capturado)
        with application.app_context():
            cuenta = database.session.execute(database.select(Accounts).filter_by(code="1100", entity="cacao")).scalar_one()
            assert cuenta.group is True
            assert cuenta.name == "Cuentas de activo"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
