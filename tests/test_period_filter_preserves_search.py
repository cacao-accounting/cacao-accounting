# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2155: el formulario de filtros por período conserva la búsqueda y el estado.

El macro ``period_list_filters`` (templates/macros.html) debe emitir campos
ocultos con los parámetros ``search`` y ``status`` de la petición para que la
paginación por compañía/período no borre el filtro de texto del listado.
"""

from __future__ import annotations

import re

from cacao_accounting.database import AccountingPeriod, Entity, User, UserCompanyAccess, database

BUSQUEDA = "XQ-TEST"
ESTADO = "draft"
CLASE_FORMULARIO_PERIODO = "p-3 border-bottom d-flex flex-wrap gap-2 align-items-end"


def _crear_compania_sin_periodos(app, sufijo: str) -> str:
    """Compañía propia sin períodos contables para probar el selector vacío."""
    codigo = f"NP{sufijo}"
    with app.app_context():
        if database.session.execute(database.select(Entity).filter_by(code=codigo)).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code=codigo,
                    name=f"Sin períodos {sufijo}",
                    company_name=f"Sin Períodos {sufijo} SA",
                    tax_id=f"NP{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )
            database.session.commit()
    return codigo


def _bloque_formulario_de_periodo(html: str) -> str:
    """Extrae el formulario de filtros por período del HTML del listado."""
    patron = rf'<form method="get" action="[^"]*" class="{CLASE_FORMULARIO_PERIODO}">(.*?)</form>'
    coincidencia = re.search(patron, html, re.DOTALL)
    return coincidencia.group(1) if coincidencia else ""


def test_filtro_de_periodo_conserva_busqueda_y_estado(app, authenticated_client, entorno_contable):
    """El listado de pagos mantiene search y status dentro del formulario de período."""
    cliente = authenticated_client()
    respuesta = cliente.get(f"/cash_management/payment/list?search={BUSQUEDA}&status={ESTADO}&company=cacao")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)

    formulario = _bloque_formulario_de_periodo(html)
    assert formulario, "El listado con períodos debe renderizar el formulario de filtros por período."
    assert f'<input type="hidden" name="search" value="{BUSQUEDA}">' in formulario
    assert f'<input type="hidden" name="status" value="{ESTADO}">' in formulario


def test_list_filters_tambien_repite_la_busqueda_visible(app, authenticated_client, entorno_contable):
    """El buscador visible conserva el término para que el usuario vea el filtro activo."""
    cliente = authenticated_client()
    respuesta = cliente.get(f"/cash_management/payment/list?search={BUSQUEDA}&status={ESTADO}&company=cacao")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert re.search(
        r'<input[^>]*id="list-search"[^>]*value="XQ-TEST"', html, re.DOTALL
    ), "El cuadro de búsqueda debe repetir el término activo."
    assert re.search(r'<option value="draft"[^>]*selected', html), "El estado seleccionado debe quedar marcado."


def test_formulario_de_periodo_no_se_emite_sin_periodos(app, authenticated_client, entorno_contable):
    """Sin períodos para la compañía no hay formulario y por tanto no hay campos ocultos."""
    with app.app_context():
        company = "alpha"
        assert (
            database.session.execute(database.select(AccountingPeriod).filter_by(entity=company)).scalars().first() is None
        ), "La compañía alpha no debe tener períodos para este escenario."

    # #1828: en Cloud el admin necesita acceso explícito a la compañía consultada.
    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    if (
        database.session.execute(
            database.select(UserCompanyAccess).filter_by(user_id=admin.id, company_code=company)
        ).scalar_one_or_none()
        is None
    ):
        database.session.add(UserCompanyAccess(user_id=admin.id, company_code=company))
        database.session.commit()

    cliente = authenticated_client()
    respuesta = cliente.get(f"/cash_management/payment/list?search={BUSQUEDA}&company={company}")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert _bloque_formulario_de_periodo(html) == ""
    assert '<input type="hidden" name="search"' not in html
