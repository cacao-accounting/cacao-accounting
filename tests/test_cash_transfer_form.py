# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2044/#2039: transferencia bancaria conserva formulario y referencia.

Un rechazo de validación o permiso no debe perder el formulario de
transferencia ni dejar pagos parciales. La referencia externa capturada debe
persistirse en `PaymentEntry.reference_no`.
"""

from __future__ import annotations

from decimal import Decimal
import re
from uuid import uuid4

import pytest

from cacao_accounting.bancos import services as bank_services
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    Modules,
    PaymentEntry,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

RUTA = "/cash_management/payment/transfer/new"


@pytest.fixture
def transferencia(app, entorno_contable):
    """Dos cuentas bancarias de cacao con cuentas GL de tipo banco."""
    sufijo = uuid4().hex[:6].upper()
    with app.app_context():
        banco = Bank(name=f"Banco {sufijo}")
        database.session.add(banco)
        database.session.flush()
        cuenta_origen = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1102")).scalar_one()
        cuenta_origen.active = True
        cuenta_origen.enabled = True
        cuenta_origen.group = False
        cuenta_destino = Accounts(
            entity="cacao",
            code=f"1103{sufijo}",
            name="Banco destino",
            classification="asset",
            account_type="bank",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta_destino)
        database.session.flush()
        origen = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta origen",
            account_no=f"ORI-{sufijo}",
            gl_account_id=cuenta_origen.id,
            currency="NIO",
            is_active=True,
        )
        destino = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta destino",
            account_no=f"DST-{sufijo}",
            gl_account_id=cuenta_destino.id,
            currency="NIO",
            is_active=True,
        )
        database.session.add_all([origen, destino])
        database.session.commit()
        return {"origen": origen.id, "destino": destino.id, "sufijo": sufijo}


def _payload(cuentas: dict, referencia: str | None = None) -> dict[str, str]:
    """Formulario mínimo de una transferencia interna."""
    data = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": cuentas["origen"],
        "target_bank_account_id": cuentas["destino"],
        "posting_date": "2026-05-15",
        "paid_amount": "100",
        "currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "mode_of_payment": "transfer",
    }
    if referencia:
        data["reference_no"] = referencia
    return data


def _conteo_pagos(app) -> int:
    """Cantidad actual de pagos persistidos."""
    with app.app_context():
        return len(database.session.execute(database.select(PaymentEntry)).scalars().all())


def test_validation_error_rerenderiza_el_formulario_de_transferencia(app, transferencia, authenticated_client):
    """Un POST inválido conserva `bankTransferForm` y no persiste pagos."""
    antes = _conteo_pagos(app)
    client = authenticated_client("admin")

    response = client.post(RUTA, data={"payment_type": "internal_transfer"})

    assert response.status_code == 200
    assert "bankTransferForm" in response.get_data(as_text=True)
    assert _conteo_pagos(app) == antes


def test_usuario_sin_crear_recibe_403(app, transferencia):
    """Sin `cash.crear` la transferencia se rechaza antes de persistir."""
    sufijo = transferencia["sufijo"]
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        role = Roles(name=f"cash-view-{sufijo}", note="Solo consulta")
        user_id = f"cash-view-{sufijo}"
        database.session.add_all(
            [
                User(id=user_id, user=user_id, name="Consulta caja", password=b"unused", active=True, company="cacao"),
                role,
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=modulo.id, access=True, view=True, create=False),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="cacao"),
            ]
        )
        database.session.commit()
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    antes = _conteo_pagos(app)

    response = client.post(RUTA, data=_payload(transferencia))

    assert response.status_code == 403
    assert _conteo_pagos(app) == antes


def test_fallo_de_numeracion_revierte_y_recupera_el_formulario(app, transferencia, authenticated_client, monkeypatch):
    """Si falla la asignación del identificador, no queda pago parcial."""
    llamado = {"valor": False}

    def _falla(**_kwargs):
        llamado["valor"] = True
        raise ValueError("fallo de numeración")

    monkeypatch.setattr(bank_services, "assign_document_identifier", _falla)
    antes = _conteo_pagos(app)
    client = authenticated_client("admin")

    response = client.post(RUTA, data=_payload(transferencia))

    assert llamado["valor"] is True
    assert response.status_code == 200
    assert "bankTransferForm" in response.get_data(as_text=True)
    assert _conteo_pagos(app) == antes


def test_referencia_externa_se_persiste_en_reference_no(app, transferencia, authenticated_client):
    """La referencia capturada por la nota/transferencia llega a PaymentEntry."""
    referencia = f"REF-{uuid4().hex[:8]}"
    client = authenticated_client("admin")

    response = client.post(RUTA, data=_payload(transferencia, referencia))

    assert response.status_code == 302
    with app.app_context():
        pago = database.session.execute(database.select(PaymentEntry).filter_by(reference_no=referencia)).scalar_one()
        assert pago.reference_no == referencia
        assert pago.paid_amount == Decimal("100.0000")


def _nota_json(cuentas: dict, tipo: str, **referencia: str) -> dict[str, str]:
    """Formulario de nota como lo envía nota_nueva.html (JSON payment_payload)."""
    import json

    payload = {
        "payment_type": tipo,
        "company": "cacao",
        "bank_account_id": cuentas["origen"],
        "posting_date": "2026-05-15",
        "paid_amount": "100",
        "currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "mode_of_payment": "transfer",
        **referencia,
    }
    return {"payment_payload": json.dumps(payload)}


def test_nota_debito_persiste_external_number_legacy(app, transferencia, authenticated_client):
    """#2039: el JSON de la nota con `external_number` llega a reference_no."""
    referencia = f"ND-{uuid4().hex[:8]}"
    client = authenticated_client("admin")

    response = client.post(
        "/cash_management/payment/debit-note/new",
        data=_nota_json(transferencia, "debit_note", external_number=referencia),
    )

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        pago = database.session.execute(database.select(PaymentEntry).filter_by(reference_no=referencia)).scalar_one()
        assert pago.payment_type == "debit_note"


