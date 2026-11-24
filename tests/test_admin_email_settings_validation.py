# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1994: la configuración SMTP se valida en servidor antes de persistirse.

Los controles HTML no protegen la ruta. El servidor debe rechazar servidor,
puerto o remitente inválidos —incluido el remitente vacío que rompe el fallback—
sin guardar una configuración inutilizable ni afirmar éxito.
"""

from __future__ import annotations

import pytest

from cacao_accounting.database import CacaoConfig, Modules, database

CLAVES_SMTP = (
    "smtp_server",
    "smtp_port",
    "smtp_user",
    "smtp_use_tls",
    "smtp_from_email",
    "smtp_password",
    "disable_transaction_emails",
)


def _snapshot(app) -> dict[str, str]:
    """Captura los valores SMTP persistidos antes de la prueba."""
    with app.app_context():
        filas = database.session.execute(database.select(CacaoConfig).where(CacaoConfig.key.in_(CLAVES_SMTP))).scalars()
        return {fila.key: fila.value for fila in filas}


def _restaurar(app, valores: dict[str, str]) -> None:
    """Devuelve las claves SMTP al estado previo."""
    with app.app_context():
        database.session.execute(database.delete(CacaoConfig).where(CacaoConfig.key.in_(CLAVES_SMTP)))
        database.session.add_all([CacaoConfig(key=clave, value=valor) for clave, valor in valores.items()])
        database.session.commit()


@pytest.fixture
def smtp_entorno(app):
    """Habilita admin y restaura las claves SMTP al finalizar."""
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
        database.session.commit()
    previos = _snapshot(app)
    yield
    _restaurar(app, previos)
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
            database.session.commit()


def _payload(**overrides: str) -> dict[str, str]:
    """POST válido base para la configuración SMTP."""
    data = {
        "smtp_server": "smtp.local",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_password": "",
        "smtp_use_tls": "on",
        "smtp_from_email": "noreply@cacao-accounting.com",
        "disable_transaction_emails": "",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    ("overrides", "mensaje"),
    [
        ({"smtp_from_email": ""}, "El correo remitente SMTP es obligatorio."),
        ({"smtp_from_email": "not-an-email"}, "El correo remitente SMTP no es válido."),
        ({"smtp_port": "nope"}, "El puerto SMTP debe ser un número entero entre 1 y 65535."),
        ({"smtp_port": "70000"}, "El puerto SMTP debe ser un número entero entre 1 y 65535."),
        ({"smtp_server": ""}, "El servidor SMTP es obligatorio."),
    ],
)
def test_configuracion_invalida_no_persiste(app, authenticated_client, smtp_entorno, overrides, mensaje):
    """Cada valor inválido muestra su error y conserva la configuración."""
    antes = _snapshot(app)

    response = authenticated_client("admin").post("/settings/email", data=_payload(**overrides), follow_redirects=True)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert mensaje in cuerpo
    assert "Configuración de correo electrónico guardada correctamente." not in cuerpo
    assert _snapshot(app) == antes


def test_configuracion_valida_persiste(app, authenticated_client, smtp_entorno):
    """Un remitente y puerto válidos se guardan normalizados."""
    response = authenticated_client("admin").post("/settings/email", data=_payload(), follow_redirects=True)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Configuración de correo electrónico guardada correctamente." in cuerpo
    with app.app_context():
        valores = {
            fila.key: fila.value
            for fila in database.session.execute(
                database.select(CacaoConfig).where(CacaoConfig.key.in_(CLAVES_SMTP))
            ).scalars()
        }
    assert valores["smtp_server"] == "smtp.local"
    assert valores["smtp_port"] == "587"
    assert valores["smtp_from_email"] == "noreply@cacao-accounting.com"
