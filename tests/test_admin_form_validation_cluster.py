# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación server-side de formularios administrativos y fiscales.

Escenario de negocio (paraguas #1717):
- #1742: helpers decimal/fecha devolvían 500 con entradas malformadas.
- #1974: el CRUD de años fiscales persistía rangos invertidos.
- #1995: la matriz de aprobación aceptaba roles/usuarios inexistentes.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    ApprovalMatrix,
    Currency,
    Entity,
    FiscalYear,
    Item,
    ItemPrice,
    Modules,
    PriceList,
    Roles,
    Tax,
    UOM,
    User,
    database,
)


def _crear_app():
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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                UOM(code="UND", name="Unidad", is_active=True),
                Roles(name="approver", note="Aprobador"),
            ]
        )
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(code="ART-1", name="Artículo", item_type="goods", default_uom="UND", is_active=True),
                PriceList(name="Ventas", company="cacao", currency="NIO", is_selling=True, is_active=True),
            ]
        )
        database.session.commit()
        ids = {
            "price_list": database.session.execute(database.select(PriceList)).scalar_one().id,
            "role": database.session.execute(database.select(Roles).filter_by(name="approver")).scalar_one().id,
        }
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_impuesto_con_tasa_no_numerica_no_responde_500():
    """#1742: un decimal malformado vuelve con error controlado."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/taxes", data={"name": "IVA", "rate": "not-a-number"})

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(Tax)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("price", "not-a-number"),
        ("valid_from", "2026-99-42"),
    ],
)
def test_precio_item_con_dato_malformado_no_responde_500(campo, valor):
    """#1742: número o fecha inválidos no crean la tarifa."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        datos = {
            "price_list_id": ids["price_list"],
            "item_code": "ART-1",
            "uom": "UND",
            "price": "10",
            "min_qty": "0",
        }
        datos[campo] = valor
        respuesta = client.post("/settings/item-prices", data=datos)

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(ItemPrice)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_conciliacion_con_tolerancia_invalida_no_responde_500():
    """#1742: la configuración de matching tampoco propaga el error interno."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/purchase-reconciliation",
            data={"company": "cacao", "price_tolerance_value": "x", "qty_tolerance_value": "0"},
        )

        assert respuesta.status_code == 302
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_anio_fiscal_no_persiste_rango_invertido():
    """#1974: el alta rechaza inicio posterior al fin."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/accounting/fiscal_year/new",
            data={"id": "FY-REVERSED", "entidad": "cacao", "inicio": "2026-12-31", "fin": "2026-01-01"},
        )

        assert respuesta.status_code == 200
        assert "La fecha final no puede ser anterior a la fecha de inicio." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(FiscalYear)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_de_anio_fiscal_conserva_el_rango_valido():
    """#1974: la edición tampoco persiste un rango invertido."""
    application, _ids = _crear_app()
    try:
        with application.app_context():
            anio = FiscalYear(
                entity="cacao",
                name="FY-1",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
            )
            database.session.add(anio)
            database.session.commit()
            anio_id = anio.id

        client = _cliente(application)
        respuesta = client.post(
            f"/accounting/fiscal_year/{anio_id}/edit",
            data={"id": "FY-1", "entidad": "cacao", "inicio": "2026-12-31", "fin": "2026-01-01"},
        )

        assert respuesta.status_code == 200
        with application.app_context():
            anio = database.session.get(FiscalYear, anio_id)
            assert anio is not None
            assert anio.year_start_date == date(2026, 1, 1)
            assert anio.year_end_date == date(2026, 12, 31)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("role_id", "missing-role"),
        ("user_id", "missing-user"),
    ],
)
def test_matriz_rechaza_referencias_inexistentes(campo, valor):
    """#1995: rol/usuario inexistente no se persiste ni responde 500."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/approval-matrix",
            data={
                "action": "add_rule",
                "company": "cacao",
                "document_type": "purchase_order",
                campo: valor,
                "min_amount": "0",
                "approval_level": "1",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(ApprovalMatrix)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_matriz_rechaza_regla_sin_receptor():
    """#1995: una regla sin rol ni usuario no tiene receptor válido."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/approval-matrix",
            data={
                "action": "add_rule",
                "company": "cacao",
                "document_type": "purchase_order",
                "min_amount": "0",
                "approval_level": "1",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(ApprovalMatrix)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_matriz_acepta_rol_existente():
    """#1995: la referencia válida sigue creando la regla."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/approval-matrix",
            data={
                "action": "add_rule",
                "company": "cacao",
                "document_type": "purchase_order",
                "role_id": ids["role"],
                "min_amount": "0",
                "approval_level": "1",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            regla = database.session.execute(database.select(ApprovalMatrix)).scalar_one()
            assert regla.role_id == ids["role"]
            assert regla.user_id is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_periodo_contable_no_persiste_rango_invertido():
    """#1941: el alta de período rechaza inicio posterior al fin."""
    application, _ids = _crear_app()
    try:
        with application.app_context():
            anio = FiscalYear(
                entity="cacao",
                name="FY-1",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
            )
            database.session.add(anio)
            database.session.commit()
            anio_id = anio.id

        client = _cliente(application)
        respuesta = client.post(
            "/accounting/accounting_period/new",
            data={
                "id": "P-REVERSED",
                "entidad": "cacao",
                "fiscal_year": anio_id,
                "nombre": "Período invertido",
                "inicio": "2026-12-31",
                "fin": "2026-01-01",
            },
        )

        assert respuesta.status_code == 200
        assert "La fecha final no puede ser anterior a la fecha de inicio." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(AccountingPeriod)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
