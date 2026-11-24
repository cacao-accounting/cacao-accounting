# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1995: la matriz de aprobación valida sus referencias antes de persistir.

Una regla con rol/usuario inexistente, sin receptor, con tipo de documento
desconocido o con compañía inexistente debe mostrar un error controlado y no
dejar filas ni provocar HTTP 500. La regla válida sí se guarda.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import ApprovalMatrix, Modules, Roles, User, database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES


@pytest.fixture
def matriz_entorno(app):
    """Habilita admin y crea un rol/usuario exclusivos para la prueba."""
    sufijo = uuid4().hex[:6]
    role_id = None
    user_id = f"matriz-user-{sufijo}"
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            creado = True
        else:
            creado = False
            anterior = modulo.enabled
            modulo.enabled = True
        rol = Roles(name=f"matriz-rol-{sufijo}", note="Receptor de matriz")
        database.session.add(rol)
        database.session.add(
            User(
                id=user_id,
                user=user_id,
                name="Receptor de Matriz",
                password=b"unused",
                active=True,
            )
        )
        database.session.flush()
        role_id = rol.id
        database.session.commit()
    yield role_id, user_id
    with app.app_context():
        database.session.execute(
            database.delete(ApprovalMatrix).where(ApprovalMatrix.company_id == "cacao", ApprovalMatrix.role_id == role_id)
        )
        database.session.execute(database.delete(User).where(User.id == user_id))
        database.session.execute(database.delete(Roles).where(Roles.id == role_id))
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def _payload(**overrides: str) -> dict[str, str]:
    """Cuerpo válido para agregar una regla de aprobación en cacao."""
    data = {
        "action": "add_rule",
        "company": "cacao",
        "document_type": next(iter(DOCUMENT_TYPES)),
        "approval_level": "1",
        "min_amount": "0",
        "max_amount": "",
    }
    data.update(overrides)
    return data


def _reglas(app, **filtros) -> list[ApprovalMatrix]:
    """Lee las reglas persistidas para cacao."""
    with app.app_context():
        consulta = database.select(ApprovalMatrix).filter_by(company_id="cacao", **filtros)
        return list(database.session.execute(consulta).scalars())


@pytest.mark.parametrize(
    ("overrides", "mensaje"),
    [
        ({"role_id": "missing-role"}, "El rol seleccionado no existe."),
        ({"user_id": "missing-user"}, "El usuario seleccionado no existe."),
        ({}, "Seleccione un rol o un usuario para la regla de aprobación."),
        (
            {"document_type": "unsupported_document", "role_id": "__ROLE__"},
            "El tipo de documento de la regla de aprobación no es válido.",
        ),
        ({"company": "missing-company", "role_id": "__ROLE__"}, "La compañía de la regla de aprobación no existe."),
    ],
)
def test_regla_con_referencia_invalida_no_persiste(app, authenticated_client, matriz_entorno, overrides, mensaje):
    """Cada referencia inválida responde con error controlado y sin filas nuevas."""
    role_id, _user_id = matriz_entorno
    antes = len(_reglas(app))
    datos = _payload(**{clave: role_id if valor == "__ROLE__" else valor for clave, valor in overrides.items()})

    response = authenticated_client("admin").post("/settings/approval-matrix", data=datos, follow_redirects=True)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert mensaje in cuerpo
    assert len(_reglas(app)) == antes


def test_regla_valida_persiste(app, authenticated_client, matriz_entorno):
    """El receptor existente y el tipo de documento válido sí crean la regla."""
    role_id, _user_id = matriz_entorno
    tipo = next(iter(DOCUMENT_TYPES))

    response = authenticated_client("admin").post(
        "/settings/approval-matrix",
        data=_payload(document_type=tipo, role_id=role_id),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Regla de aprobación creada correctamente." in response.get_data(as_text=True)
    reglas = _reglas(app, role_id=role_id, document_type=tipo)
    assert len(reglas) == 1
