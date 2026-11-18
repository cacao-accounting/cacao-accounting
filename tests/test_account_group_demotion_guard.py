# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""No se puede desmarcar como grupo una cuenta contable con cuentas hijas (#2139).

``editar_cuenta`` (contabilidad/routes.py) bloquea quitar la condición de grupo cuando
``_account_descendant_codes`` encuentra descendientes: responde con un flash traducido,
sin confirmar cambios en la base de datos. Una cuenta grupo sin hijas sí puede
desmarcarse normalmente.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.services import _account_descendant_codes
from cacao_accounting.database import Accounts, database

MENSAJE_GUARDIA = "No se puede quitar la condición de grupo porque la cuenta tiene cuentas hijas."


@pytest.fixture
def catalogo_qa(app):
    """Crea un grupo con hija, un grupo sin hijos y conserva códigos únicos por prueba."""
    sufijo = uuid4().hex[:6].upper()
    escenario = {
        "grupo": f"AG{sufijo}",
        "hija": f"AC{sufijo}",
        "grupo_libre": f"AL{sufijo}",
    }
    with app.app_context():
        database.session.add(
            Accounts(
                entity="cacao",
                code=escenario["grupo"],
                name="Grupo QA con hija",
                group=True,
                active=True,
                enabled=True,
                classification="asset",
            )
        )
        database.session.flush()
        database.session.add(
            Accounts(
                entity="cacao",
                code=escenario["hija"],
                name="Cuenta hija QA",
                group=False,
                active=True,
                enabled=True,
                classification="asset",
                parent=escenario["grupo"],
            )
        )
        database.session.add(
            Accounts(
                entity="cacao",
                code=escenario["grupo_libre"],
                name="Grupo QA sin hijos",
                group=True,
                active=True,
                enabled=True,
                classification="asset",
            )
        )
        database.session.commit()
        for clave, codigo in (("grupo", escenario["grupo"]), ("grupo_libre", escenario["grupo_libre"])):
            escenario[f"{clave}_id"] = str(
                database.session.execute(database.select(Accounts.id).filter_by(entity="cacao", code=codigo)).scalar_one()
            )

    yield escenario

    with app.app_context():
        for codigo in (escenario["hija"], escenario["grupo"], escenario["grupo_libre"]):
            cuenta = database.session.execute(
                database.select(Accounts).filter_by(entity="cacao", code=codigo)
            ).scalar_one_or_none()
            if cuenta is not None:
                database.session.delete(cuenta)
        database.session.commit()


def _datos_edicion_sin_grupo(codigo: str, nombre: str) -> dict[str, str]:
    """POST de edición de cuenta dejando la casilla de grupo desmarcada."""
    return {
        "code": codigo,
        "name": nombre,
        "entidad": "cacao",
        "activo": "y",
    }


def test_descendientes_sustentan_la_guardia(app, catalogo_qa):
    """La cuenta hija aparece como descendiente del grupo y el grupo libre no tiene hijas."""
    with app.app_context():
        assert catalogo_qa["hija"] in _account_descendant_codes("cacao", catalogo_qa["grupo"])
        assert _account_descendant_codes("cacao", catalogo_qa["grupo_libre"]) == set()


def test_no_se_desmarca_grupo_con_cuentas_hijas(app, authenticated_client, catalogo_qa):
    """El POST de desmarcado regresa al formulario con el flash de guardia y no confirma cambios."""
    response = authenticated_client().post(
        f"/accounting/account/{catalogo_qa['grupo_id']}/edit",
        data=_datos_edicion_sin_grupo(catalogo_qa["grupo"], "Grupo QA con hija"),
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert b"Internal Server Error" not in response.data
    assert "grupo" in html.lower() and ("hija" in html.lower() or "hijo" in html.lower() or "cuentas" in html.lower())
    with app.app_context():
        grupo = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code=catalogo_qa["grupo"])
        ).scalar_one()
        assert grupo.group is True
        assert grupo.name == "Grupo QA con hija"


def test_grupo_sin_hijas_puede_desmarcarse(app, authenticated_client, catalogo_qa):
    """Una cuenta grupo hoja acepta el desmarcado y persiste group=False."""
    response = authenticated_client().post(
        f"/accounting/account/{catalogo_qa['grupo_libre_id']}/edit",
        data=_datos_edicion_sin_grupo(catalogo_qa["grupo_libre"], "Grupo QA sin hijos actualizado"),
    )

    assert response.status_code == 302
    with app.app_context():
        cuenta = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code=catalogo_qa["grupo_libre"])
        ).scalar_one()
        assert cuenta.group is False
        assert cuenta.active is True
        assert cuenta.enabled is True
        assert cuenta.name == "Grupo QA sin hijos actualizado"
