# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1993: el conteo de cuentas configuradas refleja asignaciones reales.

La tabla de compañías configuradas mostraba el total de definiciones (26) en
lugar de cuántas cuentas tienen valor. La regresión contrasta una compañía con
una sola cuenta asignada y otra sin cuentas.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, CompanyDefaultAccount, Entity, Modules, database


@pytest.fixture
def cuentas_predeterminadas_demo(app):
    """Dos compañías: una con default_cash y otra sin cuentas asignadas."""
    sufijo = uuid4().hex[:6]
    con_cuenta = f"a{sufijo}"
    sin_cuenta = f"b{sufijo}"
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            creado = True
        else:
            creado = False
            anterior = modulo.enabled
            modulo.enabled = True
        for code in (con_cuenta, sin_cuenta):
            database.session.add(
                Entity(
                    code=code,
                    name=f"Compañía {code}",
                    company_name=f"Compañía {code} SA",
                    tax_id=f"TAX-{code}",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                )
            )
        database.session.flush()
        cuenta = Accounts(
            entity=con_cuenta,
            code=f"1.01.{sufijo[:4]}",
            name="Cuenta de efectivo",
            account_type="cash",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        database.session.add_all(
            [
                CompanyDefaultAccount(company=con_cuenta, default_cash=cuenta.id),
                CompanyDefaultAccount(company=sin_cuenta),
            ]
        )
        database.session.commit()
    yield con_cuenta, sin_cuenta
    with app.app_context():
        database.session.execute(
            database.delete(CompanyDefaultAccount).where(CompanyDefaultAccount.company.in_([con_cuenta, sin_cuenta]))
        )
        database.session.execute(database.delete(Accounts).where(Accounts.entity == con_cuenta))
        database.session.execute(database.delete(Entity).where(Entity.code.in_([con_cuenta, sin_cuenta])))
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def _conteo_en_fila(cuerpo: str, company: str) -> str:
    """Extrae el contador de la fila de la compañía indicada."""
    fila = re.search(rf"<tr>\s*<td><a [^>]*>{company}</a></td>\s*<td>(\d+)</td>", cuerpo)
    assert fila is not None, f"No se encontró la fila de {company}."
    return fila.group(1)


def test_el_conteo_refleja_las_cuentas_asignadas(app, authenticated_client, cuentas_predeterminadas_demo):
    """Una cuenta asignada cuenta 1 y una compañía vacía cuenta 0."""
    con_cuenta, sin_cuenta = cuentas_predeterminadas_demo

    response = authenticated_client("admin").get(f"/settings/default-accounts?company={con_cuenta}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert _conteo_en_fila(cuerpo, con_cuenta) == "1"
    assert _conteo_en_fila(cuerpo, sin_cuenta) == "0"
