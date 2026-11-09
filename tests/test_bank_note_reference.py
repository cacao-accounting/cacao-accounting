# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Referencia externa de notas bancarias.

Escenario de negocio: la referencia informativa que el usuario escribe en una
nota de débito o crédito debe conservarse como ``reference_no`` del pago. No es
un número externo único ni consume contador; solo documenta el comprobante
externo que respalda la operación.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.services import (
    _create_payment_entry,
    _payment_payload_from_request,
)
from cacao_accounting.config import configuracion


@pytest.fixture
def app_bancos():
    """Aplicación mínima para resolver el contrato de la nota bancaria."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        from cacao_accounting.database import database

        database.create_all()
    yield application
    with application.app_context():
        from cacao_accounting.database import database

        database.session.remove()
        database.engine.dispose()


def _nota(payload: dict):
    """Construye el pago de nota con el payload ya interpretado."""
    return _create_payment_entry(
        payload,
        "debit_note",
        "cacao",
        None,
        None,
        Decimal("10"),
        "NIO",
        None,
        "transfer",
        None,
        None,
    )


def test_payload_json_conserva_la_referencia_como_reference_no(app_bancos):
    """El JSON de la nota traslada la referencia al campo canónico del pago."""
    with app_bancos.test_request_context(
        "/bancos/payment/new",
        method="POST",
        data={
            "payment_payload": json.dumps(
                {
                    "payment_type": "debit_note",
                    "company": "cacao",
                    "reference_no": "EXT-NOTA-123",
                    "mode_of_payment": "transfer",
                }
            )
        },
    ):
        payload = _payment_payload_from_request()
        pago = _nota(payload)

    assert payload["reference_no"] == "EXT-NOTA-123"
    assert pago.reference_no == "EXT-NOTA-123"


def test_formulario_sin_json_tambien_conserva_la_referencia(app_bancos):
    """El fallback de formulario no pierde la referencia si no hay JSON."""
    with app_bancos.test_request_context(
        "/bancos/payment/new",
        method="POST",
        data={
            "payment_type": "debit_note",
            "company": "cacao",
            "reference_no": "EXT-FORM-456",
            "mode_of_payment": "transfer",
        },
    ):
        payload = _payment_payload_from_request()
        pago = _nota(payload)

    assert payload["reference_no"] == "EXT-FORM-456"
    assert pago.reference_no == "EXT-FORM-456"


def test_payload_legado_external_number_se_normaliza(app_bancos):
    """Un cliente previo que envía external_number no pierde el dato."""
    with app_bancos.test_request_context(
        "/bancos/payment/new",
        method="POST",
        data={
            "payment_payload": json.dumps(
                {
                    "payment_type": "debit_note",
                    "company": "cacao",
                    "external_number": "EXT-LEGADO-789",
                    "mode_of_payment": "transfer",
                }
            )
        },
    ):
        payload = _payment_payload_from_request()
        pago = _nota(payload)

    assert payload["reference_no"] == "EXT-LEGADO-789"
    assert pago.reference_no == "EXT-LEGADO-789"
