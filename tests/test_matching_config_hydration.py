# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2012: las pantallas de matching hidratan la configuración persistida.

Al seleccionar una compañía con reglas guardadas, compras y ventas deben
prefilar tolerancias, modos y checkboxes en lugar de mostrar los valores por
defecto y sobrescribir la política existente al guardar.
"""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    ApprovalRequest,
    CompanyDefaultAccount,
    Entity,
    Modules,
    PurchaseMatchingConfig,
    SalesMatchingConfig,
    database,
)

CAMPOS_COMPRAS = (
    "matching_type",
    "price_tolerance_type",
    "price_tolerance_value",
    "qty_tolerance_type",
    "qty_tolerance_value",
)


def _input(cuerpo: str, name: str, tipo: str | None = None) -> str:
    """Devuelve la etiqueta input del campo indicado, por tipo si se especifica."""
    encontrados = [
        etiqueta
        for etiqueta in re.findall(r"<input[^>]*>", cuerpo)
        if f'name="{name}"' in etiqueta and (tipo is None or f'type="{tipo}"' in etiqueta)
    ]
    assert len(encontrados) == 1, f"No se identificó de forma única el input {name} ({tipo})."
    return encontrados[0]


def _checkbox_envia_valor_explicito(cuerpo: str, name: str) -> None:
    """La casilla marcada debe preceder al valor oculto que representa False."""
    casilla = _input(cuerpo, name, "checkbox")
    oculto = _input(cuerpo, name, "hidden")
    assert oculto == '<input type="hidden" name="' + name + '" value="_no">'
    assert cuerpo.index(casilla) < cuerpo.index(oculto)


def _select(cuerpo: str, name: str, value: str) -> str:
    """Devuelve la opción seleccionada del select indicado, no de cualquier select."""
    bloque = re.search(rf"<select[^>]*name=\"{name}\"[^>]*>.*?</select>", cuerpo, re.S)
    assert bloque is not None, f"No se encontró el select {name}."
    coincidencia = re.search(rf"<option value=\"{value}\" selected>", bloque.group(0))
    assert coincidencia is not None, f"La opción {name}={value} no está seleccionada."
    return coincidencia.group(0)


@pytest.fixture
def matching_hidratado(app):
    """Compañía aislada con configuración de compras y ventas persistida."""
    sufijo = uuid4().hex[:6]
    company = f"h{sufijo}"
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
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía {company}",
                company_name=f"Compañía {company} SA",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                PurchaseMatchingConfig(
                    company=company,
                    matching_type="2-way",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("5"),
                    qty_tolerance_type="absolute",
                    qty_tolerance_value=Decimal("3"),
                    require_purchase_order=False,
                    bridge_account_required=False,
                    auto_reconcile=False,
                    allow_price_difference=True,
                ),
                SalesMatchingConfig(
                    company=company,
                    matching_type="2-way",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("4.5"),
                    require_sales_order=False,
                    allow_price_difference=True,
                ),
                CompanyDefaultAccount(company=company, apply_advances_automatically=True),
            ]
        )
        database.session.commit()
    yield company
    with app.app_context():
        database.session.execute(database.delete(CompanyDefaultAccount).where(CompanyDefaultAccount.company == company))
        database.session.execute(database.delete(PurchaseMatchingConfig).where(PurchaseMatchingConfig.company == company))
        database.session.execute(database.delete(SalesMatchingConfig).where(SalesMatchingConfig.company == company))
        database.session.execute(database.delete(Entity).where(Entity.code == company))
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def test_compras_hidrata_configuracion_existente(app, authenticated_client, matching_hidratado):
    """El formulario de compras refleja la fila guardada, no los valores por defecto."""
    response = authenticated_client("admin").get(f"/settings/purchase-reconciliation?company={matching_hidratado}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Editar configuración" in cuerpo
    assert "Nueva configuración" not in cuerpo
    _select(cuerpo, "matching_type", "2-way")
    _select(cuerpo, "price_tolerance_type", "absolute")
    _select(cuerpo, "qty_tolerance_type", "absolute")
    assert 'value="5.0000"' in _input(cuerpo, "price_tolerance_value")
    assert 'value="3.0000"' in _input(cuerpo, "qty_tolerance_value")
    assert "checked" not in _input(cuerpo, "require_purchase_order", "checkbox")
    assert "checked" not in _input(cuerpo, "bridge_account_required", "checkbox")
    assert "checked" not in _input(cuerpo, "auto_reconcile", "checkbox")
    assert "checked" in _input(cuerpo, "allow_price_difference", "checkbox")
    assert "checked" in _input(cuerpo, "apply_advances_automatically", "checkbox")
    for campo in (
        "require_purchase_order",
        "bridge_account_required",
        "auto_reconcile",
        "allow_price_difference",
        "apply_advances_automatically",
    ):
        _checkbox_envia_valor_explicito(cuerpo, campo)


def test_ventas_hidrata_configuracion_existente(app, authenticated_client, matching_hidratado):
    """El formulario de ventas refleja la fila guardada, no los valores por defecto."""
    response = authenticated_client("admin").get(f"/settings/sales-matching?company={matching_hidratado}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Editar configuración" in cuerpo
    assert "Nueva configuración" not in cuerpo
    _select(cuerpo, "matching_type", "2-way")
    _select(cuerpo, "price_tolerance_type", "absolute")
    assert 'value="4.5000"' in _input(cuerpo, "price_tolerance_value")
    assert "checked" not in _input(cuerpo, "require_sales_order", "checkbox")
    assert "checked" in _input(cuerpo, "allow_price_difference", "checkbox")
    _checkbox_envia_valor_explicito(cuerpo, "require_sales_order")
    _checkbox_envia_valor_explicito(cuerpo, "allow_price_difference")


CAMPOS_COMPRAS_GUARDADOS = CAMPOS_COMPRAS + (
    "require_purchase_order",
    "bridge_account_required",
    "auto_reconcile",
    "allow_price_difference",
)
CAMPOS_VENTAS_GUARDADOS = CAMPOS_COMPRAS[:3] + ("require_sales_order", "allow_price_difference")


def _instantanea(app, modelo, company: str, campos: tuple[str, ...]) -> tuple[str, ...]:
    """Devuelve los valores persistentes relevantes para la comparación."""
    with app.app_context():
        config = database.session.execute(database.select(modelo).filter_by(company=company)).scalar_one()
        valores = tuple(str(getattr(config, campo)) for campo in campos)
        if modelo is PurchaseMatchingConfig:
            adelantos = database.session.execute(
                database.select(CompanyDefaultAccount.apply_advances_automatically).filter_by(company=company)
            ).scalar_one()
            valores += (str(bool(adelantos)),)
        return valores


@pytest.mark.parametrize(
    ("ruta", "modelo", "campos", "datos"),
    [
        (
            "/settings/purchase-reconciliation",
            PurchaseMatchingConfig,
            CAMPOS_COMPRAS_GUARDADOS,
            {
                "config_form": "complete",
                "matching_type": "2-way",
                "price_tolerance_type": "absolute",
                "price_tolerance_value": "5.0000",
                "qty_tolerance_type": "absolute",
                "qty_tolerance_value": "3.0000",
                "require_purchase_order": "_no",
                "bridge_account_required": "_no",
                "auto_reconcile": "_no",
                "allow_price_difference": "on",
                "apply_advances_automatically": "on",
            },
        ),
        (
            "/settings/sales-matching",
            SalesMatchingConfig,
            CAMPOS_VENTAS_GUARDADOS,
            {
                "config_form": "complete",
                "matching_type": "2-way",
                "price_tolerance_type": "absolute",
                "price_tolerance_value": "4.5000",
                "require_sales_order": "_no",
                "allow_price_difference": "on",
            },
        ),
    ],
)
def test_post_completo_preserva_la_politica_guardada(
    app, authenticated_client, matching_hidratado, ruta, modelo, campos, datos
):
    """El formulario renderizado republicado no altera la configuración vigente."""
    anterior = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    cliente = authenticated_client("admin")
    try:
        pagina = cliente.get(f"{ruta}?company={matching_hidratado}")
        assert 'name="config_form" value="complete"' in pagina.get_data(as_text=True)
        antes = _instantanea(app, modelo, matching_hidratado, campos)
        respuesta = cliente.post(ruta, data={**datos, "company": matching_hidratado})
        assert respuesta.status_code == 302
        assert _instantanea(app, modelo, matching_hidratado, campos) == antes
    finally:
        app.config["MODO_ESCRITORIO"] = anterior


@pytest.mark.parametrize(
    ("ruta", "modelo", "campos"),
    [
        ("/settings/purchase-reconciliation", PurchaseMatchingConfig, CAMPOS_COMPRAS_GUARDADOS),
        ("/settings/sales-matching", SalesMatchingConfig, CAMPOS_VENTAS_GUARDADOS),
    ],
)
def test_post_parcial_se_rechaza_sin_modificar(app, authenticated_client, matching_hidratado, ruta, modelo, campos):
    """Un POST que omite el marcador del formulario no resetea valores de alta."""
    anterior = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    cliente = authenticated_client("admin")
    try:
        antes = _instantanea(app, modelo, matching_hidratado, campos)
        respuesta = cliente.post(
            ruta,
            data={
                "company": matching_hidratado,
                "matching_type": "3-way",
                "price_tolerance_type": "percentage",
            },
        )
        assert respuesta.status_code == 302
        assert _instantanea(app, modelo, matching_hidratado, campos) == antes
        detalle = cliente.get(respuesta.headers["Location"])
        assert "incompleto" in detalle.get_data(as_text=True)
    finally:
        app.config["MODO_ESCRITORIO"] = anterior


CONFIG_COMPLETA = {
    "/settings/purchase-reconciliation": {
        "config_form": "complete",
        "matching_type": "2-way",
        "price_tolerance_type": "absolute",
        "price_tolerance_value": "5.0000",
        "qty_tolerance_type": "absolute",
        "qty_tolerance_value": "3.0000",
        "require_purchase_order": "_no",
        "bridge_account_required": "_no",
        "auto_reconcile": "_no",
        "allow_price_difference": "on",
        "apply_advances_automatically": "on",
    },
    "/settings/sales-matching": {
        "config_form": "complete",
        "matching_type": "2-way",
        "price_tolerance_type": "absolute",
        "price_tolerance_value": "4.5000",
        "require_sales_order": "_no",
        "allow_price_difference": "on",
    },
}


@pytest.mark.parametrize(
    ("ruta", "modelo", "campos", "campo_omitido"),
    [
        (ruta, modelo, campos, campo)
        for ruta, modelo, campos in (
            ("/settings/purchase-reconciliation", PurchaseMatchingConfig, CAMPOS_COMPRAS_GUARDADOS),
            ("/settings/sales-matching", SalesMatchingConfig, CAMPOS_VENTAS_GUARDADOS),
        )
        for campo in CONFIG_COMPLETA[ruta]
    ],
)
def test_post_con_marcador_y_campo_omitido_se_rechaza(
    app, authenticated_client, matching_hidratado, ruta, modelo, campos, campo_omitido
):
    """El marcador del cliente no acredita completitud: el servidor la verifica."""
    cliente = authenticated_client("admin")
    datos = dict(CONFIG_COMPLETA[ruta])
    del datos[campo_omitido]
    datos["company"] = matching_hidratado
    with app.app_context():
        solicitudes_antes = database.session.execute(database.select(ApprovalRequest.id)).scalars().all()
        antes = _instantanea(app, modelo, matching_hidratado, campos)
    respuesta = cliente.post(ruta, data=datos)
    assert respuesta.status_code == 302
    with app.app_context():
        assert _instantanea(app, modelo, matching_hidratado, campos) == antes
        assert database.session.execute(database.select(ApprovalRequest.id)).scalars().all() == solicitudes_antes
    detalle = cliente.get(respuesta.headers["Location"])
    assert "incompleto" in detalle.get_data(as_text=True)
