# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1961: los formularios renderizan los Incoterms activos del catálogo."""

from __future__ import annotations

from cacao_accounting.database import Incoterm, database


def test_formularios_de_compra_y_venta_muestran_incoterms_activos(app, entorno_contable, authenticated_client):
    """La macro compartida recibe el catálogo activo y excluye los inactivos."""
    del entorno_contable
    with app.app_context():
        database.session.add_all(
            [
                Incoterm(code="FOB", version="2020", name="Free on Board", is_active=True),
                Incoterm(code="EXW", version="2020", name="Ex Works", is_active=False),
            ]
        )
        database.session.commit()

    try:
        client = authenticated_client("admin")
        compras = client.get("/buying/purchase-order/new")
        ventas = client.get("/sales/sales-order/new")

        assert compras.status_code == 200
        assert ventas.status_code == 200
        for respuesta in (compras, ventas):
            cuerpo = respuesta.get_data(as_text=True)
            assert 'value="FOB"' in cuerpo
            assert 'value="EXW"' not in cuerpo
    finally:
        with app.app_context():
            database.session.execute(database.delete(Incoterm).where(Incoterm.code.in_(["FOB", "EXW"])))
            database.session.commit()
