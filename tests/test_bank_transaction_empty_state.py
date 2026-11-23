# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2026: el listado bancario muestra un estado vacío accesible."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Bank, BankAccount, BankTransaction, User, database

URL = "/cash_management/bank-transaction/list"
MENSAJE_VACIO = "No hay transacciones bancarias para los filtros seleccionados."


def _client(application):
    """Cliente autenticado para la app aislada del escenario."""
    with application.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user_id = str(usuario.id)
        auth_version = usuario.auth_version
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def test_listado_sin_transacciones_muestra_estado_vacio(entorno_contable_aislado):
    """Sin resultados se anuncia el estado vacío y no se pinta la tabla."""
    application = entorno_contable_aislado.app
    response = _client(application).get(URL)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert MENSAJE_VACIO in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert "Listado de transacciones bancarias." not in html


def test_listado_con_transacciones_no_muestra_estado_vacio(entorno_contable_aislado):
    """Con resultados se muestra la fila y desaparece el estado vacío."""
    application = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with application.app_context():
        banco = Bank(name=f"Banco {sufijo}", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            account_name=f"Cuenta {sufijo}",
            account_no=f"ACC-{sufijo}",
            bank_id=banco.id,
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.flush()
        database.session.add(
            BankTransaction(
                identity_key=f"TX-{sufijo}",
                bank_account_id=cuenta.id,
                posting_date=date(2026, 5, 15),
                description=f"Depósito {sufijo}",
                deposit=Decimal("100"),
                is_reconciled=False,
            )
        )
        database.session.commit()

    response = _client(application).get(URL)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f"Depósito {sufijo}" in html
    assert MENSAJE_VACIO not in html
