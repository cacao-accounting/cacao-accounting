# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1747: el alta de artículo acepta UOM comercial de compra y venta.

Las rutas deben cargar choices para los tres selectores; de lo contrario WTForms
rechaza una UOM válida como 'Opción inválida' y el artículo no se persiste.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import CostCenter, Item, ItemUOMConversion, UOM, database


def test_alta_de_articulo_persiste_uom_de_compra_y_venta(app, authenticated_client, entorno_contable):
    """Una UOM comercial válida se acepta en alta y queda guardada."""
    del entorno_contable
    sufijo = uuid4().hex[:5].upper()
    base = f"EA{sufijo}"
    comercial = f"BX{sufijo}"
    nombre = f"Articulo comercial {sufijo}"
    with app.app_context():
        database.session.add_all([UOM(code=base, name="Each"), UOM(code=comercial, name="Box", is_active=True)])
        database.session.flush()
        from cacao_accounting.database import Accounts

        cuentas = {
            fila.code: fila.id
            for fila in database.session.execute(
                database.select(Accounts).where(Accounts.entity == "cacao", Accounts.code.in_(["4101", "5101", "5201"]))
            ).scalars()
        }
        database.session.add(
            CostCenter(code=f"CC{sufijo}", name="Centro de prueba", entity="cacao", active=True, enabled=True)
        )
        database.session.commit()
    try:
        response = authenticated_client("admin").post(
            "/inventory/item/new",
            data={
                "name": nombre,
                "item_type": "goods",
                "is_purchase_item": "on",
                "is_sale_item": "on",
                "default_uom": base,
                "purchase_uom": comercial,
                "sale_uom": comercial,
                "uom_code": comercial,
                "uom_conversion_factor": "12",
                "currency": "NIO",
                "account_company": "cacao",
                "expense_account_id": cuentas["5201"],
                "income_account_id": cuentas["4101"],
                "cogs_account_id": cuentas["5101"],
                "cost_center_code": f"CC{sufijo}",
            },
        )

        assert response.status_code == 302
        with app.app_context():
            item = database.session.execute(database.select(Item).filter_by(name=nombre)).scalar_one()
            assert item.default_uom == base
            assert item.purchase_uom == comercial
            assert item.sale_uom == comercial
            conversion = database.session.execute(
                database.select(ItemUOMConversion).filter_by(item_code=item.code, from_uom=comercial)
            ).scalar_one()
            assert conversion.conversion_factor == Decimal("12")
    finally:
        with app.app_context():
            item = database.session.execute(database.select(Item).filter_by(name=nombre)).scalar_one_or_none()
            if item is not None:
                from cacao_accounting.database import ItemAccount

                database.session.execute(database.delete(ItemUOMConversion).where(ItemUOMConversion.item_code == item.code))
                database.session.execute(database.delete(ItemAccount).where(ItemAccount.item_code == item.code))
                database.session.execute(database.delete(Item).where(Item.id == item.id))
            database.session.execute(database.delete(UOM).where(UOM.code.in_([base, comercial])))
            database.session.execute(database.delete(CostCenter).where(CostCenter.code == f"CC{sufijo}"))
            database.session.commit()
