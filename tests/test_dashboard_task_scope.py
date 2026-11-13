# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance del dashboard, la portada y la bandeja de tareas.

Escenas de negocio (#1600/#1558/#1608 y #1595/#1572/#1598, consolidación
#1649): el dashboard exige permiso de consulta (no solo `access`), la
portada no serializa períodos de compañías ajenas, la bandeja de tareas
respeta el alcance vigente tras revocar compañías y el selector de
asignaciones no revela el directorio global de usuarios.
"""

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CONTRASENA = "dash-tasks-scope-2026"


@pytest.fixture
def dashboard_cloud():
    """Cloud de dos compañías con usuarios de roles calibrados y tareas."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import (
            AccountingPeriod,
            Currency,
            DocumentTask,
            Entity,
            Modules,
            Roles,
            RolesAccess,
            User,
            UserCompanyAccess,
        )
        from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="secreta",
                    name="Compañía Secreta",
                    company_name="Compañía Secreta SA",
                    tax_id="J0009",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                AccountingPeriod(
                    entity="cacao",
                    name="PERIODO-CACAO-10",
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    is_closed=False,
                    enabled=True,
                    status="open",
                ),
                AccountingPeriod(
                    entity="secreta",
                    name="PERIODO-SECRET-10",
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    is_closed=False,
                    enabled=True,
                    status="open",
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        database.session.commit()

        # Rol con access=True pero view=False en contabilidad (#1600).
        rol_lector = Roles(name="revisor", note="Acceso sin consulta")
        database.session.add(rol_lector)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=rol_lector.id,
                module_id=obtener_id_modulo_por_nombre("accounting"),
                access=True,
                update=False,
                set_null=False,
                approve=False,
                bi=False,
                close=False,
                setup=False,
                view=False,
                create=False,
                edit=False,
                delete=False,
                import_=False,
                report=False,
                request=False,
                validate=False,
            )
        )

        # Usuarios del escenario.
        vendedor = User(id="vendedor", user="vendedor", name="Vendedor", password=proteger_passwd(CONTRASENA), active=True)
        revisor = User(id="revisor", user="revisor", name="Revisor", password=proteger_passwd(CONTRASENA), active=True)
        asignador = User(id="asignador", user="asignador", name="Asignador", password=proteger_passwd(CONTRASENA), active=True)
        global_ver = User(
            id="otraempresa",
            user="otraempresa",
            name="Usuario Otra Empresa",
            password=proteger_passwd(CONTRASENA),
            active=True,
        )
        ejemplar = User(id="colega", user="colega", name="Colega Cacao", password=proteger_passwd(CONTRASENA), active=True)
        database.session.add_all([vendedor, revisor, asignador, global_ver, ejemplar])
        database.session.commit()
        database.session.add_all(
            [
                UserCompanyAccess(user_id="vendedor", company_code="cacao"),
                UserCompanyAccess(user_id="revisor", company_code="cacao"),
                UserCompanyAccess(user_id="asignador", company_code="cacao"),
                UserCompanyAccess(user_id="colega", company_code="cacao"),
            ]
        )
        database.session.commit()
        asigna_rol_a_usuario("vendedor", "sales_auxiliar")
        asigna_rol_a_usuario("revisor", "revisor")
        asigna_rol_a_usuario("asignador", "sales_auxiliar")
        asigna_rol_a_usuario("otraempresa", "sales_auxiliar")

        # Tareas del asignador en ambas compañías para la bandeja (#1595).
        database.session.add_all(
            [
                DocumentTask(
                    document_type="sales_invoice",
                    document_id="DOC-1036",
                    document_no="INV-1036",
                    company="cacao",
                    title="Revisar cobro",
                    assigned_by="asignador",
                    assigned_to="asignador",
                    status="open",
                ),
                DocumentTask(
                    document_type="sales_invoice",
                    document_id="DOC-SECRETA",
                    document_no="INV-SECRET",
                    company="secreta",
                    title="Tarea de compañia secreta",
                    assigned_by="asignador",
                    assigned_to="asignador",
                    status="open",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    assert client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True).status_code == 200


def test_dashboard_exige_consulta_no_solo_access(dashboard_cloud):
    """#1600: un rol con access pero sin view no consulta el dashboard."""
    application = dashboard_cloud
    client = application.test_client()
    _iniciar(client, "revisor")
    response = client.get("/api/dashboard/data?company=cacao")
    assert response.status_code in {403, 401}


def test_dashboard_consulta_para_usuario_con_vista(dashboard_cloud):
    """Control positivo: ventas_auxiliar con consultar accede a su compañía."""
    application = dashboard_cloud
    client = application.test_client()
    _iniciar(client, "vendedor")
    response = client.get("/api/dashboard/data?company=cacao")
    assert response.status_code == 200
    assert b"cacao" in response.data


def test_portada_no_serializa_periodos_ajenos(dashboard_cloud):
    """#1558/#1608: el HTML de la portada solo incluye períodos del alcance."""
    application = dashboard_cloud
    client = application.test_client()
    _iniciar(client, "vendedor")
    response = client.get("/app")
    texto = response.get_data(as_text=True)
    assert "PERIODO-CACAO-10" in texto
    assert "PERIODO-SECRET-10" not in texto


def test_bandeja_respeta_el_alcance_vigente(dashboard_cloud):
    """#1595/#1572: al revocar la compañía, sus tareas salen de la bandeja."""
    application = dashboard_cloud
    client = application.test_client()
    _iniciar(client, "asignador")
    response = client.get("/tasks/my")
    texto = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Revisar cobro" in texto
    assert "Tarea de compañia secreta" not in response.get_data(as_text=True)


def test_contador_de_tareas_respeta_el_alcance_vigente(dashboard_cloud):
    """El badge de navegación no cuenta tareas de compañías fuera del alcance."""
    application = dashboard_cloud
    from flask_login import login_user

    from cacao_accounting import current_user_open_task_count
    from cacao_accounting.database import User, database

    with application.test_request_context("/app"):
        user = database.session.execute(database.select(User).filter_by(user="asignador")).scalar_one()
        login_user(user)
        assert current_user_open_task_count() == 1

    with application.app_context():
        from cacao_accounting.database import UserCompanyAccess

        acceso = database.session.execute(
            database.select(UserCompanyAccess).filter_by(user_id="asignador", company_code="cacao")
        ).scalar_one()
        database.session.delete(acceso)
        database.session.commit()

    with application.test_request_context("/app"):
        user = database.session.execute(database.select(User).filter_by(user="asignador")).scalar_one()
        login_user(user)
        assert current_user_open_task_count() == 0


def test_selector_de_asignaciones_no_revela_directorio_global(dashboard_cloud):
    """#1598: el selector expone solo usuarios del alcance de compañía."""
    application = dashboard_cloud
    from flask_login import login_user

    with application.test_request_context("/tasks/my"):
        from cacao_accounting.collaboration_service import active_users
        from cacao_accounting.database import User, database
        from cacao_accounting.company_context import authorized_company_codes

        user = database.session.execute(database.select(User).filter_by(user="asignador")).scalar_one()
        login_user(user)
        alcance = authorized_company_codes()
        usuarios = [u.user for u in active_users(companies=alcance)]
    assert "asignador" in usuarios
    assert "colega" in usuarios
    assert "otraempresa" not in usuarios
