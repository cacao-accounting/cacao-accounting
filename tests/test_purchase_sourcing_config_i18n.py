# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1996: el mínimo de ofertas inválido se rechaza con mensaje traducible.

Un POST con un valor no numérico no debe persistir la configuración ni filtrar
el error interno de ``int()``; el formulario siguiente muestra un mensaje de
campo comprensible.
"""

from __future__ import annotations

import pytest

from cacao_accounting.database import CacaoConfig, Modules, database

CLAVE_MINIMO = "PURCHASE_MINIMUM_REQUIRED_OFFERS"
CLAVE_COMPARACION = "PURCHASE_REQUIRE_OFFER_COMPARISON"


@pytest.fixture
def modulo_admin_activo(app):
    """Habilita el módulo administrativo durante la prueba."""
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
    yield
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
            database.session.commit()


def _valores(app) -> dict[str, str | None]:
    """Lee la configuración persistida de abastecimiento."""
    with app.app_context():
        filas = database.session.execute(
            database.select(CacaoConfig).filter(CacaoConfig.key.in_([CLAVE_MINIMO, CLAVE_COMPARACION]))
        ).scalars()
        return {fila.key: fila.value for fila in filas}


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        ("not-a-number", "El mínimo de ofertas debe ser un número entero."),
        ("0", "El mínimo de ofertas debe ser mayor o igual a uno."),
    ],
)
def test_minimo_invalido_no_persiste_y_muestra_mensaje(app, authenticated_client, modulo_admin_activo, valor, mensaje):
    """El valor inválido conserva la configuración y evita el error interno."""
    antes = _valores(app)

    response = authenticated_client("admin").post(
        "/settings/purchase-sourcing",
        data={"require_comparison": "on", "minimum_offers": valor},
        follow_redirects=True,
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert mensaje in cuerpo
    assert "invalid literal for int()" not in cuerpo
    assert _valores(app) == antes
