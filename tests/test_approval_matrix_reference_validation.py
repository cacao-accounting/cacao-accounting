# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1995: la matriz de aprobación valida sus referencias antes de persistir.

Una regla con rol/usuario inexistente, sin receptor, con tipo de documento
desconocido o con compañía inexistente debe mostrar un error controlado y no
dejar filas ni provocar HTTP 500. La regla válida sí se guarda.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import APPROVAL_SUBMIT_DOCTYPES
from cacao_accounting.database import ApprovalMatrix, Modules, Roles, User, database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="La matriz de aprobación no aplica en modo escritorio.",
)


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
        "document_type": "purchase_order",
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
    tipo = "purchase_order"

    response = authenticated_client("admin").post(
        "/settings/approval-matrix",
        data=_payload(document_type=tipo, role_id=role_id),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Regla de aprobación creada correctamente." in response.get_data(as_text=True)
    reglas = _reglas(app, role_id=role_id, document_type=tipo)
    assert len(reglas) == 1


def test_tipo_registrado_sin_despacho_no_crea_regla(app, authenticated_client, matriz_entorno, monkeypatch):
    """Un tipo futuro sin implementación se rechaza aunque exista en el registro."""
    monkeypatch.setitem(DOCUMENT_TYPES, "bank_transaction", SimpleNamespace(label="Transacción bancaria"))
    role_id, _user_id = matriz_entorno
    antes = len(_reglas(app))

    response = authenticated_client("admin").post(
        "/settings/approval-matrix",
        data=_payload(document_type="bank_transaction", role_id=role_id),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "El motor de aprobación no tiene flujo de envío para el tipo de documento bank_transaction." in response.get_data(
        as_text=True
    )
    assert len(_reglas(app)) == antes


def test_selector_solo_ofrece_tipos_con_despacho(app, authenticated_client, matriz_entorno, monkeypatch):
    """El formulario no ofrece tipos que dejarían una solicitud sin acción posible."""
    monkeypatch.setitem(DOCUMENT_TYPES, "bank_transaction", SimpleNamespace(label="Transacción bancaria"))
    response = authenticated_client("admin").get("/settings/approval-matrix?company=cacao")
    cuerpo = response.get_data(as_text=True)

    assert response.status_code == 200
    for doctype in APPROVAL_SUBMIT_DOCTYPES:
        assert f'<option value="{doctype}">' in cuerpo
    assert '<option value="bank_transaction">' not in cuerpo


def test_regla_historica_sin_despacho_no_se_puede_habilitar(app, authenticated_client, matriz_entorno):
    """Una regla legada se muestra y puede deshabilitarse, pero no reactivarse."""
    role_id, _user_id = matriz_entorno
    with app.app_context():
        regla = ApprovalMatrix(
            company_id="cacao",
            document_type="bank_transaction",
            role_id=role_id,
            min_amount=0,
            approval_level=1,
            enabled=False,
        )
        database.session.add(regla)
        database.session.commit()
        regla_id = regla.id

    client = authenticated_client("admin")
    response = client.post(
        "/settings/approval-matrix?company=cacao",
        data={"action": "toggle_rule", "rule_id": regla_id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "El motor de aprobación no tiene flujo de envío para el tipo de documento bank_transaction." in response.get_data(
        as_text=True
    )
    assert _reglas(app, id=regla_id)[0].enabled is False

    with app.app_context():
        database.session.get(ApprovalMatrix, regla_id).enabled = True
        database.session.commit()
    response = client.post(
        "/settings/approval-matrix?company=cacao",
        data={"action": "toggle_rule", "rule_id": regla_id},
        follow_redirects=True,
    )
    assert "Regla de aprobación deshabilitada." in response.get_data(as_text=True)
    assert _reglas(app, id=regla_id)[0].enabled is False
