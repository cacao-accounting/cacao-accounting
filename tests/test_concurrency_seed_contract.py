# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Contrato de los helpers que comparten los casos de lock sobre motor real.

``test_purchase_receipt_return_cancel_postgresql`` siembra la compañía y crea la
base desechable que reutilizan los escenarios de concurrencia de #2306, #2353 y
#2355. Esos módulos importan ``_isolated_url``, ``_seed`` y ``_drop`` y dan por
sentados códigos fijos (``cacao``, NIO, libro FISCAL, almacén BOD01, artículo
ART01). Aquí se fija ese contrato sobre SQLite para que un cambio de códigos o
de estructura falle en una prueba clara en vez de romper la colección de cinco
módulos en CI.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from test_purchase_receipt_return_cancel_postgresql import _seed

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    FiscalYear,
    Item,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)


@pytest.fixture
def app_aislada():
    """App SQLite en memoria, independiente de la base compartida del worker."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2311-contrato",
        }
    )
    try:
        yield application
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_siembra_sin_sufijo_conserva_el_escenario_historico(app_aislada):
    """Los casos de lock siguen encontrando los códigos fijos que esperan."""
    semilla = _seed(app_aislada)
    assert semilla["company"] == "cacao"
    assert semilla["currency"] == "NIO"
    assert semilla["book"] == "FISCAL"
    assert semilla["warehouse_code"] == "BOD01"

    with app_aislada.app_context():
        entidad = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        libro = database.session.execute(database.select(Book).filter_by(entity="cacao", is_primary=True)).scalar_one()
        moneda = database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one()
        ejercicio = database.session.get(FiscalYear, "FY2026")
        periodo = database.session.get(AccountingPeriod, "P2026-05")
        administrador = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        articulo = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        unidad = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        bodega = database.session.execute(database.select(Warehouse).filter_by(code="BOD01")).scalar_one()

        assert entidad.currency == "NIO"
        assert (libro.code, libro.currency) == ("FISCAL", "NIO")
        assert moneda.default is True
        assert ejercicio is not None and ejercicio.entity == "cacao"
        assert periodo is not None and periodo.fiscal_year_id == "FY2026"
        assert administrador.classification == "admin"
        assert articulo.default_uom == "UND" and articulo.is_stock_item
        assert bodega.company == "cacao"
        assert semilla["admin_id"] == administrador.id
        assert semilla["item_id"] == articulo.id
        assert semilla["uom_id"] == unidad.id
        assert semilla["warehouse_id"] == bodega.id


def test_siembra_provee_el_plan_contable_completo_para_postear(app_aislada):
    """Cada tipo de cuenta que un posting necesita queda sembrado y enlazado."""
    _seed(app_aislada)
    with app_aislada.app_context():
        cuentas = database.session.execute(database.select(Accounts).filter_by(entity="cacao")).scalars().all()
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        enlace_bodega = database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(company="cacao", warehouse_code="BOD01")
        ).scalar_one()

    por_tipo = {cuenta.account_type: cuenta for cuenta in cuentas}
    assert set(por_tipo) == {
        "cash",
        "bank",
        "receivable",
        "payable",
        "stock",
        "bridge",
        "tax",
        "income",
        "expense",
    }
    assert defaults.default_cash == por_tipo["cash"].id
    assert defaults.default_bank == por_tipo["bank"].id
    assert defaults.default_receivable == por_tipo["receivable"].id
    assert defaults.default_payable == por_tipo["payable"].id
    assert defaults.default_income == por_tipo["income"].id
    assert defaults.default_expense == por_tipo["expense"].id
    assert defaults.bridge_account_id == por_tipo["bridge"].id
    assert enlace_bodega.inventory_account_id == por_tipo["stock"].id


def test_siembra_con_sufijo_permite_dos_companias_en_la_misma_base(app_aislada):
    """Con sufijo los códigos son exclusivos: dos carreras comparten la base."""
    primera = _seed(app_aislada, "AAA111")
    segunda = _seed(app_aislada, "BBB222")

    claves_comunes = set(primera) & set(segunda)
    assert {"company", "currency", "book", "item_id", "uom_id", "warehouse_id", "supplier_id", "admin_id"} <= claves_comunes
    for clave in ("company", "currency", "book", "warehouse_code", "admin_id"):
        assert primera[clave] != segunda[clave], f"la clave {clave} debe quedar aislada por sufijo"

    with app_aislada.app_context():
        companias = {entidad.code for entidad in database.session.execute(database.select(Entity)).scalars().all()}
        assert {primera["company"], segunda["company"]} <= companias
        for semilla in (primera, segunda):
            libros = (
                database.session.execute(database.select(Book).filter_by(entity=semilla["company"], is_primary=True))
                .scalars()
                .all()
            )
            assert len(libros) == 1, f"{semilla['company']} debe tener un único libro primario"
            assert libros[0].currency == semilla["currency"]
            tipos = {
                cuenta.account_type
                for cuenta in database.session.execute(database.select(Accounts).filter_by(entity=semilla["company"]))
                .scalars()
                .all()
            }
            assert "stock" in tipos and "payable" in tipos
