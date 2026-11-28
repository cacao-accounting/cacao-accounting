# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1818: editar un diario conserva la tasa de cabecera y normaliza base_currency."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect, select

from cacao_accounting.contabilidad.journal_service import create_journal_draft, update_journal_draft
from cacao_accounting.database import Accounts, Book, ComprobanteContable, Currency, Entity, User, UserCompanyAccess, database


def _payload(**overrides: object) -> dict[str, object]:
    """Construye un comprobante multimoneda balanceado para edición."""
    payload: dict[str, object] = {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "reference": f"FX-EDIT-{uuid4().hex[:8]}",
        "transaction_currency": "USD",
        "base_currency": "NIO",
        "exchange_rate": "36.5",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }
    payload.update(overrides)
    return payload


def _actor_id() -> str:
    return str(database.session.execute(select(User.id).where(User.user == "admin")).scalar_one())


def test_editar_sin_tasa_conserva_la_tasa_y_normaliza_base_currency(app, entorno_contable):
    """El formulario no envía base_currency ni tasa; la edición no debe vaciarlos."""
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)

        edit_payload = _payload()
        edit_payload.pop("base_currency")
        edit_payload.pop("exchange_rate")
        actualizado = update_journal_draft(journal.id, edit_payload, user_id=actor_id)

        assert actualizado.base_currency == "NIO"
        assert actualizado.exchange_rate == Decimal("36.5")


def test_editar_con_tasa_explicita_la_persiste(app, entorno_contable):
    """Una tasa enviada por el usuario reemplaza la del borrador."""
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)

        actualizado = update_journal_draft(journal.id, _payload(exchange_rate="37.25"), user_id=actor_id)

        assert actualizado.exchange_rate == Decimal("37.25")


def test_cambiar_de_moneda_con_tasa_enviada_no_conserva_la_tasa_anterior(app, entorno_contable):
    """El formulario puede enviar la tasa previa al cambiar de moneda."""
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)

        edit_payload = _payload(transaction_currency="NIO")
        edit_payload.pop("base_currency")
        actualizado = update_journal_draft(journal.id, edit_payload, user_id=actor_id)

        assert actualizado.transaction_currency == "NIO"
        assert actualizado.exchange_rate is None


def test_cambiar_de_moneda_con_tasa_nueva_explicita_la_persiste(entorno_contable_aislado):
    """Una tasa distinta enviada junto al nuevo par monetario es una tasa nueva."""
    app = entorno_contable_aislado.app
    with app.app_context():
        database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
        database.session.commit()
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)

        actualizado = update_journal_draft(
            journal.id,
            _payload(transaction_currency="EUR", exchange_rate="40"),
            user_id=actor_id,
        )

        assert actualizado.transaction_currency == "EUR"
        assert actualizado.base_currency == "NIO"
        assert actualizado.exchange_rate == Decimal("40")


def test_cambiar_compania_con_otro_base_no_conserva_la_tasa_anterior(entorno_contable_aislado):
    """Cambiar de compañía cambia la base monetaria y descarta la tasa anterior."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.app_context():
        suffix = uuid4().hex[:6]
        database.session.add(
            Entity(
                code="alpha",
                name="Alpha",
                company_name="Alpha Company",
                tax_id="J0002",
                currency="USD",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add(
            Book(
                entity="alpha",
                code=f"A{suffix}",
                name="Libro Alpha para edición",
                status="activo",
                is_primary=True,
                currency="USD",
            )
        )
        database.session.add(UserCompanyAccess(user_id=actor_id, company_code="alpha"))
        debit_code = f"D{suffix}"
        credit_code = f"C{suffix}"
        database.session.add_all(
            [
                Accounts(
                    entity="alpha", code=debit_code, name="Caja Alpha", active=True, enabled=True, classification="asset"
                ),
                Accounts(
                    entity="alpha", code=credit_code, name="Ingreso Alpha", active=True, enabled=True, classification="income"
                ),
            ]
        )
        database.session.commit()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)

        edit_payload = _payload(company="alpha")
        edit_payload.pop("base_currency")
        edit_payload["lines"] = [
            {"order": 1, "account": debit_code, "debit": "100", "credit": ""},
            {"order": 2, "account": credit_code, "debit": "", "credit": "100"},
        ]
        actualizado = update_journal_draft(journal.id, edit_payload, user_id=actor_id)

        assert actualizado.entity == "alpha"
        assert actualizado.base_currency == "USD"
        assert actualizado.transaction_currency == "USD"
        assert actualizado.exchange_rate is None


def test_edicion_http_sin_tasa_conserva_tasa_y_base(entorno_contable_aislado):
    """El POST real al formulario conserva la tasa y la moneda base del borrador."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.app_context():
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        identifier = journal.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = actor_id
        session["_fresh"] = True

    edit_payload = _payload()
    edit_payload.pop("base_currency")
    edit_payload.pop("exchange_rate")
    response = client.post(f"/accounting/journal/edit/{identifier}", data={"journal_payload": json.dumps(edit_payload)})

    assert response.status_code == 302
    with app.app_context():
        persisted = database.session.get(ComprobanteContable, identifier)
        assert persisted.base_currency == "NIO"
        assert persisted.exchange_rate == Decimal("36.5")

    page = client.get(f"/accounting/journal/edit/{identifier}")

    assert page.status_code == 200
    tasas = re.findall(r'"exchange_rate":\s*"([0-9.]+)"', page.get_data(as_text=True))
    assert tasas and Decimal(tasas[0]) == Decimal("36.5")


def test_edicion_http_con_par_y_tasa_nuevos_persiste_la_tasa(entorno_contable_aislado):
    """El formulario HTTP conserva una tasa nueva explícita al cambiar de moneda."""
    app = entorno_contable_aislado.app
    actor_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    with app.app_context():
        database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
        database.session.commit()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        identifier = journal.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = actor_id
        session["_fresh"] = True

    edit_payload = _payload(transaction_currency="EUR", exchange_rate="40")
    response = client.post(f"/accounting/journal/edit/{identifier}", data={"journal_payload": json.dumps(edit_payload)})

    assert response.status_code == 302
    with app.app_context():
        persisted = database.session.get(ComprobanteContable, identifier)
        assert persisted.transaction_currency == "EUR"
        assert persisted.base_currency == "NIO"
        assert persisted.exchange_rate == Decimal("40")
