# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2085: el listado de cuentas bancarias conserva la compañía."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Accounts, Bank, BankAccount, database


def test_busqueda_y_paginacion_conservan_company(app, entorno_contable, authenticated_client):
    """El filtro explícito no se pierde al buscar ni al avanzar de página."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        banco = Bank(name=f"Banco {suffix}", is_active=True)
        cuenta_gl = Accounts(
            code=f"BANK-{suffix}",
            name="Cuenta bancaria",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        database.session.add_all([banco, cuenta_gl])
        database.session.flush()
        for index in range(12):
            database.session.add(
                BankAccount(
                    company="cacao",
                    bank_id=banco.id,
                    account_name=f"Cuenta {suffix} {index:02d}",
                    account_no=f"{suffix}-{index:02d}",
                    gl_account_id=cuenta_gl.id,
                    currency="NIO",
                    is_active=True,
                )
            )
        database.session.commit()

    response = authenticated_client().get("/cash_management/bank-account/list?company=cacao")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="company" value="cacao"' in html
    assert "company=cacao" in html
    assert "page=2" in html
