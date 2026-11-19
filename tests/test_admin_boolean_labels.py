# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2065: las tablas administrativas renderizan etiquetas, no booleanos crudos."""

from __future__ import annotations

from cacao_accounting.database import LedgerMappingRule, Modules, PriceList, database


def _activar_admin(app) -> None:
    """Habilita el módulo administrativo que exigen las rutas."""
    with app.app_context():
        if database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none() is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
            database.session.commit()


def _tabla(html: str) -> str:
    """Extrae el cuerpo de la primera tabla de resultados del HTML."""
    return html.split("<table", 1)[1].split("</table>", 1)[0]


def test_ledger_mapping_renderiza_estado_traducido(app, entorno_contable, authenticated_client):
    """La columna Estado muestra Activo/Inactivo y nunca True/False."""
    _activar_admin(app)
    with app.app_context():
        reglas = [
            LedgerMappingRule(source_book="DEFAULT_BOOK", target_book="NIIF", rule_description="Activa", is_active=True),
            LedgerMappingRule(source_book="DEFAULT_BOOK", target_book="NIIF", rule_description="Inactiva", is_active=False),
        ]
        database.session.add_all(reglas)
        database.session.commit()
        reglas_ids = [regla.id for regla in reglas]

    try:
        respuesta = authenticated_client().get("/settings/ledger-mapping-rules")

        assert respuesta.status_code == 200
        tabla = _tabla(respuesta.get_data(as_text=True))
        assert "Activo" in tabla
        assert "Inactivo" in tabla
        assert ">True<" not in tabla
        assert ">False<" not in tabla
    finally:
        with app.app_context():
            for regla in database.session.execute(
                database.select(LedgerMappingRule).where(LedgerMappingRule.id.in_(reglas_ids))
            ).scalars():
                database.session.delete(regla)
            database.session.commit()


def test_price_lists_renderiza_booleanos_traducidos(app, entorno_contable, authenticated_client):
    """Las columnas de compra, venta y predeterminada usan Sí/No."""
    _activar_admin(app)
    with app.app_context():
        lista = PriceList(
            name="Lista visible", company="cacao", currency="NIO", is_buying=False, is_selling=True, is_default=False
        )
        database.session.add(lista)
        database.session.commit()
        lista_id = lista.id

    try:
        respuesta = authenticated_client().get("/settings/price-lists")

        assert respuesta.status_code == 200
        tabla = _tabla(respuesta.get_data(as_text=True))
        assert "Lista visible" in tabla
        assert "Sí" in tabla
        assert "No" in tabla
        assert ">True<" not in tabla
        assert ">False<" not in tabla
    finally:
        with app.app_context():
            lista = database.session.get(PriceList, lista_id)
            if lista is not None:
                database.session.delete(lista)
                database.session.commit()
