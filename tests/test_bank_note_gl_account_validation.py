# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las notas bancarias solo aceptan cuentas GL activas, habilitadas y hoja.

Escenario de negocio (#2180): un borrador de nota bancaria apoyado en una cuenta
inactiva, deshabilitada o agrupadora debe rechazarse con error controlado sin
dejar pagos ni asientos persistidos; la misma cuenta se revalida al enviar el
borrador porque su estado pudo cambiar después de guardarlo.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    CompanyDefaultAccount,
    GLEntry,
    PaymentEntry,
    database,
)

MENSAJE_CUENTA_NO_OPERATIVA = "La cuenta GL del pago debe estar activa, habilitada y ser una cuenta hoja."
BANDERAS_INVALIDAS = {
    "inactiva": {"active": False, "enabled": True, "group": False},
    "deshabilitada": {"active": True, "enabled": False, "group": False},
    "agrupadora": {"active": True, "enabled": True, "group": True},
}
BANDERAS_VALIDAS = {"active": True, "enabled": True, "group": False}


def _crear_cuenta_gl(sufijo: str, banderas: dict) -> str:
    """Crea una cuenta contable bancaria con el estado operativo indicado."""
    cuenta = Accounts(
        entity="cacao",
        code=f"1102-{sufijo}",
        name=f"Bancos nota {sufijo}",
        classification="asset",
        account_type="bank",
        **banderas,
    )
    database.session.add(cuenta)
    database.session.flush()
    return str(cuenta.id)


def _crear_cuenta_bancaria(sufijo: str, gl_account_id: str) -> str:
    """Crea una cuenta bancaria activa en cacao enlazada a la cuenta GL dada."""
    banco = Bank(name=f"Banco notas {sufijo}")
    database.session.add(banco)
    database.session.flush()
    cuenta = BankAccount(
        company="cacao",
        bank_id=banco.id,
        account_name=f"Cuenta notas {sufijo}",
        account_no=f"NT-{sufijo}",
        currency="NIO",
        is_active=True,
        gl_account_id=gl_account_id,
    )
    database.session.add(cuenta)
    database.session.flush()
    return str(cuenta.id)


def _cuerpo_nota(cuenta_bancaria_id: str, cuenta_gl_id: str) -> str:
    """Payload de nota de débito bancaria tal como lo envía el formulario."""
    return json.dumps(
        {
            "payment_type": "debit_note",
            "company": "cacao",
            "bank_account_id": cuenta_bancaria_id,
            "posting_date": "2026-05-15",
            "paid_amount": "10",
            "paid_to_account_id": cuenta_gl_id,
        }
    )


@pytest.mark.parametrize("variante", sorted(BANDERAS_INVALIDAS))
def test_nota_debito_rechaza_cuenta_gl_no_operativa(entorno_contable, authenticated_client, variante):
    """El borrador no se crea ni deja asiento cuando la cuenta GL no es operativa."""
    app = entorno_contable.app
    with app.app_context():
        sufijo = uuid4().hex[:8]
        cuenta_gl_id = _crear_cuenta_gl(sufijo, BANDERAS_INVALIDAS[variante])
        cuenta_bancaria_id = _crear_cuenta_bancaria(sufijo, cuenta_gl_id)
        database.session.commit()
        pagos_antes = database.session.query(PaymentEntry).count()
        gl_antes = database.session.query(GLEntry).count()

    response = authenticated_client("admin").post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": _cuerpo_nota(cuenta_bancaria_id, cuenta_gl_id)},
    )

    assert response.status_code == 200
    assert MENSAJE_CUENTA_NO_OPERATIVA in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(PaymentEntry).count() == pagos_antes
        assert database.session.query(GLEntry).count() == gl_antes


