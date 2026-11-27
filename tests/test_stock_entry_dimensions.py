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
    Accounts,
    Book,
    CompanyDefaultAccount,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
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
    UserCompanyAccess,
    Warehouse,
    WarehouseCompanyAccount,
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
        # #1828: en Cloud la clasificación admin no concede compañías por sí sola.
        database.session.add_all(
            [
                UserCompanyAccess(user_id="admin", company_code="cacao"),
                UserCompanyAccess(user_id="admin", company_code="alpha"),
            ]
        )
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
            ]
        )
        cacao_year = FiscalYear(
            entity="cacao",
            name="AF2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
            financial_closed=False,
        )
        database.session.add(cacao_year)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=cacao_year.id,
                name="PERIODO-CACAO",
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
                enabled=True,
                is_closed=False,
            )
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


def _post_entrada_con_detalle(application, lineas, payload_fiscal: str = ""):
    """Postea una entrada cuyo detalle lleva dimensiones y observaciones por línea."""
    with application.app_context():
        naming_series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()
    data = {
        "purpose": "material_receipt",
        "company": "cacao",
        "naming_series": naming_series_id,
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "to_warehouse": "WH-CACAO",
        "tax_lines_payload": payload_fiscal,
    }
    for index, linea in enumerate(lineas):
        data.update(
            {
                f"item_code_{index}": "ART-1",
                f"qty_{index}": "1",
                f"rate_{index}": "10",
                f"uom_{index}": "UND",
                f"cost_center_{index}": linea.get("centro", ""),
                f"project_{index}": linea.get("proyecto", ""),
                f"remarks_{index}": linea.get("observaciones", ""),
                f"account_{index}": linea.get("cuenta", ""),
                f"unit_{index}": linea.get("unidad", ""),
            }
        )
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client.post("/inventory/stock-entry/material-receipt/new", data=data)


def _detalle_por_linea(application):
    """Devuelve (centro, proyecto, observaciones) de cada línea persistida."""
    entrada = database.session.execute(database.select(StockEntry)).scalars().one()
    lineas = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entrada.id)).scalars().all()
    return {(linea.cost_center_code, linea.project_code, linea.remarks) for linea in lineas}


def test_linea_persiste_dimensiones_y_observaciones_propias(inventario_dimensiones):
    """Cada línea conserva su centro, proyecto y observaciones de la compañía."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]

    with application.app_context():
        database.session.add(
            CostCenter(
                entity="cacao",
                code="CC-ALTERNO",
                name="Centro alterno",
                active=True,
                enabled=True,
                group=False,
            )
        )
        database.session.commit()
        response = _post_entrada_con_detalle(
            application,
            [
                {"centro": propias["centro"], "proyecto": propias["proyecto"], "observaciones": "lote de apertura"},
                {"centro": "CC-ALTERNO", "observaciones": "sin proyecto"},
            ],
        )
        assert response.status_code == 302
        assert _detalle_por_linea(application) == {
            (propias["centro"], propias["proyecto"], "lote de apertura"),
            ("CC-ALTERNO", None, "sin proyecto"),
        }


@pytest.mark.parametrize(("campo", "dimension"), [("centro", "centro"), ("proyecto", "proyecto")])
def test_linea_rechaza_dimension_de_otra_compania(inventario_dimensiones, campo, dimension):
    """Una dimensión de alpha en la línea impide guardar la entrada completa."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]
    linea = {"centro": propias["centro"], "proyecto": propias["proyecto"]}
    linea[campo] = ajenas[dimension]

    with application.app_context():
        response = _post_entrada_con_detalle(application, [linea])
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


@pytest.mark.parametrize("campo", ["cuenta", "unidad"])
def test_linea_rechaza_controles_no_admitidos(inventario_dimensiones, campo):
    """La cuenta contable y la unidad de negocio no forman parte del detalle de línea."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]

    with application.app_context():
        response = _post_entrada_con_detalle(
            application,
            [{"centro": propias["centro"], "proyecto": propias["proyecto"], campo: "VALOR-NO-ADMITIDO"}],
        )
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_entrada_rechaza_cargos_fiscales_del_modal(inventario_dimensiones):
    """El payload fiscal que serializa la plantilla se rechaza, no se ignora."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]

    with application.app_context():
        response = _post_entrada_con_detalle(
            application,
            [{"centro": propias["centro"], "proyecto": propias["proyecto"]}],
            payload_fiscal='[{"account": "ACC-1", "amount": 19}]',
        )
        assert response.status_code == 200
        assert database.session.execute(database.select(StockEntry)).scalars().all() == []


