# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2025: los enlaces de pronósticos siguen el permiso efectivo de consulta.

La portada de bancos publica los enlaces a Flujo de Caja, Comparativo y
Entradas Manuales solo con ``acceso.consultar``. Un usuario con permiso de
reportes pero sin consulta no debe ver los enlaces, y la ruta tampoco puede
atenderlo; con consulta explícita, ambos deben funcionar.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

ENLACE_FLUJO = 'href="/cash_management/cash-forecast/list"'
ENLACE_COMPARATIVO = 'href="/cash_management/cash-forecast/compare"'
ENLACE_ENTRADAS = 'href="/cash_management/cash-forecast/manual-entries"'

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="El pronóstico de caja no aplica en modo escritorio.",
)


def _cash_viewer(app, *, consultar: bool, reportes: bool) -> tuple[str, int]:
    """Crea un usuario de solo lectura con los permisos de caja indicados."""
    suffix = uuid4().hex[:6]
    user_id = f"cash-forecast-{suffix}"
    with app.app_context():
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        role = Roles(name=f"cash-forecast-{suffix}", note="Permisos de pronósticos")
        database.session.add(role)
        database.session.flush()
        user = User(
            id=user_id,
            user=user_id,
            name="Pronósticos de Caja",
            password=proteger_passwd("CashForecast-2026!"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=module_id,
                    access=True,
                    view=consultar,
                    report=reportes,
                ),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="cacao"),
            ]
        )
        database.session.commit()
        return user_id, user.auth_version


def _client_for(app, user_id: str, auth_version: int):
    """Devuelve un cliente HTTP con la sesión del usuario indicado."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def test_forecast_links_and_route_require_consultar(app, entorno_contable):
    """Un rol con solo reportes no ve los enlaces ni accede a la ruta."""
    assert entorno_contable.app is app
    user_id, auth_version = _cash_viewer(app, consultar=False, reportes=True)
    client = _client_for(app, user_id, auth_version)

    portada = client.get("/cash_management/cash")
    assert portada.status_code == 200
    html = portada.get_data(as_text=True)
    assert ENLACE_FLUJO not in html
    assert ENLACE_COMPARATIVO not in html
    assert ENLACE_ENTRADAS not in html
    assert "<span>Proyección de Flujo de Caja</span>" in html

    ruta = client.get("/cash_management/cash-forecast/list?company=cacao")
    assert ruta.status_code == 403


def test_forecast_links_and_route_available_with_consultar(app, entorno_contable):
    """El permiso de consulta publica los enlaces y habilita la ruta."""
    assert entorno_contable.app is app
    user_id, auth_version = _cash_viewer(app, consultar=True, reportes=False)
    client = _client_for(app, user_id, auth_version)

    portada = client.get("/cash_management/cash")
    assert portada.status_code == 200
    html = portada.get_data(as_text=True)
    assert ENLACE_FLUJO in html
    assert ENLACE_COMPARATIVO in html
    assert ENLACE_ENTRADAS in html
    assert "<span>Proyección de Flujo de Caja</span>" not in html

    ruta = client.get("/cash_management/cash-forecast/list?company=cacao")
    assert ruta.status_code == 200
