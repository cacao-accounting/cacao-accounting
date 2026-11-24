# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2002/#2004: la matriz de aprobación distingue el estado y nombra la acción.

Una regla activa y otra inactiva deben renderizar su estado y ofrecer la acción
contraria con un nombre accesible traducible (aria-label/title), no un icono
sin texto.
"""

from __future__ import annotations

import os
import re
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import ApprovalMatrix, Modules, Roles, database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="La matriz de aprobación no aplica en modo escritorio.",
)


@pytest.fixture
def reglas_activas_e_inactivas(app):
    """Habilita admin y crea una regla activa y otra inactiva en cacao."""
    sufijo = uuid4().hex[:6]
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
        rol = Roles(name=f"matriz-render-{sufijo}", note=f"Receptor {sufijo}")
        database.session.add(rol)
        database.session.flush()
        tipo = next(iter(DOCUMENT_TYPES))
        database.session.add_all(
            [
                ApprovalMatrix(
                    company_id="cacao",
                    document_type=tipo,
                    role_id=rol.id,
                    min_amount=Decimal("0"),
                    approval_level=1,
                    enabled=True,
                ),
                ApprovalMatrix(
                    company_id="cacao",
                    document_type=tipo,
                    role_id=rol.id,
                    min_amount=Decimal("0"),
                    approval_level=2,
                    enabled=False,
                ),
            ]
        )
        database.session.commit()
        role_id = rol.id
    yield role_id, sufijo
    with app.app_context():
        database.session.execute(database.delete(ApprovalMatrix).where(ApprovalMatrix.role_id == role_id))
        database.session.execute(database.delete(Roles).where(Roles.id == role_id))
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def test_render_muestra_estado_y_accion_accesible(app, authenticated_client, reglas_activas_e_inactivas):
    """Ambos estados se etiquetan y el botón expone su acción a tecnologías de asistencia."""
    _role_id, sufijo = reglas_activas_e_inactivas

    response = authenticated_client("admin").get("/settings/approval-matrix?company=cacao")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert f"Receptor {sufijo}" in cuerpo
    assert re.search(r">\s*Activa\s*<", cuerpo)
    assert re.search(r">\s*Inactiva\s*<", cuerpo)
    for accion in ("Deshabilitar regla de aprobación", "Habilitar regla de aprobación"):
        assert f'aria-label="{accion}"' in cuerpo
        assert f'title="{accion}"' in cuerpo
