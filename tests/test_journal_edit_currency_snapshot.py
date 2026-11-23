# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1818: editar un diario conserva la tasa de cabecera y normaliza base_currency."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import create_journal_draft, update_journal_draft
from cacao_accounting.database import Accounts, Book, Entity, User, UserCompanyAccess, database


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


def test_cambiar_compania_con_otro_base_no_conserva_la_tasa_anterior(app, entorno_contable, reference_users):
    """Cambiar de compañía cambia la base monetaria y descarta la tasa anterior."""
    del reference_users
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        suffix = uuid4().hex[:6]
        company = database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one()
        company.currency = "USD"
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
        access = database.session.execute(
            database.select(UserCompanyAccess).filter_by(user_id=actor_id, company_code="alpha")
        ).scalar_one_or_none()
        if access is None:
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
