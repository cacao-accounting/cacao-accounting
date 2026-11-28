# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1874: precargar una entrada desde un origen hidrata compañía y moneda."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import DeliveryNote, PurchaseReceipt, StockEntry, database

URL = "/inventory/stock-entry/new"


def _origen() -> StockEntry:
    """Crea un movimiento de inventario que sirve como documento origen."""
    sufijo = uuid4().hex[:8]
    entry = StockEntry(
        company="cacao",
        purpose="material_receipt",
        posting_date=date(2026, 5, 15),
        transaction_currency="NIO",
        base_currency="NIO",
        document_no=f"SE-{sufijo}",
    )
    database.session.add(entry)
    database.session.commit()
    return entry


def test_origen_valido_hidrata_cabecera_bloqueada(app, authenticated_client):
    """La compañía y la moneda del origen llegan al formulario."""
    with app.app_context():
        origen_id = _origen().id
    client = authenticated_client("admin")

    response = client.get(f"{URL}?source_type=stock_entry&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": "stock_entry"' in body
    assert '"initialHeader"' in body
    assert '"company": "cacao"' in body
    assert '"currency": "NIO"' in body


def test_origen_inexistente_deja_los_campos_editables(app, authenticated_client):
    """Un origen inexistente no hidrata ni expone metadatos."""
    client = authenticated_client("admin")

    response = client.get(f"{URL}?source_type=stock_entry&source_id=NO-EXISTE")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": ""' in body
    assert '"initialHeader"' not in body


def test_origen_sin_moneda_deja_los_campos_editables(app, authenticated_client):
    """Un origen heredado sin moneda transaccional no bloquea la cabecera vacía."""
    with app.app_context():
        origen = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 15),
            transaction_currency=None,
            base_currency="NIO",
            document_no=f"SE-{uuid4().hex[:8]}",
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id

    response = authenticated_client("admin").get(f"{URL}?source_type=stock_entry&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": ""' in body
    assert '"initialHeader"' not in body


@pytest.mark.parametrize(
    ("modelo", "source_type", "prefijo"),
    [
        (PurchaseReceipt, "purchase_receipt", "PR"),
        (DeliveryNote, "delivery_note", "DN"),
    ],
)
def test_origenes_de_compra_y_venta_hidratan_cabecera(app, authenticated_client, modelo, source_type, prefijo):
    """Recepción de compra y nota de entrega aportan compañía y moneda del origen."""
    with app.app_context():
        origen = modelo(
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            document_no=f"{prefijo}-{uuid4().hex[:8]}",
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id

    response = authenticated_client("admin").get(f"{URL}?source_type={source_type}&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'"initialSourceType": "{source_type}"' in body
    assert '"company": "cacao"' in body
    assert '"currency": "NIO"' in body


def _usuario_solo_inventario_crear(app, *, con_lectura_inventario: bool = False):
    """Usuario con crear en inventario; lectura de origen controlable."""
    from werkzeug.security import generate_password_hash

    from cacao_accounting.database import Modules, Roles, RolesAccess, RolesUser, User, UserCompanyAccess

    uid = f"inv-only-{uuid4().hex[:8]}"
    with app.app_context():
        for mod in ("inventory", "purchases", "sales"):
            if database.session.execute(database.select(Modules).filter_by(module=mod)).scalar_one_or_none() is None:
                database.session.add(Modules(module=mod, default=False, enabled=True))
        database.session.flush()
        user = User(user=uid, e_mail=f"{uid}@test.local", password=generate_password_hash("test").encode("utf-8"), active=True)
        database.session.add(user)
        database.session.flush()
        role = Roles(name=f"role-{uid}", note="inv-only")
        database.session.add(role)
        database.session.flush()
        inv_mod = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        database.session.add(
            RolesAccess(
                rol_id=role.id,
                module_id=inv_mod,
                access=True,
                view=con_lectura_inventario,
                create=True,
            )
        )
        database.session.add(RolesUser(user_id=user.id, role_id=role.id, active=True))
        database.session.add(UserCompanyAccess(user_id=user.id, company_code="cacao"))
        database.session.commit()
        return user.id


def test_usuario_sin_lectura_origen_no_recibe_hidratacion(app):
    """#1874 QA: sin lectura del origen la respuesta es indistinguible de inexistente."""
    with app.app_context():
        origen = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            document_no=f"PR-{uuid4().hex[:8]}",
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id
    user_id = _usuario_solo_inventario_crear(app, con_lectura_inventario=False)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    with app.app_context():
        from cacao_accounting.database import User

        u = database.session.get(User, user_id)
        with client.session_transaction() as session:
            session["_auth_version"] = u.auth_version

    existente = client.get(f"{URL}?source_type=purchase_receipt&source_id={origen_id}")
    inexistente = client.get(f"{URL}?source_type=purchase_receipt&source_id=NO-EXISTE")

    assert existente.status_code == inexistente.status_code == 200
    body = existente.get_data(as_text=True)
    assert '"initialSourceType": ""' in body
    assert '"initialHeader"' not in body
    assert '"currency": "USD"' not in body


def test_usuario_con_lectura_origen_recibe_hidratacion(app):
    """#1874 QA: con permiso de lectura del origen se hidrata cabecera."""
    with app.app_context():
        origen = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            document_no=f"PR-{uuid4().hex[:8]}",
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id
    user_id = _usuario_solo_inventario_crear(app, con_lectura_inventario=True)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    with app.app_context():
        from cacao_accounting.database import User

        u = database.session.get(User, user_id)
        with client.session_transaction() as session:
            session["_auth_version"] = u.auth_version

    response = client.get(f"{URL}?source_type=purchase_receipt&source_id={origen_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"initialSourceType": "purchase_receipt"' in body
    assert '"currency": "USD"' in body
