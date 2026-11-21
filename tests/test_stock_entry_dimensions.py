# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Dimensiones analíticas de inventario limitadas a la compañía.

Escenario de negocio: una entrada de almacén de ``cacao`` no puede guardar un
centro de costo, unidad de negocio o proyecto de ``alpha``. La UI normal no
expone esos campos, por lo que el servidor debe rechazar un POST manipulado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    CostCenter,
    Currency,
    Entity,
    GLEntry,
    Item,
    Modules,
    NamingSeries,
    Project,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    Unit,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.contabilidad.posting_service import PostingError, post_stock_entry

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
                Warehouse(
                    code="WH-CACAO",
                    name="Bodega Cacao",
                    company="cacao",
                    is_active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code="ART-1",
                name="Artículo de prueba",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
            )
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
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        database.session.commit()
    yield application, dimensiones
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _post_entrada(application, dimensiones, purpose="material_receipt"):
    """Post a crafted stock-entry header through the same HTTP route as the client."""
    with application.app_context():
        naming_series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    path = {
        "material_receipt": "/inventory/stock-entry/material-receipt/new",
        "stock_reconciliation": "/inventory/stock-entry/reconciliation/new",
    }[purpose]
    response = client.post(
        path,
        data={
            "purpose": purpose,
            "company": "cacao",
            "naming_series": naming_series_id,
            "posting_date": FECHA.isoformat(),
            "transaction_currency": "NIO",
            "to_warehouse": "WH-CACAO",
            "cost_center_code": dimensiones["centro"],
            "unit_code": dimensiones["unidad"],
            "project_code": dimensiones["proyecto"],
            "item_code_0": "ART-1",
            "qty_0": "1",
            "rate_0": "10",
            "uom_0": "UND",
        },
    )
    return response


def test_entrada_rechaza_dimensiones_de_otra_compania(inventario_dimensiones):
    """El POST con dimensiones de alpha no persiste una StockEntry."""
    application, dimensiones = inventario_dimensiones

    with application.app_context():
        response = _post_entrada(application, dimensiones["alpha"])
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_entrada_rechaza_centro_ajeno_con_dimensiones_propias(inventario_dimensiones):
    """El centro de costo ajeno se rechaza con unidad y proyecto propios."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        response = _post_entrada(
            application,
            {"centro": ajenas["centro"], "unidad": propias["unidad"], "proyecto": propias["proyecto"]},
        )
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_entrada_rechaza_unidad_ajena_con_dimensiones_propias(inventario_dimensiones):
    """La unidad de negocio ajena se rechaza aunque las otras dimensiones sean propias."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        response = _post_entrada(
            application,
            {"centro": propias["centro"], "unidad": ajenas["unidad"], "proyecto": propias["proyecto"]},
        )
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_entrada_rechaza_proyecto_ajeno_con_dimensiones_propias(inventario_dimensiones):
    """El proyecto ajeno se rechaza con centro y unidad propios."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        response = _post_entrada(
            application,
            {"centro": propias["centro"], "unidad": propias["unidad"], "proyecto": ajenas["proyecto"]},
        )
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


@pytest.mark.parametrize(
    ("field", "dimension", "error"),
    [
        ("cost_center_code", "centro", "centro de costo"),
        ("unit_code", "unidad", "unidad"),
        ("project_code", "proyecto", "proyecto"),
    ],
)
def test_posting_rechaza_entrada_heredada_con_dimension_ajena(inventario_dimensiones, field, dimension, error):
    """Una entrada heredada no llega a stock ledger ni GL con una dimensión ajena."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]
    entry_dimensions = {
        "cost_center_code": propias["centro"],
        "unit_code": propias["unidad"],
        "project_code": propias["proyecto"],
    }
    entry_dimensions[field] = ajenas[dimension]

    with application.app_context():
        entrada = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=FECHA,
            to_warehouse="WH-CACAO",
            **entry_dimensions,
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=1,
        )
        database.session.add(entrada)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entrada.id,
                item_code="ART-1",
                target_warehouse="WH-CACAO",
                qty=Decimal("1"),
                uom="UND",
                qty_in_base_uom=Decimal("1"),
                basic_rate=Decimal("10"),
                amount=Decimal("10"),
            )
        )
        database.session.commit()

        with application.test_request_context(f"/inventory/stock-entry/{entrada.id}"):
            from flask_login import login_user

            usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(usuario)
            with pytest.raises(PostingError, match=error):
                post_stock_entry(entrada)
            assert database.session.execute(database.select(StockLedgerEntry)).scalars().all() == []
            assert database.session.execute(database.select(GLEntry)).scalars().all() == []
        database.session.rollback()

        assert database.session.execute(database.select(StockLedgerEntry)).scalars().all() == []
        assert database.session.execute(database.select(GLEntry)).scalars().all() == []


