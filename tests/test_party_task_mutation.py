# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Mutaciones de terceros y tareas: propiedad y alcance de edición.

Escenas de negocio (#1280/#1282 y #1328/#1467, consolidación #1649): la
configuración por compañía de un tercero exige edición por compañía
(presentes y omitidas), los contactos/roles compartidos exigen edición
del módulo con vínculo autorizado, y el estado de una tarea solo lo
muta su asignado o quien la creó.
"""

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CONTRASENA = "terceros-mutate-2026"


@pytest.fixture
def terceros_mutacion():
    """Cloud de dos compañías con un cliente compartido y tareas asignadas."""
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
            CompanyParty,
            Currency,
            DocumentTask,
            Entity,
            Modules,
            Party,
            User,
            UserCompanyAccess,
        )

        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
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
                User(
                    id="editor",
                    user="editor",
                    name="Editor Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="gerente",
                    user="gerente",
                    name="Gerente Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="lemedor",
                    user="lemedor",
                    name="Lector Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id="editor", company_code="cacao"),
                UserCompanyAccess(user_id="gerente", company_code="cacao"),
                UserCompanyAccess(user_id="lemedor", company_code="cacao"),
                Party(
                    code="CL-SH",
                    is_customer=True,
                    name="Cliente Compartido",
                    tax_id="CL-SH-1",
                    is_active=True,
                ),
                DocumentTask(
                    document_type="sales_invoice",
                    document_id="DOC-1",
                    document_no="INV-1",
                    company="cacao",
                    title="Cobrar al cliente",
                    assigned_by="gerente",
                    assigned_to="editor",
                    status="open",
                    created_by="gerente",
                ),
            ]
        )
        database.session.commit()
        cliente = database.session.execute(database.select(Party).filter_by(code="CL-SH")).scalar_one()
        database.session.add(CompanyParty(company="cacao", party_id=cliente.id, is_active=True))
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        for usuario, rol in (
            ("editor", "sales_auxiliar"),
            ("gerente", "sales_manager"),
            ("lemedor", "sales_user"),
        ):
            asigna_rol_a_usuario(usuario, rol)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    assert client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True).status_code == 200


def _party_id(application) -> str:
    with application.app_context():
        from cacao_accounting.database import Party, database

        return database.session.execute(database.select(Party).filter_by(code="CL-SH")).scalar_one().id


def test_configuracion_rechaza_compania_ajena(terceros_mutacion):
    """#1280: la compañía omitida del alcance responde 403 y no borra filas."""
    application = terceros_mutacion
    id_cliente = _party_id(application)
    client = application.test_client()
    _iniciar(client, "editor")
    response = client.post(
        f"/sales/customer/{id_cliente}/company-settings",
        data={"company": "secreta", "company_is_active": "y"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_configuracion_de_compania_autorizada_cambia(terceros_mutacion):
    """La propia compañía del editor se guarda sin restricción."""
    application = terceros_mutacion
    id_cliente = _party_id(application)
    client = application.test_client()
    _iniciar(client, "editor")
    response = client.post(
        f"/sales/customer/{id_cliente}/company-settings",
        data={"company": "cacao", "company_is_active": "y"},
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_contacto_rechaza_lector_sin_edicion(terceros_mutacion):
    """#1282: un usuario solo de consulta no crea contactos del tercero."""
    application = terceros_mutacion
    id_cliente = _party_id(application)
    client = application.test_client()
    _iniciar(client, "lemedor")
    response = client.post(
        f"/sales/customer/{id_cliente}/contacts",
        data={"name": "Contacto secreto", "email": "x@y.z"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_contacto_crea_para_editor(terceros_mutacion):
    """Control positivo: el editor con vínculo autorizado crea el contacto."""
    application = terceros_mutacion
    id_cliente = _party_id(application)
    client = application.test_client()
    _iniciar(client, "editor")
    response = client.post(
        f"/sales/customer/{id_cliente}/contacts",
        data={"name": "Contacto autorizado", "email": "x@y.z"},
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_estado_de_tarea_rechaza_a_un_ajeno(terceros_mutacion):
    """#1328/#1467: un lector con acceso al documento no complete la tarea."""
    application = terceros_mutacion
    client = application.test_client()
    _iniciar(client, "gerente")
    with application.app_context():
        from cacao_accounting.database import DocumentTask, database

        task_id = database.session.execute(database.select(DocumentTask)).scalar_one().id
    client_ajeno = application.test_client()
    _iniciar(client_ajeno, "lemedor")
    response = client_ajeno.post(f"/api/tasks/{task_id}/status", json={"status": "completed"})
    assert response.status_code in {403, 404}


def test_estado_de_tarea_lo_cambia_el_asignado(terceros_mutacion):
    """Control positivo: el asignado completa su propia tarea."""
    application = terceros_mutacion
    client = application.test_client()
    _iniciar(client, "editor")
    with application.app_context():
        from cacao_accounting.database import DocumentTask, database

        task_id = database.session.execute(database.select(DocumentTask)).scalar_one().id
    response = client.post(f"/api/tasks/{task_id}/status", json={"status": "completed"})
    assert response.status_code == 200