def test_nota_debito_acepta_cuenta_gl_activa_hoja_como_borrador(entorno_contable, authenticated_client):
    """Con una cuenta GL operativa el borrador se crea sin asiento hasta enviarlo."""
    app = entorno_contable.app
    with app.app_context():
        sufijo = uuid4().hex[:8]
        cuenta_gl_id = _crear_cuenta_gl(sufijo, BANDERAS_VALIDAS)
        cuenta_bancaria_id = _crear_cuenta_bancaria(sufijo, cuenta_gl_id)
        database.session.commit()
        gl_antes = database.session.query(GLEntry).count()

    response = authenticated_client("admin").post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": _cuerpo_nota(cuenta_bancaria_id, cuenta_gl_id)},
    )

    assert response.status_code == 302
    with app.app_context():
        borrador = database.session.query(PaymentEntry).filter_by(paid_to_account_id=cuenta_gl_id).one()
        assert borrador.payment_type == "debit_note"
        assert borrador.company == "cacao"
        assert borrador.docstatus == 0
        gl_del_pago = database.session.query(GLEntry).filter_by(voucher_id=borrador.id, voucher_type="payment_entry")
        assert gl_del_pago.count() == gl_antes


def test_submit_revalida_cuenta_gl_desactivada_tras_el_borrador(entorno_contable, authenticated_client):
    """Enviar un borrador cuya cuenta GL quedó inactiva falla controlado y sin asiento."""
    app = entorno_contable.app
    with app.app_context():
        sufijo = uuid4().hex[:8]
        cuenta_gl_id = _crear_cuenta_gl(sufijo, BANDERAS_VALIDAS)
        cuenta_bancaria_id = _crear_cuenta_bancaria(sufijo, cuenta_gl_id)
        borrador = PaymentEntry(
            payment_type="debit_note",
            company="cacao",
            bank_account_id=cuenta_bancaria_id,
            posting_date=date(2026, 5, 15),
            docstatus=0,
            paid_amount=Decimal("10"),
            received_amount=Decimal("10"),
            currency="NIO",
            paid_to_account_id=cuenta_gl_id,
        )
        database.session.add(borrador)
        database.session.flush()
        pago_id = str(borrador.id)
        cuenta_gl = database.session.get(Accounts, cuenta_gl_id)
        cuenta_gl.active = False
        database.session.commit()
        gl_antes = database.session.query(GLEntry).count()

    response = authenticated_client("admin").post(f"/cash_management/payment/{pago_id}/submit", follow_redirects=True)

    assert response.status_code == 200
    assert MENSAJE_CUENTA_NO_OPERATIVA in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.get(PaymentEntry, pago_id).docstatus == 0
        assert database.session.query(GLEntry).count() == gl_antes


def test_submit_rechaza_default_expense_no_operativo(entorno_contable, authenticated_client):
    """El fallback de gasto por defecto también debe ser una cuenta imputable."""
    app = entorno_contable.app
    with app.app_context():
        sufijo = uuid4().hex[:8]
        banco_gl_id = _crear_cuenta_gl(sufijo, BANDERAS_VALIDAS)
        cuenta_bancaria_id = _crear_cuenta_bancaria(sufijo, banco_gl_id)
        gasto_invalido_id = _crear_cuenta_gl(sufijo + "G", BANDERAS_INVALIDAS["agrupadora"])
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        gasto_anterior = defaults.default_expense
        defaults.default_expense = gasto_invalido_id
        borrador = PaymentEntry(
            payment_type="debit_note",
            company="cacao",
            bank_account_id=cuenta_bancaria_id,
            posting_date=date(2026, 5, 15),
            docstatus=0,
            paid_amount=Decimal("10"),
            received_amount=Decimal("10"),
            currency="NIO",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(borrador)
        database.session.flush()
        pago_id = str(borrador.id)
        database.session.commit()
        gl_antes = database.session.query(GLEntry).count()

    try:
        response = authenticated_client("admin").post(
            f"/cash_management/payment/{pago_id}/submit",
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "activa, habilitada" in response.get_data(as_text=True)
        with app.app_context():
            assert database.session.get(PaymentEntry, pago_id).docstatus == 0
            assert database.session.query(GLEntry).count() == gl_antes
    finally:
        with app.app_context():
            defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
            defaults.default_expense = gasto_anterior
            database.session.commit()
