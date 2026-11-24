# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1703: el número visible de confirmación no colisiona con ULID próximos."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.balance_confirmation import (
    _balance_confirmation_document_no,
    create_balance_confirmation,
)
from cacao_accounting.database import CompanyParty, Currency, Entity, Party, database


def test_documento_visible_usa_el_ulid_completo():
    """Dos ULID con el mismo prefijo temporal generan números distintos."""
    primero = _balance_confirmation_document_no("01M6D476VBKD3RKJRQKE7FWC0H")
    segundo = _balance_confirmation_document_no("01M6D476VBKD3RKJRQKE7FWC0J")

    assert primero == "CONF-01M6D476VBKD3RKJRQKE7FWC0H"
    assert segundo == "CONF-01M6D476VBKD3RKJRQKE7FWC0J"
    assert primero != segundo


@pytest.fixture
def confirmation_scene():
    """Compañía con un cliente activo para emitir confirmaciones."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="TAX-1703",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        party = Party(code="CLI-1703", name="Cliente", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
        database.session.commit()
        party_id = party.id
    yield application, party_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_confirmaciones_consecutivas_no_repiten_numero(confirmation_scene):
    """Cada confirmación emite un número derivado de su propio ID completo."""
    application, party_id = confirmation_scene
    with application.app_context():
        primera = create_balance_confirmation("cacao", party_id, "customer", date(2026, 5, 15), ["cliente@example.com"], None)
        segunda = create_balance_confirmation("cacao", party_id, "customer", date(2026, 5, 15), ["cliente@example.com"], None)
        database.session.commit()

        assert primera.document_no == f"CONF-{primera.id.upper()}"
        assert segunda.document_no == f"CONF-{segunda.id.upper()}"
        assert primera.document_no != segunda.document_no
