# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2067: las tablas de tolerancias renderizan etiquetas localizadas."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Modules, Entity, PurchaseMatchingConfig, SalesMatchingConfig, database


def _activar_admin(app) -> None:
    """Habilita el módulo administrativo que exigen las rutas."""

    with app.app_context():
        if database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none() is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
            database.session.commit()


def _tabla(html: str) -> str:
    """Extrae el cuerpo de la tabla de configuraciones del HTML."""
    return html.split('<table class="ca-table">', 1)[1].split("</table>", 1)[0]


def _segunda_compania(app) -> str:
    """Crea una compañía adicional para cubrir ambos tipos de tolerancia."""
    with app.app_context():
        code = f"otra{uuid4().hex[:6]}"
        database.session.add(
            Entity(
                code=code,
                name="Otra",
                company_name="Otra SA",
                tax_id=f"J-{code}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.commit()
        return code


def test_compra_renderiza_tipos_absoluto_y_porcentaje(app, entorno_contable, authenticated_client):
    """Precio y cantidad muestran Absoluto o % y no los códigos persistidos."""
    _activar_admin(app)
    otra = _segunda_compania(app)
    with app.app_context():
        database.session.add_all(
            [
                PurchaseMatchingConfig(
                    company="cacao",
                    price_tolerance_type="absolute",
                    price_tolerance_value=Decimal("1.5"),
                    qty_tolerance_type="absolute",
                    qty_tolerance_value=Decimal("2"),
                ),
                PurchaseMatchingConfig(
                    company=otra,
                    price_tolerance_type="percentage",
                    price_tolerance_value=Decimal("3"),
                    qty_tolerance_type="percentage",
                    qty_tolerance_value=Decimal("4"),
                ),
            ]
        )
        database.session.commit()

    respuesta = authenticated_client().get("/settings/purchase-reconciliation")

    assert respuesta.status_code == 200
    tabla = _tabla(respuesta.get_data(as_text=True))
    assert "1.5000 Absoluto" in tabla
    assert "2.0000 Absoluto" in tabla
    assert "3.0000 %" in tabla
    assert "4.0000 %" in tabla
    assert "absolute" not in tabla
    assert "percentage" not in tabla
    with app.app_context():
        for config in database.session.execute(
            database.select(PurchaseMatchingConfig).where(PurchaseMatchingConfig.company.in_(["cacao", otra]))
        ).scalars():
            database.session.delete(config)
        entidad = database.session.execute(database.select(Entity).filter_by(code=otra)).scalar_one()
        database.session.delete(entidad)
        database.session.commit()


def test_venta_renderiza_el_tipo_de_tolerancia(app, entorno_contable, authenticated_client):
    """La tabla de ventas muestra Absoluto sin el código técnico."""
    _activar_admin(app)
    with app.app_context():
        config = SalesMatchingConfig(company="cacao", price_tolerance_type="absolute", price_tolerance_value=Decimal("5"))
        database.session.add(config)
        database.session.commit()
        config_id = config.id

    respuesta = authenticated_client().get("/settings/sales-matching")

    assert respuesta.status_code == 200
    tabla = _tabla(respuesta.get_data(as_text=True))
    assert "5.0000 Absoluto" in tabla
    assert "absolute" not in tabla
    with app.app_context():
        config = database.session.get(SalesMatchingConfig, config_id)
        if config is not None:
            database.session.delete(config)
            database.session.commit()
