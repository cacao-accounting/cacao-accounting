# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2103: la paginación de series conserva el filtro de compañía."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import NamingSeries, database


def test_siguiente_conserva_company_en_series(app, authenticated_client):
    """Con más de una página, el enlace siguiente mantiene `company`."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        series = [
            NamingSeries(
                name=f"PAG-{suffix}-{index:02d}",
                entity_type="sales_invoice",
                company="cacao",
                prefix_template=f"PAG-{index}-",
                is_active=True,
                is_default=False,
            )
            for index in range(25)
        ]
        database.session.add_all(series)
        database.session.commit()
        series_ids = [row.id for row in series]

    try:
        response = authenticated_client().get("/accounting/naming-series/list?company=cacao")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "page=2" in html
        assert "company=cacao" in html
    finally:
        with app.app_context():
            for series_id in series_ids:
                row = database.session.get(NamingSeries, series_id)
                if row is not None:
                    database.session.delete(row)
            database.session.commit()
