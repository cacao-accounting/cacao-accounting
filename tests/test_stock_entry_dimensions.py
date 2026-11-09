# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Dimensiones analíticas de inventario limitadas a la compañía.

Escenario de negocio: una entrada de almacén de ``cacao`` no puede guardar un
centro de costo, unidad de negocio o proyecto de ``alpha``. La UI normal no
expone esos campos, por lo que el servidor debe rechazar un POST manipulado.
"""

from __future__ import annotations

from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    CostCenter,
    Currency,
    Entity,
    GLEntry,
    Item,
    Modules,
    Project,
    StockEntry,
    StockLedgerEntry,
    Unit,
    UOM,
    User,
    database,
)
from cacao_accounting.contabilidad.posting_service import PostingError, post_stock_entry
from cacao_accounting.inventario.services import (
    _handle_stock_entry_new_post,
    _update_stock_entry_from_form,
)

CONTRASENA = "stock-dimensiones-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def inventario_dimensiones():
    """Cloud con dimensiones homónimas en cacao y alpha."""
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
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Book(
                    entity="cacao",
                    code="LOCAL",
                    name="Principal",
                    status="activo",
                    currency="NIO",
                    default=True,
                    is_primary=True,
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="PERIODO-CACAO",
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    enabled=True,
                    is_closed=False,
                ),
            ]
        )
        dimensiones = {}
        database.session.add_all(
            [
                UOM(code="UND", name="Unidad"),
                Item(
                    code="ART-1",
                    name="Artículo de prueba",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="UND",
                ),
            ]
        )
        for company in ("cacao", "alpha"):
            centro = CostCenter(
                entity=company,
                code=f"CC-{company.upper()}",
                name=f"Centro {company}",
                active=True,
                enabled=True,
                group=False,
            )
            unidad = Unit(entity=company, code=f"UN-{company.upper()}", name=f"Unidad {company}", enabled=True)
            proyecto = Project(entity=company, code=f"PR-{company.upper()}", name=f"Proyecto {company}", enabled=True)
            database.session.add_all([centro, unidad, proyecto])
            dimensiones[company] = {
                "centro": centro.code,
                "unidad": unidad.code,
                "proyecto": proyecto.code,
            }
        database.session.commit()
    yield application, dimensiones
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _post_entrada(application, dimensiones):
    formulario = MultiDict(
        [
            ("purpose", "material_receipt"),
            ("company", "cacao"),
            ("posting_date", FECHA.isoformat()),
            ("transaction_currency", "NIO"),
            ("cost_center_code", dimensiones["centro"]),
            ("unit_code", dimensiones["unidad"]),
            ("project_code", dimensiones["proyecto"]),
            ("item_code_0", "ART-1"),
            ("qty_0", "1"),
            ("rate_0", "10"),
            ("uom_0", "UND"),
        ]
    )
    with application.test_request_context("/inventory/stock-entry/new", method="POST", data=formulario):
        from flask_login import login_user

        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        login_user(usuario)
        _handle_stock_entry_new_post(formulario)


def test_entrada_rechaza_dimensiones_de_otra_compania(inventario_dimensiones):
    """El POST con dimensiones de alpha no persiste una StockEntry."""
    application, dimensiones = inventario_dimensiones

    with application.app_context():
        _post_entrada(application, dimensiones["alpha"])
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_entrada_rechaza_proyecto_ajeno_con_dimensiones_propias(inventario_dimensiones):
    """El proyecto ajeno se rechaza con centro y unidad propios."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        formulario = MultiDict(
            [
                ("purpose", "material_receipt"),
                ("company", "cacao"),
                ("posting_date", FECHA.isoformat()),
                ("transaction_currency", "NIO"),
                ("cost_center_code", propias["centro"]),
                ("unit_code", propias["unidad"]),
                ("project_code", ajenas["proyecto"]),
                ("item_code_0", "ART-1"),
                ("qty_0", "1"),
                ("rate_0", "10"),
                ("uom_0", "UND"),
            ]
        )
        with application.test_request_context("/inventory/stock-entry/new", method="POST", data=formulario):
            from flask_login import login_user

            usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(usuario)
            _handle_stock_entry_new_post(formulario)

        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_posting_rechaza_entrada_heredada_con_dimension_ajena(inventario_dimensiones):
    """Una entrada heredada no llega a stock ledger ni GL con dimensiones ajenas."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        entrada = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=FECHA,
            cost_center_code=propias["centro"],
            unit_code=ajenas["unidad"],
            project_code=propias["proyecto"],
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=1,
        )
        database.session.add(entrada)
        database.session.commit()

        with application.test_request_context(f"/inventory/stock-entry/{entrada.id}"):
            from flask_login import login_user

            usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(usuario)
            with pytest.raises(PostingError, match="unidad"):
                post_stock_entry(entrada)
        database.session.rollback()

        assert database.session.execute(database.select(StockLedgerEntry)).scalars().all() == []
        assert database.session.execute(database.select(GLEntry)).scalars().all() == []


def test_entrada_acepta_dimensiones_de_su_compania(inventario_dimensiones):
    """Control positivo: las dimensiones de cacao sí se guardan."""
    application, dimensiones = inventario_dimensiones

    with application.app_context():
        _post_entrada(application, dimensiones["cacao"])
        entradas = database.session.execute(database.select(StockEntry)).scalars().all()
        assert len(entradas) == 1
        assert entradas[0].cost_center_code == dimensiones["cacao"]["centro"]
        assert entradas[0].unit_code == dimensiones["cacao"]["unidad"]
        assert entradas[0].project_code == dimensiones["cacao"]["proyecto"]


def test_edicion_rechaza_dimensiones_de_otra_compania(inventario_dimensiones):
    """La edición tampoco puede introducir una dimensión ajena."""
    application, dimensiones = inventario_dimensiones

    with application.app_context():
        _post_entrada(application, dimensiones["cacao"])
        entrada = database.session.execute(database.select(StockEntry)).scalar_one()
        formulario = MultiDict(
            [
                ("purpose", "material_receipt"),
                ("company", "cacao"),
                ("posting_date", FECHA.isoformat()),
                ("transaction_currency", "NIO"),
                ("cost_center_code", dimensiones["cacao"]["centro"]),
                ("unit_code", dimensiones["alpha"]["unidad"]),
                ("project_code", dimensiones["cacao"]["proyecto"]),
            ]
        )
        with application.test_request_context("/inventory/stock-entry/edit", method="POST", data=formulario):
            from flask_login import login_user

            usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(usuario)
            with pytest.raises(ValueError, match="unidad de negocio"):
                _update_stock_entry_from_form(entrada)

        assert entrada.unit_code == dimensiones["cacao"]["unidad"]
