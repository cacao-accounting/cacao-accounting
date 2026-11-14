# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Centro de costo obligatorio en el gasto de caja chica (#2032).

Escenario de negocio: toda liquidación de caja chica debe cargarse a un
centro de costo para que la analítica cuadre. La exigencia vive en tres
capas: el smart select marca el campo como requerido en el formulario, el
formulario WTForms valida ``DataRequired`` y el servicio rechaza el gasto sin
centro de costo antes de generar el asiento contable.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.bancos.forms import FormularioPettyCashExpense
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    ComprobanteContable,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-gasto-centro-costos-2026"
FECHA = date(2026, 11, 16)


@pytest.fixture
def caja_gasto_centro_costo():
    """Compañía con fondo, cuenta de gasto y centro de costo contabilizables."""
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
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="liquidador-gastos",
                    user="liquidador-gastos",
                    name="Liquidador de Gastos",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="liquidador-gastos", company_code="cacao"))
        database.session.flush()
        rol_liquidador = Roles(name="cash-crea-gastos", note="Liquida gastos de caja chica")
        database.session.add(rol_liquidador)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add(
            RolesAccess(rol_id=rol_liquidador.id, module_id=modulo_caja.id, access=True, create=True, view=True)
        )
        modulo_contable = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one()
        database.session.add(
            RolesAccess(
                rol_id=rol_liquidador.id,
                module_id=modulo_contable.id,
                access=True,
                create=True,
                approve=True,
                view=True,
            )
        )
        database.session.add(RolesUser(user_id="liquidador-gastos", role_id=rol_liquidador.id, active=True))
        database.session.flush()
        database.session.add_all(
            [
                Accounts(
                    code="1.01.05.001",
                    name="Caja Chica Gastos",
                    entity="cacao",
                    group=False,
                    active=True,
                    enabled=True,
                    account_type="petty_cash",
                ),
                Accounts(
                    code="5.01.01.001",
                    name="Suministros de oficina",
                    entity="cacao",
                    group=False,
                    active=True,
                    enabled=True,
                    classification="expense",
                    account_type="expense",
                ),
                CostCenter(code="CC-GASTO", name="Administracion", entity="cacao", active=True, enabled=True),
                Book(
                    entity="cacao",
                    code="LIBRO-GASTOS",
                    name="Libro principal de gastos",
                    status="activo",
                    currency="NIO",
                    is_primary=True,
                ),
            ]
        )
        anio_fiscal = FiscalYear(
            entity="cacao",
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(anio_fiscal)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=anio_fiscal.id,
                name="Noviembre 2026",
                status="open",
                enabled=True,
                is_closed=False,
                start=date(2026, 11, 1),
                end=date(2026, 11, 30),
            )
        )
        fondo = PettyCashAccount(
            company="cacao",
            account_id=database.session.execute(
                database.select(Accounts.id).filter_by(entity="cacao", code="1.01.05.001")
            ).scalar_one(),
            name="Fondo Gasto Centro Costo",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        ids = {"fondo": fondo.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "liquidador-gastos", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _postear_gasto(client, ids, **reemplazos):
    """POSTea la liquidación de un gasto de caja chica directo."""
    datos = {
        "company": "cacao",
        "petty_cash_id": ids["fondo"],
        "posting_date": FECHA.isoformat(),
        "beneficiary": "Papeleria Central",
        "concept": "Compra de resmas de papel",
        "expense_account_code": "5.01.01.001",
        "amount": "25.00",
        "cost_center_code": "CC-GASTO",
    }
    for clave, valor in reemplazos.items():
        if valor is None:
            datos.pop(clave, None)
        else:
            datos[clave] = valor
    return client.post("/cash_management/petty-cash-expense/new", data=datos)


def test_gasto_sin_centro_de_costo_rechaza_con_mensaje_del_guard(caja_gasto_centro_costo):
    """El servicio rechaza el gasto sin centro de costo y no genera asiento."""
    application, ids = caja_gasto_centro_costo
    client = application.test_client()
    _iniciar(client)

    response = _postear_gasto(client, ids, cost_center_code=None)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "requiere un centro de costo" in cuerpo
    with application.app_context():
        assert database.session.execute(database.select(PettyCashExpense)).scalars().all() == []
        assert database.session.execute(database.select(ComprobanteContable)).scalars().all() == []
        assert database.session.execute(database.select(GLEntry)).scalars().all() == []


def test_gasto_con_centro_de_costo_se_persiste_y_postea(caja_gasto_centro_costo):
    """Control positivo: con centro de costo el gasto contabiliza balanceado."""
    application, ids = caja_gasto_centro_costo
    client = application.test_client()
    _iniciar(client)

    response = _postear_gasto(client, ids)

    assert response.status_code == 302, response.get_data(as_text=True)
    with application.app_context():
        gasto = database.session.execute(database.select(PettyCashExpense)).scalar_one()
        assert gasto.docstatus == 1
        assert gasto.cost_center_code == "CC-GASTO"
        assert gasto.amount == Decimal("25.0000")
        asiento = database.session.get(ComprobanteContable, gasto.journal_id)
        assert asiento is not None and asiento.status == "submitted"
        asientos = (
            database.session.execute(database.select(GLEntry).filter_by(voucher_id=gasto.journal_id, is_cancelled=False))
            .scalars()
            .all()
        )
        assert len(asientos) == 2
        assert sum((entry.debit for entry in asientos), Decimal("0")) == Decimal("25.0000")
        assert sum((entry.credit for entry in asientos), Decimal("0")) == Decimal("25.0000")
        assert {(entry.account_code, entry.debit, entry.credit) for entry in asientos} == {
            ("5.01.01.001", Decimal("25.0000"), Decimal("0.0000")),
            ("1.01.05.001", Decimal("0.0000"), Decimal("25.0000")),
        }


def test_formulario_marca_centro_de_costo_requerido(caja_gasto_centro_costo):
    """El GET del formulario exige el centro de costo en la UI y en el formulario."""
    application, _ids = caja_gasto_centro_costo
    client = application.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-expense/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    # El smart select del centro de costo renderiza el atributo required; el
    # de unidad de negocio (opcional) no lo hace.
    assert re.search(r'placeholder="Buscar Centro de costo"\s+required', cuerpo)
    assert not re.search(r'placeholder="Buscar Unidad de negocio"\s+required', cuerpo)

    with application.test_request_context("/cash_management/petty-cash-expense/new"):
        formulario = FormularioPettyCashExpense()
        validadores = [type(validador).__name__ for validador in formulario.cost_center_code.validators]
    assert "DataRequired" in validadores
