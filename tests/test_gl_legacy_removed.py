# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Superficie GL legacy retirada en favor del flujo de comprobantes.

Escenario de negocio: las pantallas ``/accounting/gl/list`` y
``/accounting/gl/new`` no tenían POST, contexto ni persistencia. El flujo
operativo es el módulo de comprobantes (``/accounting/journal/...``); las rutas
legacy no deben seguir simulando una pantalla funcional.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Book, Currency, Entity, Modules, User, database

CONTRASENA = "gl-legacy-2026"


@pytest.fixture
def contabilidad_admin():
    """Cloud contable con administrador."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.parametrize("ruta", ["/accounting/gl/list", "/accounting/gl/new"])
def test_rutas_gl_legacy_estan_retiradas(contabilidad_admin, ruta):
    """Las pantallas legacy ya no responden."""
    client = contabilidad_admin.test_client()
    _iniciar(client)

    assert client.get(ruta).status_code == 404


@pytest.mark.parametrize("ruta", ["/accounting/journal/list", "/accounting/journal/new"])
def test_flujo_canonico_de_comprobantes_sigue_disponible(contabilidad_admin, ruta):
    """El flujo operativo de comprobantes conserva sus pantallas."""
    client = contabilidad_admin.test_client()
    _iniciar(client)

    response = client.get(ruta)

    assert response.status_code == 200


def test_flujo_canonico_crea_y_contabiliza_comprobante_por_http(app, entorno_contable, authenticated_client):
    """La ruta canónica permite crear un borrador y publicarlo en GL."""
    from cacao_accounting.database import ComprobanteContable, GLEntry

    client = authenticated_client("admin")
    reference = f"GL-HTTP-{uuid4().hex[:8]}"
    payload = {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": ["DEFAULT_BOOK"],
        "reference": reference,
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }

    response = client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})

    assert response.status_code == 302
    with app.app_context():
        journal = database.session.execute(
            select(ComprobanteContable).where(ComprobanteContable.reference == reference)
        ).scalar_one()
        assert journal.status == "draft"

    post_response = client.post(f"/accounting/journal/{journal.id}/submit")

    assert post_response.status_code == 302
    with app.app_context():
        journal = database.session.get(ComprobanteContable, journal.id)
        primary_book_id = database.session.execute(select(Book.id).where(Book.code == "DEFAULT_BOOK")).scalar_one()
        entries = database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal.id)).scalars().all()
        assert journal.status == "submitted"
        assert len(entries) == 2
        assert {entry.ledger_id for entry in entries} == {primary_book_id}
