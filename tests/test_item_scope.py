# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance de compañía en el detalle y la edición de artículos.

Escenarios de negocio (#1181/#1541 y #1418/#1542, consolidación #1649):
un artículo global expone configuración contable por compañía; el
detalle solo debe mostrar las filas de compañías consultables, y el
guardado no debe borrar las filas de compañías omitidas del formulario
que el usuario no puede editar.
"""

from decimal import Decimal

import pytest
from flask_login import login_user

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import database
from cacao_accounting.inventario.service import ItemParams, update_item_with_uoms

CONTRASENA = "articulos-alcance-2026"


@pytest.fixture
def inventario_articulos():
    """Cloud con artículo compartido y configuración contable en dos compañías."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import (
            Accounts,
            CostCenter,
            Entity,
            Item,
            ItemAccount,
            Modules,
            UOM,
            User,
            UserCompanyAccess,
            Warehouse,
        )

        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                UOM(code="Unidad", name="Unidad", is_active=True),
                CostCenter(code="CC01", name="Centro principal", entity="cacao", active=True, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="secreta",
                    name="Compañía Secreta",
                    company_name="Compañía Secreta SA",
                    tax_id="J0009",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Item(
                    code="CHOCOLATE-100G",
                    name="Chocolate 100g",
                    item_type="goods",
                    default_uom="Unidad",
                    is_stock_item=False,
                ),
                User(
                    id="editor",
                    user="editor",
                    name="Editor Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="editor", company_code="cacao"),
                Warehouse(
                    code="BODEGA-SECRET",
                    name="Bodega Secreta",
                    company="secreta",
                    is_active=True,
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("editor", "inventory_auxiliar")
        cuenta = Accounts(
            code="6.01.01.001",
            name="Gasto del Artículo",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="expense",
        )
        database.session.add(cuenta)
        database.session.commit()
        database.session.add_all(
            [
                ItemAccount(
                    item_code="CHOCOLATE-100G",
                    company="cacao",
                    expense_account_id=cuenta.id,
                    cost_center_code="CC01",
                ),
                ItemAccount(
                    item_code="CHOCOLATE-100G",
                    company="secreta",
                    expense_account_id=cuenta.id,
                    cost_center_code="CC01",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    assert client.post("/login", data={"usuario": "editor", "acceso": CONTRASENA}, follow_redirects=True).status_code == 200


def test_editar_preserva_las_filas_de_companias_no_autorizadas(inventario_articulos):
    """#1418/#1542: el reemplazo no borra la fila de la compañía ajena."""
    application = inventario_articulos
    client = application.test_client()
    _iniciar(client)
    response = client.post(
        "/inventory/item/CHOCOLATE-100G/edit",
        data={
            "name": "Chocolate 100g",
            "item_type": "goods",
            "is_stock_item": "y",
            "default_uom": "Unidad",
            "standard_rate": "100",
            "account_company": "cacao",
            "expense_account_id": cuenta_id(application),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with application.app_context():
        from cacao_accounting.database import ItemAccount, database

        filas = {
            fila.company
            for fila in database.session.execute(database.select(ItemAccount).filter_by(item_code="CHOCOLATE-100G")).scalars()
        }
    assert filas == {"cacao", "secreta"}, "La fila de la compañía ajena no debe borrarse por omisión del formulario."


def test_el_guardado_parcial_actualiza_las_filas_autorizadas(inventario_articulos):
    """El usuario con edición autorizada solo modifica su fila; la ajena se conserva."""
    application = inventario_articulos
    with application.test_request_context("/"):
        from flask_login import login_user

        from cacao_accounting.database import ItemAccount, User, database

        user = database.session.execute(database.select(User).filter_by(user="editor")).scalar_one()
        login_user(user)

        row_owner = database.session.execute(
            database.select(ItemAccount).filter_by(item_code="CHOCOLATE-100G", company="cacao")
        ).scalar_one()
        params = ItemParams(
            name="Chocolate 100g renovado",
            item_type="goods",
            is_stock_item=True,
            default_uom="Unidad",
            standard_rate=Decimal("120"),
            account_rows=[
                ItemAccount(
                    item_code="CHOCOLATE-100G",
                    company="cacao",
                    expense_account_id=row_owner.expense_account_id,
                )
            ],
        )
        update_item_with_uoms("CHOCOLATE-100G", params)
        filas = {
            fila.company: fila.expense_account_id for fila in database.session.execute(database.select(ItemAccount)).scalars()
        }
    assert set(filas) == {"cacao", "secreta"}
    assert filas["cacao"] == cuenta_id(application)


def cuenta_id(application) -> str:
    """Devuelve el id de la cuenta contable de gasto sembrada para 'cacao'."""
    with application.app_context():
        from cacao_accounting.database import Accounts, database

        cuenta = database.session.execute(database.select(Accounts).filter_by(code="6.01.01.001")).scalar_one()
        return cuenta.id


def test_el_detalle_no_expone_filas_de_companias_no_consultables(inventario_articulos):
    """#1181/#1541: el detalle se limita a la configuración consultable."""
    application = inventario_articulos
    client = application.test_client()
    _iniciar(client)
    response = client.get("/inventory/item/CHOCOLATE-100G")
    texto = response.get_data(as_text=True)
    assert "secreta" not in texto
    assert "cacao" in texto
    # La bodega ajena tampoco se expone en el detalle.
    assert "BODEGA-SECRET" not in texto
