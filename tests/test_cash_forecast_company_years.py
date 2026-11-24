# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2016: el formulario de pronóstico recarga años fiscales por compañía."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import FiscalYear, UserCompanyAccess, database


def test_el_selector_de_anio_fiscal_sigue_a_la_compania(app, entorno_contable, reference_users, authenticated_client):
    """Cada compañía ofrece solo sus propios años fiscales."""
    del entorno_contable
    admin_id = str(reference_users["admin"].id)
    sufijo = uuid4().hex[:6]
    with app.app_context():
        anio = FiscalYear(
            entity="alpha",
            name=f"ALPHA-{sufijo}",
            year_start_date=date(2027, 1, 1),
            year_end_date=date(2027, 12, 31),
            is_closed=False,
        )
        database.session.add(anio)
        acceso = database.session.execute(
            select(UserCompanyAccess).filter_by(user_id=admin_id, company_code="alpha")
        ).scalar_one_or_none()
        if acceso is None:
            database.session.add(UserCompanyAccess(user_id=admin_id, company_code="alpha"))
        database.session.commit()
        anio_id = anio.id

    try:
        client = authenticated_client("admin")
        cacao = client.get("/cash_management/cash-forecast/new?company=cacao")
        alpha = client.get("/cash_management/cash-forecast/new?company=alpha")

        assert cacao.status_code == 200
        assert alpha.status_code == 200
        cuerpo_cacao = cacao.get_data(as_text=True)
        cuerpo_alpha = alpha.get_data(as_text=True)
        assert 'value="FY2026"' in cuerpo_cacao
        assert f'value="{anio_id}"' not in cuerpo_cacao
        assert f'value="{anio_id}"' in cuerpo_alpha
        assert 'value="FY2026"' not in cuerpo_alpha
        assert 'name="company" value="alpha"' in cuerpo_alpha
    finally:
        with app.app_context():
            anio = database.session.get(FiscalYear, anio_id)
            if anio is not None:
                database.session.delete(anio)
            database.session.execute(
                database.delete(UserCompanyAccess).where(
                    UserCompanyAccess.user_id == admin_id, UserCompanyAccess.company_code == "alpha"
                )
            )
            database.session.commit()