def test_posting_rechaza_dimension_ajena_en_el_detalle(inventario_dimensiones):
    """Una dimensión de alpha en la línea bloquea el asiento sin dejar GL ni stock."""
    application, dimensiones = inventario_dimensiones
    propias = dimensiones["cacao"]
    ajenas = dimensiones["alpha"]

    with application.app_context():
        entrada = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=FECHA,
            to_warehouse="WH-CACAO",
            cost_center_code=propias["centro"],
            unit_code=propias["unidad"],
            project_code=propias["proyecto"],
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
                cost_center_code=ajenas["centro"],
            )
        )
        database.session.commit()

        with application.test_request_context(f"/inventory/stock-entry/{entrada.id}"):
            from flask_login import login_user

            usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(usuario)
            with pytest.raises(PostingError, match="centro de costo"):
                post_stock_entry(entrada)
            database.session.rollback()

        assert database.session.execute(database.select(GLEntry)).scalars().all() == []
        assert database.session.execute(database.select(StockLedgerEntry)).scalars().all() == []


def test_gl_lleva_las_dimensiones_de_cada_linea(entorno_contable_aislado):
    """El detalle manda sobre la cabecera y ninguna línea hereda dimensiones ajenas."""
    application = entorno_contable_aislado.app
    with application.app_context():
        cuenta_inventario = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="1109")
        ).scalar_one()
        cuenta_ajuste = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="5201")
        ).scalar_one()
        for account_id in (cuenta_inventario, cuenta_ajuste):
            cuenta = database.session.get(Accounts, account_id)
            assert cuenta is not None
            cuenta.active = True
            cuenta.enabled = True
            cuenta.group = False
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        defaults.inventory_adjustment_account_id = cuenta_ajuste

        bodega = "DIM-W"
        database.session.add(Warehouse(code=bodega, name="Bodega dimensiones", company="cacao", is_active=True))
        database.session.flush()
        database.session.add(
            WarehouseCompanyAccount(warehouse_code=bodega, company="cacao", inventory_account_id=cuenta_inventario)
        )
        for code in ("CC-L1", "CC-L2", "CC-CAB"):
            database.session.add(
                CostCenter(entity="cacao", code=code, name=f"Centro {code}", active=True, enabled=True, group=False)
            )
        for code in ("PR-L1", "PR-CAB"):
            database.session.add(Project(entity="cacao", code=code, name=f"Proyecto {code}", enabled=True))
        database.session.add(
            Item(
                code="DIM-ART",
                name="Artículo dimensional",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
            )
        )
        entrada = StockEntry(
            purpose="adjustment_positive",
            company="cacao",
            posting_date=date(2026, 5, 20),
            to_warehouse=bodega,
            from_warehouse=bodega,
            cost_center_code="CC-CAB",
            project_code="PR-CAB",
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=1,
        )
        database.session.add(entrada)
        database.session.flush()
        for index, (centro, proyecto) in enumerate((("CC-L1", "PR-L1"), ("CC-L2", None))):
            database.session.add(
                StockEntryItem(
                    stock_entry_id=entrada.id,
                    item_code="DIM-ART",
                    source_warehouse=bodega,
                    target_warehouse=bodega,
                    qty=Decimal("1"),
                    uom="UND",
                    qty_in_base_uom=Decimal("1"),
                    basic_rate=Decimal("10"),
                    amount=Decimal("10"),
                    cost_center_code=centro,
                    project_code=proyecto,
                )
            )
        database.session.commit()

        with application.test_request_context(f"/inventory/stock-entry/{entrada.id}"):
            from flask_login import login_user

            usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(usuario)
            post_stock_entry(entrada)

        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entrada.id)).scalars().all()
        assert asientos
        dimensiones_gl = {(asiento.cost_center_code, asiento.project_code) for asiento in asientos}
        assert ("CC-L1", "PR-L1") in dimensiones_gl
        assert ("CC-L2", "PR-CAB") in dimensiones_gl
        assert all(centro != "CC-CAB" for centro, _proyecto in dimensiones_gl)


def _cliente_admin(application):
    """Cliente autenticado como administrador sin depender de CSRF."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_la_entrada_no_renderiza_controles_no_admitidos(inventario_dimensiones):
    """#1888: la cuadrícula de inventario omite cuenta, unidad y cargos fiscales."""
    application, _dimensiones = inventario_dimensiones
    html = _cliente_admin(application).get("/inventory/stock-entry/adjustment-positive/new").get_data(as_text=True)
    for retirado in (
        "'account_' + index",
        "'unit_' + index",
        "tax_lines_payload",
        "tax_summary_payload",
        'name="modal_account"',
        'name="modal_unit"',
    ):
        assert retirado not in html
    for admitido in ("'cost_center_' + index", "'project_' + index", "'remarks_' + index"):
        assert admitido in html


def test_la_macro_compartida_conserva_el_contrato_de_compras(app):
    """El default de la macro mantiene cuenta, unidad e impuestos."""
    from flask import get_template_attribute

    with app.test_request_context("/buying/purchase-invoice/new"):
        default = get_template_attribute("transaction_form_macros.html", "transaction_grid")()
        inventario = get_template_attribute("transaction_form_macros.html", "transaction_grid")(
            include_line_account=False, include_line_unit=False, include_taxes=False
        )
    for obligatorio in ("'account_' + index", "'unit_' + index", "tax_lines_payload", 'name="modal_account"'):
        assert obligatorio in default
        assert obligatorio not in inventario
