# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Validación de la secuencia en las líneas de una plantilla de impuestos (#2068).

Escenario de negocio: un administrador agrega líneas a una plantilla de
impuestos desde ``/settings/tax-templates/<id>/items``. Si la secuencia no es
un número entero la petición debe responder con una redirección controlada y
el mensaje traducido al usuario, sin un error 500 ni persistir la línea
inválida; una secuencia entera válida sí debe persistir la línea.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Tax, TaxTemplate, TaxTemplateItem, database

MENSAJES_SECUENCIA_INVALIDA = (
    "La secuencia debe ser un número entero.",
    "The sequence must be an integer.",
)


@pytest.fixture
def modulo_admin_activo(app):
    """Habilita el módulo admin para las rutas de configuración y restaura su estado al salir."""
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            fue_creado = True
            estado_previo = True
        else:
            fue_creado = False
            estado_previo = modulo.enabled
            modulo.enabled = True
        database.session.commit()

    yield

    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if fue_creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = estado_previo
            database.session.commit()


def _crear_plantilla(app, *, con_impuesto: bool) -> tuple[str, str]:
    """Crea una plantilla de impuestos única y opcionalmente un impuesto activo.

    Devuelve el identificador de la plantilla y el del impuesto (vacío si no
    se solicitó impuesto).
    """
    sufijo = uuid4().hex[:8]
    with app.app_context():
        plantilla = TaxTemplate(
            name=f"Plantilla de ventas {sufijo}",
            company="cacao",
            template_type="selling",
            currency="NIO",
            is_active=True,
        )
        database.session.add(plantilla)
        impuesto = Tax(
            name=f"IVA de prueba {sufijo}",
            rate=15,
            tax_type="percentage",
            applies_to="both",
            is_active=True,
        )
        database.session.add(impuesto)
        database.session.commit()
        return plantilla.id, (impuesto.id if con_impuesto else "")


def test_secuencia_no_entera_redirige_con_mensaje_y_no_persiste(app, authenticated_client, modulo_admin_activo):
    """Una secuencia no entera responde con redirección controlada y no persiste la línea."""
    plantilla_id, _ = _crear_plantilla(app, con_impuesto=False)
    ruta = f"/settings/tax-templates/{plantilla_id}/items"
    cliente = authenticated_client()

    respuesta = cliente.post(ruta, data={"sequence": "abc", "tax_id": "", "calculation_base": "net_document"})

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith(ruta)

    con_seguimiento = cliente.post(
        ruta,
        data={"sequence": "abc", "tax_id": "", "calculation_base": "net_document"},
        follow_redirects=True,
    )

    assert con_seguimiento.status_code == 200
    html = con_seguimiento.get_data(as_text=True)
    assert any(mensaje in html for mensaje in MENSAJES_SECUENCIA_INVALIDA)
    with app.app_context():
        lineas = (
            database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=plantilla_id)).scalars().all()
        )
        assert lineas == []


def test_secuencia_entera_persiste_la_linea_de_plantilla(app, authenticated_client, modulo_admin_activo):
    """Una secuencia entera válida persiste la línea con el impuesto y los valores enviados."""
    plantilla_id, impuesto_id = _crear_plantilla(app, con_impuesto=True)
    ruta = f"/settings/tax-templates/{plantilla_id}/items"

    respuesta = authenticated_client().post(
        ruta,
        data={
            "sequence": "5",
            "tax_id": impuesto_id,
            "calculation_base": "previous_total",
            "behavior": "deductive",
        },
    )

    assert respuesta.status_code == 302
    with app.app_context():
        linea = (
            database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=plantilla_id)).scalars().one()
        )
        assert linea.sequence == 5
        assert linea.tax_id == impuesto_id
        assert linea.calculation_base == "previous_total"
        assert linea.behavior == "deductive"
        assert linea.is_inclusive is False


def test_secuencia_vacia_usa_el_valor_predeterminado(app, authenticated_client, modulo_admin_activo):
    """Omitir la secuencia persiste la línea con el valor predeterminado 10."""
    plantilla_id, impuesto_id = _crear_plantilla(app, con_impuesto=True)
    ruta = f"/settings/tax-templates/{plantilla_id}/items"

    respuesta = authenticated_client().post(ruta, data={"sequence": "", "tax_id": impuesto_id})

    assert respuesta.status_code == 302
    with app.app_context():
        linea = (
            database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=plantilla_id)).scalars().one()
        )
        assert linea.sequence == 10