def test_conciliacion_rechaza_dimension_ajena_antes_de_guardar(inventario_dimensiones):
    """La ruta de conciliación también rechaza dimensiones ajenas en borradores nuevos."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        response = _post_entrada(
            application,
            {"centro": propias["centro"], "unidad": ajenas["unidad"], "proyecto": propias["proyecto"]},
            purpose="stock_reconciliation",
        )
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_entrada_acepta_dimensiones_de_su_compania(inventario_dimensiones):
    """Control positivo: las dimensiones de cacao sí se guardan."""
    application, dimensiones = inventario_dimensiones

    with application.app_context():
        response = _post_entrada(application, dimensiones["cacao"])
        assert response.status_code == 302
        entradas = database.session.execute(database.select(StockEntry)).scalars().all()
        assert len(entradas) == 1
        assert entradas[0].cost_center_code == dimensiones["cacao"]["centro"]
        assert entradas[0].unit_code == dimensiones["cacao"]["unidad"]
        assert entradas[0].project_code == dimensiones["cacao"]["proyecto"]


@pytest.mark.parametrize(
    ("field", "dimension", "error"),
    [
        ("cost_center_code", "centro", "centro de costo"),
        ("unit_code", "unidad", "unidad"),
        ("project_code", "proyecto", "proyecto"),
    ],
)
def test_edicion_rechaza_dimension_ajena_en_conciliacion(inventario_dimensiones, field, dimension, error):
    """La edición de conciliación rechaza cada dimensión ajena sin alterar el borrador."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        entrada = StockEntry(
            purpose="stock_reconciliation",
            company="cacao",
            posting_date=FECHA,
            cost_center_code=propias["centro"],
            unit_code=propias["unidad"],
            project_code=propias["proyecto"],
            naming_series_id=database.session.execute(
                database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
            ).scalar_one(),
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=0,
        )
        database.session.add(entrada)
        database.session.commit()
        original_id = entrada.id
        posted_dimensions = {
            "cost_center_code": propias["centro"],
            "unit_code": propias["unidad"],
            "project_code": propias["proyecto"],
        }
        posted_dimensions[field] = ajenas[dimension]
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True
        response = client.post(
            f"/inventory/stock-entry/{original_id}/edit",
            data={
                "purpose": "stock_reconciliation",
                "company": "cacao",
                "naming_series": entrada.naming_series_id,
                "posting_date": FECHA.isoformat(),
                "transaction_currency": "NIO",
                "cost_center_code": posted_dimensions["cost_center_code"],
                "unit_code": posted_dimensions["unit_code"],
                "project_code": posted_dimensions["project_code"],
            },
        )
        assert response.status_code == 200

        database.session.expire_all()
        entrada = database.session.get(StockEntry, original_id)
        assert entrada is not None
        assert (entrada.cost_center_code, entrada.unit_code, entrada.project_code) == (
            propias["centro"],
            propias["unidad"],
            propias["proyecto"],
        )
        assert database.session.execute(database.select(StockLedgerEntry)).scalars().all() == []
        assert database.session.execute(database.select(GLEntry)).scalars().all() == []
