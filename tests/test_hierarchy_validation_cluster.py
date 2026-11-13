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
from sqlalchemy.exc import IntegrityError
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
            ]
        )
        database.session.flush()
        database.session.add(
            Accounts(
                entity="cacao",
                code="1100",
                name="Cuentas de activo",
                group=True,
                active=True,
                enabled=True,
            )
        )
        database.session.flush()
        database.session.add(
            Accounts(
                entity="cacao",
                code="1101",
                name="Caja",
                group=False,
                active=True,
                enabled=True,
                parent="1100",
            )
        )
        database.session.commit()
    return application


def _cliente(application, user_id="admin"):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
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
                check_hierarchy_cycle(Project, None, "NO-EXISTE", entity="cacao")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def _crear_padres_de_otra_entidad(application):
    """Crea una entidad y un padre de cada tipo para probar el límite jerárquico."""
    with application.app_context():
        database.session.add(
            Entity(
                code="secret",
                name="Secret",
                company_name="Secret SA",
                tax_id="J0002",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        unit = Unit(code="U-SECRET", name="Unidad ajena", entity="secret", status="activo", enabled=True)
        project = Project(code="P-SECRET", name="Proyecto ajeno", entity="secret")
        database.session.add_all([unit, project])
        database.session.commit()
        return unit.id, project.id


def _crear_usuario_con_acceso_a_cacao(application):
    """Crea un usuario contable con alcance únicamente a cacao."""
    from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
    from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
    from cacao_accounting.database import UserCompanyAccess

    with application.app_context():
        database.session.add(User(id="limitado", user="limitado", name="Contable limitado", password=b"x", active=True))
        database.session.add(UserCompanyAccess(user_id="limitado", company_code="cacao"))
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("limitado", "accounting_auxiliar")


def test_alta_de_unidad_rechaza_padre_de_otra_entidad():
    """#1705: una unidad no puede heredar el path de una compañía distinta."""
    application = _crear_app()
    try:
        unit_parent_id, _project_parent_id = _crear_padres_de_otra_entidad(application)
        client = _cliente(application)
        response = client.post(
            "/accounting/unit/new",
            data={
                "id": "U-CHILD",
                "nombre": "Unidad hija",
                "entidad": "cacao",
                "parent_id": unit_parent_id,
                "habilitado": "on",
            },
        )

        assert response.status_code == 200
        assert "Los registros de una jerarquía deben pertenecer a la misma compañía." in response.get_data(as_text=True)
        with application.app_context():
            child = database.session.execute(database.select(Unit).filter_by(code="U-CHILD")).scalar_one_or_none()
            assert child is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_de_unidad_rechaza_padre_de_otra_entidad_sin_mutar_el_hijo():
    """#1705: una edición cross-company debe conservar la jerarquía anterior."""
    application = _crear_app()
    try:
        unit_parent_id, _project_parent_id = _crear_padres_de_otra_entidad(application)
        with application.app_context():
            child = Unit(code="U-CHILD", name="Unidad hija", entity="cacao", status="activo", enabled=True)
            database.session.add(child)
            database.session.commit()
            child_id = child.id

        client = _cliente(application)
        response = client.post(
            "/accounting/unit/U-CHILD/edit",
            data={
                "id": "U-CHILD",
                "nombre": "Cambio rechazado",
                "entidad": "cacao",
                "parent_id": unit_parent_id,
                "habilitado": "on",
            },
        )

        assert response.status_code == 200
        assert "Los registros de una jerarquía deben pertenecer a la misma compañía." in response.get_data(as_text=True)
        with application.app_context():
            child = database.session.get(Unit, child_id)
            assert child is not None
            assert child.parent_id is None
            assert child.name == "Unidad hija"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_alta_de_proyecto_rechaza_padre_de_otra_entidad():
    """#1705: el árbol de proyectos también exige que padre e hijo compartan entidad."""
    application = _crear_app()
    try:
        _unit_parent_id, project_parent_id = _crear_padres_de_otra_entidad(application)
        client = _cliente(application)
        response = client.post(
            "/accounting/project/new",
            data={
                "id": "P-CHILD",
                "nombre": "Proyecto hijo",
                "entidad": "cacao",
                "parent_id": project_parent_id,
                "status": "open",
            },
        )

        assert response.status_code == 200
        assert "Los registros de una jerarquía deben pertenecer a la misma compañía." in response.get_data(as_text=True)
        with application.app_context():
            child = database.session.execute(database.select(Project).filter_by(code="P-CHILD")).scalar_one_or_none()
            assert child is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_de_proyecto_rechaza_padre_de_otra_entidad_sin_mutar_el_hijo():
    """#1705: una edición cross-company conserva el proyecto y padre previos."""
    application = _crear_app()
    try:
        _unit_parent_id, project_parent_id = _crear_padres_de_otra_entidad(application)
        with application.app_context():
            child = Project(code="P-CHILD", name="Proyecto hijo", entity="cacao")
            database.session.add(child)
            database.session.commit()

        client = _cliente(application)
        response = client.post(
            "/accounting/project/P-CHILD/edit",
            data={
                "id": "P-CHILD",
                "nombre": "Cambio rechazado",
                "entidad": "cacao",
                "parent_id": project_parent_id,
                "status": "open",
            },
        )

        assert response.status_code == 200
        assert "Los registros de una jerarquía deben pertenecer a la misma compañía." in response.get_data(as_text=True)
        with application.app_context():
            child = database.session.execute(database.select(Project).filter_by(code="P-CHILD")).scalar_one()
            assert child.parent_id is None
            assert child.name == "Proyecto hijo"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cambiar_entidad_de_unidad_con_hijos_debe_rechazarse():
    """#1705: cambiar la entidad del padre no debe separar la jerarquía existente."""
    application = _crear_app()
    try:
        _crear_padres_de_otra_entidad(application)
        with application.app_context():
            root = Unit(code="U-ROOT", name="Unidad raíz", entity="cacao", status="activo", enabled=True)
            database.session.add(root)
            database.session.flush()
            child = Unit(
                code="U-CHILD",
                name="Unidad hija",
                entity="cacao",
                status="activo",
                enabled=True,
                parent_id=root.id,
            )
            database.session.add(child)
            database.session.commit()
            root_id = root.id

        response = _cliente(application).post(
            "/accounting/unit/U-ROOT/edit",
            data={
                "id": "U-ROOT",
                "nombre": "Raíz editada",
                "entidad": "secret",
                "parent_id": "",
                "habilitado": "on",
            },
        )

        assert response.status_code == 200
        assert "Los registros de una jerarquía deben pertenecer a la misma compañía." in response.get_data(as_text=True)
        with application.app_context():
            root = database.session.get(Unit, root_id)
            child = database.session.execute(database.select(Unit).filter_by(code="U-CHILD")).scalar_one()
            assert root is not None
            assert root.entity == "cacao"
            assert child.entity == "cacao"
            assert child.parent_id == root.id
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cambiar_entidad_de_proyecto_con_hijos_debe_rechazarse():
    """#1705: cambiar la entidad de un proyecto conserva el árbol en la compañía original."""
    application = _crear_app()
    try:
        _crear_padres_de_otra_entidad(application)
        with application.app_context():
            root = Project(code="P-ROOT", name="Proyecto raíz", entity="cacao")
            database.session.add(root)
            database.session.flush()
            child = Project(code="P-CHILD", name="Proyecto hijo", entity="cacao", parent_id=root.id)
            database.session.add(child)
            database.session.commit()

        response = _cliente(application).post(
            "/accounting/project/P-ROOT/edit",
            data={"id": "P-ROOT", "nombre": "Raíz editada", "entidad": "secret", "parent_id": "", "status": "open"},
        )

        assert response.status_code == 200
        assert "Los registros de una jerarquía deben pertenecer a la misma compañía." in response.get_data(as_text=True)
        with application.app_context():
            root = database.session.execute(database.select(Project).filter_by(code="P-ROOT")).scalar_one()
            child = database.session.execute(database.select(Project).filter_by(code="P-CHILD")).scalar_one()
            assert root.entity == "cacao"
            assert child.entity == "cacao"
            assert child.parent_id == root.id
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("node_type", "path", "cacao_parent_code", "secret_parent_code"),
    [
        ("unit", "/accounting/unit/new", "U-CACAO", "U-SECRET"),
        ("project", "/accounting/project/new", "P-CACAO", "P-SECRET"),
    ],
)
def test_selectores_de_padre_solo_exponen_companias_autorizadas(node_type, path, cacao_parent_code, secret_parent_code):
    """#1705/#1649: el formulario no revela padres de una compañía ajena."""
    application = _crear_app()
    try:
        _crear_padres_de_otra_entidad(application)
        with application.app_context():
            database.session.add_all(
                [
                    Unit(code="U-CACAO", name="Unidad de Cacao", entity="cacao", status="activo", enabled=True),
                    Project(code="P-CACAO", name="Proyecto de Cacao", entity="cacao"),
                ]
            )
            database.session.commit()
        _crear_usuario_con_acceso_a_cacao(application)

        response = _cliente(application, user_id="limitado").get(path)
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert secret_parent_code not in page

        client = _cliente(application, user_id="limitado")
        authorized = client.get(f"/accounting/hierarchy/{node_type}/parents?entity=cacao&action=crear")
        unauthorized = client.get(f"/accounting/hierarchy/{node_type}/parents?entity=secret&action=crear")
        assert authorized.status_code == 200
        assert any(cacao_parent_code in option["label"] for option in authorized.get_json())
        assert all(secret_parent_code not in option["label"] for option in authorized.get_json())
        assert unauthorized.status_code == 403
        assert secret_parent_code not in unauthorized.get_data(as_text=True)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("model", [Unit, Project], ids=["unit", "project"])
def test_base_rechaza_insertar_padre_de_otra_entidad(model):
    """La FK compuesta protege la compañía incluso en escrituras ORM directas."""
    application = _crear_app()
    try:
        unit_parent_id, project_parent_id = _crear_padres_de_otra_entidad(application)
        parent_id = unit_parent_id if model is Unit else project_parent_id
        child = model(code="CHILD", name="Hijo", entity="cacao", parent_id=parent_id)
        with application.app_context(), pytest.raises(IntegrityError):
            database.session.add(child)
            database.session.commit()
            database.session.rollback()
    finally:
        with application.app_context():
            database.session.rollback()
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("model", [Unit, Project], ids=["unit", "project"])
def test_base_rechaza_cambiar_entidad_del_padre_con_hijos(model):
    """La FK compuesta evita fracturar el árbol incluso con escrituras ORM directas."""
    application = _crear_app()
    try:
        _crear_padres_de_otra_entidad(application)
        with application.app_context():
            root = model(code="ROOT", name="Raíz", entity="cacao")
            database.session.add(root)
            database.session.flush()
            child = model(code="CHILD", name="Hijo", entity="cacao", parent_id=root.id)
            database.session.add(child)
            database.session.commit()
            root_id = root.id

            root = database.session.get(model, root_id)
            assert root is not None
            root.entity = "secret"
            with pytest.raises(IntegrityError):
                database.session.commit()
            database.session.rollback()
            root = database.session.get(model, root_id)
            assert root is not None
            assert root.entity == "cacao"
    finally:
        with application.app_context():
            database.session.rollback()
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("model", [Unit, Project], ids=["unit", "project"])
def test_base_rechaza_registro_jerarquico_sin_entidad(model):
    """Las dimensiones jerárquicas requieren siempre una compañía."""
    application = _crear_app()
    try:
        record = model(code="NO-ENTITY", name="Sin entidad", entity=None)
        with application.app_context(), pytest.raises(IntegrityError):
            database.session.add(record)
            database.session.commit()
    finally:
        with application.app_context():
            database.session.rollback()
            database.session.remove()
            database.engine.dispose()


def test_commit_hierarchy_change_hace_rollback_si_falla_la_fk_compuesta():
    """Una carrera que viola la FK no confirma cambios parciales ni deja la sesión rota."""
    from cacao_accounting.contabilidad.services import commit_hierarchy_change
    from cacao_accounting.database.helpers import update_hierarchy_attributes

    application = _crear_app()
    try:
        unit_parent_id, _project_parent_id = _crear_padres_de_otra_entidad(application)
        with application.app_context():
            invalid_unit = Unit(code="U-INVALID", name="Unidad inválida", entity="cacao", parent_id=unit_parent_id)
            database.session.add(invalid_unit)
            assert commit_hierarchy_change(lambda: update_hierarchy_attributes(invalid_unit)) is False
            assert database.session.execute(database.select(Unit).filter_by(code="U-INVALID")).scalar_one_or_none() is None
    finally:
        with application.app_context():
            database.session.rollback()
            database.session.remove()
            database.engine.dispose()


def test_alta_con_codigo_duplicado_muestra_conflicto_neutral_y_hace_rollback():
    """Un conflicto de unicidad no se etiqueta erróneamente como cambio jerárquico."""
    application = _crear_app()
    try:
        with application.app_context():
            database.session.add(Unit(code="U-DUP", name="Unidad existente", entity="cacao", enabled=True))
            database.session.commit()

        response = _cliente(application).post(
            "/accounting/unit/new",
            data={"id": "U-DUP", "nombre": "Unidad duplicada", "entidad": "cacao", "parent_id": "", "habilitado": "on"},
        )

        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "No se pudo guardar porque los datos entran en conflicto con otro registro." in page
        assert "jerarquía cambió" not in page
        with application.app_context():
            units = database.session.execute(database.select(Unit).filter_by(code="U-DUP")).scalars().all()
            assert len(units) == 1
    finally:
        with application.app_context():
            database.session.rollback()
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
