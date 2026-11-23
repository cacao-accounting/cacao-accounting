# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2038: conciliación bancaria exige y selecciona compañía explícita."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Bank, BankAccount, database


def test_panel_muestra_selector_con_multiples_companias(app, reference_users, authenticated_client):
    """Con más de una compañía el panel presenta el selector y oculta el POST."""
    del reference_users
    response = authenticated_client("admin").get("/cash_management/bank-reconciliation")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert 'id="reconciliation_company"' in cuerpo
    assert 'value="cacao"' in cuerpo
    assert 'value="alpha"' in cuerpo
    assert 'name="company"' in cuerpo


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
