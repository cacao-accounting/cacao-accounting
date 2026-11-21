# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""#1685: los impuestos solo aceptan tipos de cálculo conocidos.

Escenario de negocio: un administrador crea un impuesto desde
``/settings/taxes``. Un ``tax_type`` manipulado fuera de ``percentage`` o
``fixed`` no debe persistirse ni calcularse como porcentaje por defecto. El
contrato se aplica tanto en la ruta administrativa como en el modelo y en la
conversión de plantillas hacia el motor fiscal.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.accounting_engine.document_builders import (
    CalculationContextBuilderError,
    _template_tax_calculation_method,
)
from cacao_accounting.database import Modules, Tax, database

MENSAJES_TIPO_INVALIDO = (
    "El tipo de impuesto seleccionado no es válido.",
    "The selected tax type is not valid.",
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


def test_admin_rechaza_tipo_de_impuesto_desconocido(app, authenticated_client, modulo_admin_activo):
    """Un tipo manipulado responde con error y no crea el impuesto."""
    nombre = f"Impuesto inválido {uuid4().hex[:8]}"
    cliente = authenticated_client()

    respuesta = cliente.post(
        "/settings/taxes",
        data={
            "name": nombre,
            "rate": "15",
            "tax_type": "otro",
            "applies_to": "both",
            "is_active": "on",
        },
    )

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/settings/taxes")

    con_seguimiento = cliente.post(
        "/settings/taxes",
        data={
            "name": nombre,
            "rate": "15",
            "tax_type": "otro",
            "applies_to": "both",
            "is_active": "on",
        },
        follow_redirects=True,
    )

    assert con_seguimiento.status_code == 200
    html = con_seguimiento.get_data(as_text=True)
    assert any(mensaje in html for mensaje in MENSAJES_TIPO_INVALIDO)
    with app.app_context():
        assert database.session.execute(database.select(Tax).filter_by(name=nombre)).scalar_one_or_none() is None


@pytest.mark.parametrize(("tipo", "tasa"), (("percentage", "15"), ("fixed", "25")))
def test_admin_persiste_los_tipos_de_impuesto_soportados(app, authenticated_client, modulo_admin_activo, tipo, tasa):
    """Los dos tipos ofrecidos por la interfaz siguen guardándose."""
    nombre = f"Impuesto válido {uuid4().hex[:8]}"

    respuesta = authenticated_client().post(
        "/settings/taxes",
        data={
            "name": nombre,
            "rate": tasa,
            "tax_type": tipo,
            "applies_to": "both",
            "is_active": "on",
        },
    )

    assert respuesta.status_code == 302
    with app.app_context():
        impuesto = database.session.execute(database.select(Tax).filter_by(name=nombre)).scalar_one()
        assert impuesto.tax_type == tipo
        database.session.delete(impuesto)
        database.session.commit()


def test_modelo_rechaza_tipo_de_impuesto_desconocido():
    """Asignar o crear un impuesto con un tipo fuera del contrato falla en el ORM."""
    with pytest.raises(ValueError, match="El tipo de impuesto seleccionado no es válido\\."):
        Tax(name="Impuesto inválido", rate=15, tax_type="otro")

    impuesto = Tax(name="Impuesto válido", rate=15, tax_type="percentage")
    with pytest.raises(ValueError, match="El tipo de impuesto seleccionado no es válido\\."):
        impuesto.tax_type = "mystery"


@pytest.mark.parametrize(("tipo", "metodo"), (("percentage", "percentage"), ("fixed", "fixed")))
def test_conversion_de_plantilla_conserva_los_tipos_soportados(tipo, metodo):
    """La conversión al motor fiscal no altera los tipos permitidos."""
    assert _template_tax_calculation_method(SimpleNamespace(tax_type=tipo)) == metodo


def test_conversion_de_plantilla_rechaza_tipo_desconocido():
    """Un valor heredado inválido no se normaliza silenciosamente a porcentaje."""
    with pytest.raises(CalculationContextBuilderError, match="El tipo de impuesto seleccionado no es válido\\."):
        _template_tax_calculation_method(SimpleNamespace(tax_type="otro"))
