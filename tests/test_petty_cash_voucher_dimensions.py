# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Dimensiones analíticas de caja chica limitadas a la compañía.

Escenario de negocio: un vale o gasto de caja chica de ``cacao`` no puede
referenciar centro de costo, unidad de negocio o proyecto de ``alpha``. Los
Smart Selects de la UI filtran, pero el servicio debe rechazar el payload
aunque llegue manipulado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.services import (
    create_petty_cash_expense,
    create_petty_cash_expense_from_voucher,
    create_petty_cash_voucher,
    set_petty_cash_voucher_status,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    CostCenter,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashVoucher,
    Project,
    Unit,
    GLEntry,
    User,
    database,
)

FECHA = date(2026, 10, 20)


@pytest.fixture
def caja_dimensiones():
    """Dos compañías con dimensiones homónimas y un fondo en cacao."""
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
                Modules(module="cash", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
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
        database.session.flush()
        caja = Accounts(
            code="1.01.05.001",
            name="Caja Chica",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        gasto = Accounts(
            code="5.01.01.001",
            name="Gastos Operativos",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="expense",
        )
        database.session.add_all([caja, gasto])
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=caja.id,
            name="Fondo Cacao",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        dimensiones = {}
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
        ids = {
            "fondo": fondo.id,
            "cuenta_gasto": gasto.code,
            "dimensiones": dimensiones,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _crear_vale(ids, dimensiones, **extra):
    return create_petty_cash_voucher(
        company="cacao",
        petty_cash_id=ids["fondo"],
        posted_date=FECHA,
        delivered_to="Cajero",
        concept="Vale de prueba",
        amount=Decimal("50"),
        cost_center_code=dimensiones["centro"],
        unit_code=dimensiones["unidad"],
        project_code=dimensiones["proyecto"],
        **extra,
    )


def test_vale_rechaza_dimensiones_de_otra_compania(caja_dimensiones):
    """El vale no se persiste si una dimensión pertenece a alpha."""
    application, ids = caja_dimensiones
    ajenas = ids["dimensiones"]["alpha"]

    with application.app_context():
        with pytest.raises(ValueError, match="compañía"):
            _crear_vale(ids, ajenas)
        assert database.session.execute(database.select(PettyCashVoucher)).scalars().all() == []


def test_vale_acepta_dimensiones_de_su_compania(caja_dimensiones):
    """Control positivo: las dimensiones de cacao sí se persisten."""
    application, ids = caja_dimensiones
    propias = ids["dimensiones"]["cacao"]

    with application.app_context():
        vale = _crear_vale(ids, propias)
        assert vale.cost_center_code == propias["centro"]
        assert vale.unit_code == propias["unidad"]
        assert vale.project_code == propias["proyecto"]


def test_gasto_rechaza_centro_de_costo_ajeno(caja_dimensiones):
    """La liquidación tampoco acepta dimensiones de otra compañía."""
    application, ids = caja_dimensiones
    ajenas = ids["dimensiones"]["alpha"]

    with application.app_context():
        with pytest.raises(ValueError, match="compañía"):
            create_petty_cash_expense(
                company="cacao",
                petty_cash_id=ids["fondo"],
                expense_account_code=ids["cuenta_gasto"],
                concept="Gasto con dimensión ajena",
                amount=Decimal("10"),
                cost_center_code=ajenas["centro"],
                unit_code=ajenas["unidad"],
                project_code=ajenas["proyecto"],
                posted_date=FECHA,
            )
        assert database.session.execute(database.select(PettyCashExpense)).scalars().all() == []


def test_gasto_rechaza_unidad_ajena_con_centro_propio(caja_dimensiones):
    """El ownership de unidad y proyecto no depende del centro de costo."""
    application, ids = caja_dimensiones
    propias = ids["dimensiones"]["cacao"]
    ajenas = ids["dimensiones"]["alpha"]

    with application.app_context():
        with pytest.raises(ValueError, match="unidad de negocio"):
            create_petty_cash_expense(
                company="cacao",
                petty_cash_id=ids["fondo"],
                expense_account_code=ids["cuenta_gasto"],
                concept="Gasto con unidad ajena",
                amount=Decimal("10"),
                cost_center_code=propias["centro"],
                unit_code=ajenas["unidad"],
                project_code=propias["proyecto"],
                posted_date=FECHA,
            )
        assert database.session.execute(database.select(PettyCashExpense)).scalars().all() == []


def test_liquidacion_rechaza_unidad_ajena_sin_mutar_el_vale(caja_dimensiones):
    """Un vale heredado con unidad ajena no se liquida ni postea."""
    application, ids = caja_dimensiones
    propias = ids["dimensiones"]["cacao"]
    ajenas = ids["dimensiones"]["alpha"]

    with application.app_context():
        vale = PettyCashVoucher(
            company="cacao",
            petty_cash_id=ids["fondo"],
            posting_date=FECHA,
            delivered_to="Cajero",
            concept="Vale heredado",
            amount=Decimal("25"),
            cost_center_code=propias["centro"],
            unit_code=ajenas["unidad"],
            project_code=ajenas["proyecto"],
            voucher_status="entregado",
            docstatus=1,
        )
        database.session.add(vale)
        database.session.commit()
        vale_id = vale.id

        with pytest.raises(ValueError, match="unidad de negocio"):
            create_petty_cash_expense_from_voucher(
                vale,
                expense_account_code=ids["cuenta_gasto"],
                cost_center_code=propias["centro"],
                posted_date=FECHA,
            )
        database.session.rollback()

        vale = database.session.get(PettyCashVoucher, vale_id)
        assert vale.voucher_status == "entregado"
        assert vale.expense_id is None
        assert database.session.execute(database.select(PettyCashExpense)).scalars().all() == []


def test_liquidacion_acepta_dimensiones_propias(caja_dimensiones):
    """Control positivo: la liquidación con dimensiones de cacao postea."""
    application, ids = caja_dimensiones
    propias = ids["dimensiones"]["cacao"]

    with application.app_context():
        vale = _crear_vale(ids, propias)
        vale = set_petty_cash_voucher_status(vale, "entregado")
        gasto = create_petty_cash_expense_from_voucher(
            vale,
            expense_account_code=ids["cuenta_gasto"],
            cost_center_code=propias["centro"],
            posted_date=FECHA,
            actor_id="admin",
        )
        database.session.commit()

        assert gasto.id is not None
        assert vale.voucher_status == "liquidado"
        assert vale.expense_id == gasto.id
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=gasto.journal_id)).scalars().all()
        assert asientos