def test_nota_credito_persiste_reference_no(app, transferencia, authenticated_client):
    """#2039: la referencia de la nota de crédito se conserva al persistir."""
    referencia = f"NC-{uuid4().hex[:8]}"
    client = authenticated_client("admin")

    response = client.post(
        "/cash_management/payment/credit-note/new",
        data=_nota_json(transferencia, "credit_note", reference_no=referencia),
    )

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        pago = database.session.execute(database.select(PaymentEntry).filter_by(reference_no=referencia)).scalar_one()
        assert pago.payment_type == "credit_note"


def test_dos_notas_pueden_compartir_la_referencia_externa(app, transferencia, authenticated_client):
    """#2039: la referencia externa no es un identificador único del sistema."""
    referencia = f"COMPARTIDA-{uuid4().hex[:8]}"
    client = authenticated_client("admin")

    for _ in range(2):
        response = client.post(
            "/cash_management/payment/debit-note/new",
            data=_nota_json(transferencia, "debit_note", reference_no=referencia),
        )
        assert response.status_code == 302, response.get_data(as_text=True)

    with app.app_context():
        pagos = database.session.execute(database.select(PaymentEntry).filter_by(reference_no=referencia)).scalars().all()
        assert len(pagos) == 2
        assert all(pago.payment_type == "debit_note" for pago in pagos)


def test_la_nota_no_consume_contadores_externos(app, transferencia, authenticated_client):
    """#2039: postear una nota no avanza contadores ni auditoría externa."""
    from cacao_accounting.database import (
        ExternalCounter,
        ExternalCounterAuditLog,
        SeriesExternalCounterMap,
        database,
    )

    with app.app_context():
        contadores = {
            (contador.id, contador.last_used)
            for contador in database.session.execute(database.select(ExternalCounter)).scalars().all()
        }
        auditoria = len(database.session.execute(database.select(ExternalCounterAuditLog)).scalars().all())
        mapeos = len(database.session.execute(database.select(SeriesExternalCounterMap)).scalars().all())

    referencia = f"EXT-{uuid4().hex[:8]}"
    response = authenticated_client("admin").post(
        "/cash_management/payment/debit-note/new",
        data=_nota_json(transferencia, "debit_note", reference_no=referencia),
    )

    assert response.status_code == 302, response.get_data(as_text=True)
    with app.app_context():
        contadores_despues = {
            (contador.id, contador.last_used)
            for contador in database.session.execute(database.select(ExternalCounter)).scalars().all()
        }
        assert contadores_despues == contadores
        assert len(database.session.execute(database.select(ExternalCounterAuditLog)).scalars().all()) == auditoria
        assert len(database.session.execute(database.select(SeriesExternalCounterMap)).scalars().all()) == mapeos


def test_rechazo_conserva_los_datos_del_formulario(app, transferencia, authenticated_client):
    """#2044: un rechazo devuelve el formulario con los datos enviados."""
    referencia = f"REF-{uuid4().hex[:8]}"
    antes = _conteo_pagos(app)
    client = authenticated_client("admin")
    data = _payload(transferencia, referencia)
    data["target_bank_account_id"] = "CUENTA-INEXISTENTE"

    response = client.post(RUTA, data=data)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "bankTransferForm" in html
    assert referencia in html
    assert "CUENTA-INEXISTENTE" in html
    assert re.search(r'initialValue:\s*"' + re.escape(str(data["bank_account_id"])) + '"', html)
    assert re.search(r'initialValue:\s*"CUENTA-INEXISTENTE"', html)
    assert re.search(r'"reference_no":\s*"' + re.escape(referencia) + '"', html)
    assert _conteo_pagos(app) == antes
