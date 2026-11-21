# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1154: un período cerrado no puede redefinirse sin reabrirlo.

Cambiar fechas o año fiscal de un período cerrado reclasificaría movimientos
históricos sin pasar por la reapertura auditada.
"""

from __future__ import annotations

import re
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import AccountingPeriod, Entity, FiscalYear, database


@pytest.fixture
def periodo_cerrado_aislado(app, entorno_contable):
    """Compañía, año fiscal y período cerrado propios de la prueba."""
    sufijo = uuid4().hex[:6].upper()
    company = f"C{sufijo}"
    fiscal_year_id = f"FYC{sufijo}"
    period_id = f"P{sufijo}"
    with app.app_context():
        entity = Entity(
            code=company,
            name=f"Compañía {sufijo}",
            company_name=f"Compañía {sufijo} SA",
            tax_id=f"J-C{sufijo}",
            currency="NIO",
            enabled=True,
            status="activo",
        )
        database.session.add(entity)
        database.session.flush()
        database.session.add(
            FiscalYear(
                id=fiscal_year_id,
                entity=company,
                name=f"Año {sufijo}",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                id=period_id,
                entity=company,
                fiscal_year_id=fiscal_year_id,
                name=f"Periodo cerrado {sufijo}",
                start=date(2026, 3, 1),
                end=date(2026, 3, 31),
                enabled=True,
                is_closed=True,
                status="habilitado_cerrado",
            )
        )
        database.session.commit()
    yield {"company": company, "fiscal_year": fiscal_year_id, "period": period_id, "suffix": sufijo}
    with app.app_context():
        period = database.session.get(AccountingPeriod, period_id)
        if period is not None:
            database.session.delete(period)
        database.session.flush()
        fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
        if fiscal_year is not None:
            database.session.delete(fiscal_year)
        database.session.flush()
        entity = database.session.get(Entity, company)
        if entity is not None:
            database.session.delete(entity)
        database.session.commit()


def _datos(periodo: dict[str, str], *, nombre: str, inicio: str, fin: str) -> dict[str, str]:
    """POST del formulario de edición con la definición solicitada."""
    return {
        "id": periodo["suffix"],
        "entidad": periodo["company"],
        "fiscal_year": periodo["fiscal_year"],
        "nombre": nombre,
        "inicio": inicio,
        "fin": fin,
        "habilitado": "on",
    }


def test_editar_periodo_cerrado_rechaza_cambios_y_conserva_historial(app, authenticated_client, periodo_cerrado_aislado):
    """El POST no altera nombre, fechas ni estado de un período cerrado."""
    periodo = periodo_cerrado_aislado
    nombre_original = f"Periodo cerrado {periodo['suffix']}"

    respuesta = authenticated_client().post(
        f"/accounting/accounting_period/{periodo['period']}/edit",
        data=_datos(periodo, nombre="Período redefinido", inicio="2026-04-01", fin="2026-04-30"),
    )

    assert respuesta.status_code == 200
    assert "Reabralo antes de modificar" in respuesta.get_data(as_text=True)
    with app.app_context():
        registro = database.session.get(AccountingPeriod, periodo["period"])
        assert registro is not None
        assert registro.name == nombre_original
        assert registro.start == date(2026, 3, 1)
        assert registro.end == date(2026, 3, 31)
        assert registro.is_closed is True
        assert registro.enabled is True


def test_formulario_de_periodo_cerrado_no_permite_editar_campos(app, authenticated_client, periodo_cerrado_aislado):
    """La pantalla desactiva los campos estructurales y oculta Guardar."""
    periodo = periodo_cerrado_aislado

    respuesta = authenticated_client().get(f"/accounting/accounting_period/{periodo['period']}/edit")
    html = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    nombre = re.search(r'<input[^>]*id="nombre"[^>]*>', html)
    inicio = re.search(r'<input[^>]*id="inicio"[^>]*>', html)
    fiscal_year = re.search(r'<select[^>]*id="fiscal_year"[^>]*>', html)
    assert nombre is not None and "disabled" in nombre.group(0)
    assert inicio is not None and "disabled" in inicio.group(0)
    assert fiscal_year is not None and "disabled" in fiscal_year.group(0)
    assert "Guardar Período" not in html
    assert "Reabrir período y continuar cierre" in html


def test_periodo_reabierto_permite_editar_su_definicion(app, authenticated_client, periodo_cerrado_aislado):
    """Tras la reapertura controlada, la edición vuelve a persistir."""
    periodo = periodo_cerrado_aislado
    with app.app_context():
        registro = database.session.get(AccountingPeriod, periodo["period"])
        registro.is_closed = False
        registro.status = "habilitado_abierto"
        database.session.commit()

    respuesta = authenticated_client().post(
        f"/accounting/accounting_period/{periodo['period']}/edit",
        data=_datos(periodo, nombre="Período reabierto", inicio="2026-04-01", fin="2026-04-30"),
    )

    assert respuesta.status_code == 302
    with app.app_context():
        registro = database.session.get(AccountingPeriod, periodo["period"])
        assert registro is not None
        assert registro.name == "Período reabierto"
        assert registro.start == date(2026, 4, 1)
        assert registro.end == date(2026, 4, 30)
        assert registro.is_closed is False
