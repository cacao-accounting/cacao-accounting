# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2038: conciliación bancaria exige y selecciona compañía explícita."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    database,
)


def test_panel_muestra_selector_con_multiples_companias(app, reference_users, authenticated_client):
    """Con más de una compañía el panel presenta el selector y oculta el POST."""
    del reference_users
    response = authenticated_client("admin").get("/cash_management/bank-reconciliation")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert 'id="reconciliation_company"' in cuerpo
    assert 'value="cacao"' in cuerpo
    assert 'value="alpha"' in cuerpo
    assert 'name="company" value=""' in cuerpo
    assert "Conciliar seleccionados" not in cuerpo
    assert "Seleccione una compañía para conciliar transacciones." in cuerpo


def test_seleccion_de_compania_conserva_el_hidden_y_habilita_el_post(app, reference_users, authenticated_client):
    """Al elegir una compañía autorizada el formulario queda listo para enviarse."""
    del reference_users
    response = authenticated_client("admin").get("/cash_management/bank-reconciliation?company=cacao")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert 'name="company" value="cacao"' in cuerpo
    assert "Conciliar seleccionados" in cuerpo


def test_flujo_completo_selecciona_compania_y_aplica_conciliacion(app, entorno_contable, authenticated_client):
    """El formulario multiempresa selecciona cacao, conserva el hidden y aplica el POST."""
    del entorno_contable
    suffix = uuid4().hex[:6]
    with app.app_context():
        banco = Bank(name=f"Banco flujo {suffix}")
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name=f"Cuenta flujo {suffix}",
            account_no=f"F-{suffix}",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.flush()
        transaccion = BankTransaction(
            identity_key=f"flow-{suffix}",
            bank_account_id=cuenta.id,
            posting_date=date(2026, 5, 15),
            deposit=Decimal("100"),
            withdrawal=Decimal("0"),
            description="Depósito de prueba",
            is_reconciled=False,
        )
        pago = PaymentEntry(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            payment_type="receive",
            bank_account_id=cuenta.id,
            currency="NIO",
            received_amount=Decimal("100"),
            base_received_amount=Decimal("100"),
        )
        database.session.add_all([transaccion, pago])
        database.session.commit()
        cuenta_id, banco_id = cuenta.id, banco.id
        transaccion_id, pago_id = transaccion.id, pago.id

    client = authenticated_client("admin")
    reconciliation_id = None
    try:
        seleccion = client.get("/cash_management/bank-reconciliation?company=cacao")
        assert seleccion.status_code == 200
        cuerpo = seleccion.get_data(as_text=True)
        assert 'name="company" value="cacao"' in cuerpo
        assert f'name="bank_transaction_id" value="{transaccion_id}"' in cuerpo
        assert f"payment_entry:{pago_id}" in cuerpo

        respuesta = client.post(
            "/cash_management/bank-reconciliation/apply",
            data={
                "company": "cacao",
                "reconciliation_date": "2026-05-15",
                "bank_transaction_id": transaccion_id,
                f"target_{transaccion_id}": f"payment_entry:{pago_id}",
                f"amount_{transaccion_id}": "100",
                f"difference_{transaccion_id}": "0",
            },
        )

        assert respuesta.status_code == 302
        assert "company=cacao" in respuesta.headers["Location"]
        with app.app_context():
            item = database.session.execute(
                database.select(ReconciliationItem).filter_by(source_id=transaccion_id)
            ).scalar_one()
            assert item.target_id == pago_id
            assert item.allocated_amount == Decimal("100.0000")
            assert database.session.get(BankTransaction, transaccion_id).is_reconciled is True
            reconciliation_id = item.reconciliation_id
    finally:
        with app.app_context():
            database.session.execute(database.delete(ReconciliationItem).where(ReconciliationItem.source_id == transaccion_id))
            if reconciliation_id is not None:
                database.session.execute(database.delete(Reconciliation).where(Reconciliation.id == reconciliation_id))
            database.session.execute(database.delete(BankTransaction).where(BankTransaction.id == transaccion_id))
            database.session.execute(database.delete(PaymentEntry).where(PaymentEntry.id == pago_id))
            database.session.execute(database.delete(BankAccount).where(BankAccount.id == cuenta_id))
            database.session.execute(database.delete(Bank).where(Bank.id == banco_id))
            database.session.commit()


def test_panel_de_cuenta_presenta_la_compania_de_la_cuenta(app, entorno_contable, authenticated_client):
    """La ruta por cuenta pasa las compañías y no rompe la plantilla compartida."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        banco = Bank(name=f"Banco {sufijo}")
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta conciliación",
            account_no=f"C-{sufijo}",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        cuenta_id, banco_id = cuenta.id, banco.id

    try:
        response = authenticated_client("admin").get(f"/cash_management/bank-reconciliation/{cuenta_id}")

        assert response.status_code == 200
        cuerpo = response.get_data(as_text=True)
        assert 'id="reconciliation_company"' in cuerpo
        assert '<option value="cacao" selected>' in cuerpo
        assert 'name="company" value="cacao"' in cuerpo
    finally:
        with app.app_context():
            database.session.execute(database.delete(BankAccount).where(BankAccount.id == cuenta_id))
            database.session.execute(database.delete(Bank).where(Bank.id == banco_id))
            database.session.commit()


def test_compania_ajena_se_rechaza(app, reference_users, authenticated_client):
    """Un usuario de otra compañía no puede abrir el panel de cacao."""
    del reference_users
    response = authenticated_client("other_company").get("/cash_management/bank-reconciliation?company=cacao")

    assert response.status_code == 403
