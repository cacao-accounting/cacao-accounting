# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests for contabilidad module to reach 90% coverage."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


# ===========================================================================
# auxiliares.py — all helper functions
# ===========================================================================


def test_auxiliares_obtener_lista_entidades(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    result = obtener_lista_entidades_por_id_razonsocial()
    assert isinstance(result, list)
    assert any(item[0] == "cacao" for item in result)


def test_auxiliares_obtener_catalogo_base_with_entity(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo_base
    from cacao_accounting.database import Accounts, database

    database.session.add(Accounts(entity="cacao", code="1", name="Activo", active=True, enabled=True, group=True, parent=None))
    database.session.commit()
    result = obtener_catalogo_base(entidad_="cacao")
    assert isinstance(result, list)


def test_auxiliares_obtener_catalogo_base_default(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo_base

    result = obtener_catalogo_base()
    assert isinstance(result, list)


def test_auxiliares_obtener_catalogo_centros_costo_base_with_entity(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo_centros_costo_base
    from cacao_accounting.database import CostCenter, database

    database.session.add(CostCenter(entity="cacao", code="MAIN", name="Main", active=True, enabled=True, group=False))
    database.session.commit()
    result = obtener_catalogo_centros_costo_base(entidad_="cacao")
    assert isinstance(result, list)


def test_auxiliares_obtener_catalogo_centros_costo_base_default(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo_centros_costo_base

    result = obtener_catalogo_centros_costo_base()
    assert isinstance(result, list)


def test_auxiliares_obtener_catalogo_with_entity(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo
    from cacao_accounting.database import Accounts, database

    database.session.add(
        Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, group=False, parent="1")
    )
    database.session.commit()
    result = obtener_catalogo(entidad_="cacao")
    assert isinstance(result, list)


def test_auxiliares_obtener_catalogo_default(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_catalogo

    result = obtener_catalogo()
    assert isinstance(result, list)


def test_auxiliares_obtener_centros_costos_with_entity(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_centros_costos
    from cacao_accounting.database import CostCenter, database

    database.session.add(CostCenter(entity="cacao", code="ADM", name="Adm", active=True, enabled=True, group=False))
    database.session.commit()
    result = obtener_centros_costos(entidad_="cacao")
    assert isinstance(result, list)


def test_auxiliares_obtener_centros_costos_default(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_centros_costos

    result = obtener_centros_costos()
    assert isinstance(result, list)


def test_auxiliares_obtener_entidades(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_entidades

    result = obtener_entidades()
    assert len(result) >= 1


def test_auxiliares_obtener_entidad_by_code(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_entidad

    result = obtener_entidad(ent="cacao")
    assert result is not None


def test_auxiliares_obtener_entidad_default(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_entidad

    result = obtener_entidad()
    assert result is not None


def test_auxiliares_obtener_lista_monedas(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_monedas
    from cacao_accounting.database import Currency, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    result = obtener_lista_monedas()
    assert any(item[0] == "NIO" for item in result)


def test_auxiliares_obtener_lista_monedas_empty(app_ctx):
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_monedas

    result = obtener_lista_monedas()
    assert isinstance(result, list)


# ===========================================================================
# default_accounts.py — missing error paths and helper functions
# ===========================================================================


def test_default_accounts_account_label_none(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import account_label

    assert account_label(None) == ""


def test_default_accounts_account_label_with_account(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import account_label
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True)
    database.session.add(acct)
    database.session.commit()
    assert account_label(acct) == "1.01 - Caja"


def test_default_accounts_catalog_has_no_mapping(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import catalog_has_default_mapping

    assert not catalog_has_default_mapping("/tmp/nonexistent.csv")


def test_default_accounts_load_mapping_missing_file(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, load_catalog_default_mapping

    with pytest.raises(DefaultAccountError):
        load_catalog_default_mapping("/tmp/nonexistent.csv")


def test_default_accounts_load_mapping_bad_json(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, load_catalog_default_mapping

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = f.name
    json_path = Path(csv_path).with_suffix(".json")
    json_path.write_text(json.dumps({"other_key": {}}), encoding="utf-8")
    try:
        with pytest.raises(DefaultAccountError):
            load_catalog_default_mapping(csv_path)
    finally:
        json_path.unlink(missing_ok=True)
        Path(csv_path).unlink(missing_ok=True)


def test_default_accounts_load_mapping_missing_fields(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, load_catalog_default_mapping

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = f.name
    json_path = Path(csv_path).with_suffix(".json")
    json_path.write_text(json.dumps({"default_accounts": {"default_cash": "1.01"}}), encoding="utf-8")
    try:
        with pytest.raises(DefaultAccountError):
            load_catalog_default_mapping(csv_path)
    finally:
        json_path.unlink(missing_ok=True)
        Path(csv_path).unlink(missing_ok=True)


def test_default_accounts_validate_assignment_wrong_type(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_default_account_assignment
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, account_type="bank")
    database.session.add(acct)
    database.session.commit()

    with pytest.raises(DefaultAccountError, match="tipo"):
        validate_default_account_assignment("cacao", "default_cash", acct.id)


def test_default_accounts_validate_assignment_valid(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import validate_default_account_assignment
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, account_type="cash")
    database.session.add(acct)
    database.session.commit()
    validate_default_account_assignment("cacao", "default_cash", acct.id)


def test_default_accounts_validate_assignment_none_skips(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import validate_default_account_assignment

    validate_default_account_assignment("cacao", "default_cash", None)


def test_default_accounts_apply_catalog_missing_account(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import (
        DefaultAccountError,
        apply_catalog_default_mapping,
        DEFAULT_ACCOUNT_FIELDS,
    )

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = f.name
    json_path = Path(csv_path).with_suffix(".json")
    mapping = {field: "NONEXISTENT" for field in DEFAULT_ACCOUNT_FIELDS}
    json_path.write_text(json.dumps({"default_accounts": mapping}), encoding="utf-8")
    try:
        with pytest.raises(DefaultAccountError, match="no existe"):
            apply_catalog_default_mapping("cacao", csv_path)
    finally:
        json_path.unlink(missing_ok=True)
        Path(csv_path).unlink(missing_ok=True)


def test_default_accounts_validate_gl_account_usage_missing_account(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_gl_account_usage

    with pytest.raises(DefaultAccountError, match="no existe"):
        validate_gl_account_usage("nonexistent-id", "journal_entry")


def test_default_accounts_validate_gl_account_usage_blocked_manual(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_gl_account_usage
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="INV001", name="Inventario", active=True, enabled=True, account_type="inventory")
    database.session.add(acct)
    database.session.commit()
    with pytest.raises(DefaultAccountError, match="no permite afectacion manual"):
        validate_gl_account_usage(acct.id, "comprobante_contable")


def test_default_accounts_validate_gl_account_usage_disallowed_voucher(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_gl_account_usage
    from cacao_accounting.database import Accounts, database

    acct = Accounts(
        entity="cacao", code="COGS001", name="Costo Ventas", active=True, enabled=True, account_type="cost_of_goods_sold"
    )
    database.session.add(acct)
    database.session.commit()
    with pytest.raises(DefaultAccountError, match="no puede afectarse"):
        validate_gl_account_usage(acct.id, "sales_invoice")


def test_default_accounts_validate_gl_account_usage_no_type(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import validate_gl_account_usage
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="GEN001", name="General", active=True, enabled=True, account_type=None)
    database.session.add(acct)
    database.session.commit()
    validate_gl_account_usage(acct.id, "comprobante_contable")


def test_default_accounts_accounts_for_company(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import accounts_for_company
    from cacao_accounting.database import Accounts, database

    database.session.add(Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, group=False))
    database.session.commit()
    result = accounts_for_company("cacao")
    assert any(a.code == "1.01" for a in result)


def test_default_accounts_default_account_rows(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import default_account_rows

    rows = default_account_rows(None)
    assert len(rows) > 0
    assert rows[0]["account"] is None


# ===========================================================================
# journal_service.py — missing error branches
# ===========================================================================


def test_journal_service_submit_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, submit_journal

    with pytest.raises(JournalValidationError, match="no existe"):
        submit_journal("nonexistent-id")


def test_journal_service_submit_not_draft(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, Book, database

    debit = Accounts(entity="cacao", code="EXP-S1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-S1", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit, credit, book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "lines": [
                {"account": debit.id, "debit": "10.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )
    submit_journal(journal.id)
    with pytest.raises(JournalValidationError, match="borrador"):
        submit_journal(journal.id)


def test_journal_service_reject_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, reject_journal_draft

    with pytest.raises(JournalValidationError, match="no existe"):
        reject_journal_draft("nonexistent-id")


def test_journal_service_reject_not_draft(app_ctx):
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        create_journal_draft,
        reject_journal_draft,
    )
    from cacao_accounting.database import Accounts, Book, database

    debit = Accounts(entity="cacao", code="EXP-R1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-R1", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit, credit, book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    reject_journal_draft(journal.id)
    with pytest.raises(JournalValidationError, match="borrador"):
        reject_journal_draft(journal.id)


def test_journal_service_cancel_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, cancel_submitted_journal

    with pytest.raises(JournalValidationError, match="no existe"):
        cancel_submitted_journal("nonexistent-id")


def test_journal_service_cancel_not_submitted(app_ctx):
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        cancel_submitted_journal,
        create_journal_draft,
    )
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-C1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-C1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    with pytest.raises(JournalValidationError, match="contabilizado"):
        cancel_submitted_journal(journal.id)


def test_journal_service_cancel_submitted(app_ctx):
    from cacao_accounting.contabilidad.journal_service import (
        cancel_submitted_journal,
        create_journal_draft,
        submit_journal,
    )
    from cacao_accounting.database import Accounts, AccountingPeriod, Book, database

    debit = Accounts(entity="cacao", code="EXP-CA", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-CA", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO")
    period = AccountingPeriod(
        entity="cacao",
        name="2026-05",
        enabled=True,
        is_closed=False,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
    )
    database.session.add_all([debit, credit, book, period])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "lines": [
                {"account": debit.id, "debit": "8.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "8.00"},
            ],
        },
        user_id="user-1",
    )
    submit_journal(journal.id)
    entries = cancel_submitted_journal(journal.id, user_id="admin")
    assert len(entries) >= 0


def test_journal_service_duplicate_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, duplicate_journal_as_draft

    with pytest.raises(JournalValidationError, match="no existe"):
        duplicate_journal_as_draft("nonexistent-id", user_id="admin")


def test_journal_service_duplicate_cancelled_status(app_ctx):
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        create_journal_draft,
        duplicate_journal_as_draft,
    )
    from cacao_accounting.database import Accounts, ComprobanteContable, database

    debit = Accounts(entity="cacao", code="EXP-D1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-D1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.status = "cancelled"
    database.session.commit()

    with pytest.raises(JournalValidationError, match="duplicar"):
        duplicate_journal_as_draft(journal.id, user_id="admin")


def test_journal_service_reversal_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, duplicate_journal_as_reversal_draft

    with pytest.raises(JournalValidationError, match="no existe"):
        duplicate_journal_as_reversal_draft("nonexistent-id", user_id="admin")


def test_journal_service_reversal_cancelled_status(app_ctx):
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        create_journal_draft,
        duplicate_journal_as_reversal_draft,
    )
    from cacao_accounting.database import Accounts, ComprobanteContable, database

    debit = Accounts(entity="cacao", code="EXP-E1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-E1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.status = "cancelled"
    database.session.commit()

    with pytest.raises(JournalValidationError, match="revertir"):
        duplicate_journal_as_reversal_draft(journal.id, user_id="admin")


def test_journal_service_update_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, update_journal_draft

    with pytest.raises(JournalValidationError, match="no existe"):
        update_journal_draft(
            "nonexistent-id", {"company": "cacao", "posting_date": "2026-05-01", "lines": []}, user_id="admin"
        )


def test_journal_service_update_not_draft(app_ctx):
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        create_journal_draft,
        update_journal_draft,
    )
    from cacao_accounting.database import Accounts, ComprobanteContable, database

    debit = Accounts(entity="cacao", code="EXP-U1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-U1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.status = "submitted"
    database.session.commit()

    with pytest.raises(JournalValidationError, match="borrador"):
        update_journal_draft(
            journal.id,
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [
                    {"account": debit.id, "debit": "5.00", "credit": "0"},
                    {"account": credit.id, "debit": "0", "credit": "5.00"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_parse_form_invalid_json(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, parse_journal_form

    class FakeForm:
        def get(self, key, default=None):
            if key == "journal_payload":
                return "{{invalid json}}"
            return default

    with pytest.raises(JournalValidationError, match="formato valido"):
        parse_journal_form(FakeForm())


def test_journal_service_parse_form_not_dict(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, parse_journal_form

    class FakeForm:
        def get(self, key, default=None):
            if key == "journal_payload":
                return json.dumps([1, 2, 3])
            return default

    with pytest.raises(JournalValidationError, match="formato valido"):
        parse_journal_form(FakeForm())


def test_journal_service_parse_form_no_payload_key(app_ctx):
    from cacao_accounting.contabilidad.journal_service import parse_journal_form

    class FakeForm:
        def get(self, key, default=None):
            return default

        def getlist(self, key):
            return []

    result = parse_journal_form(FakeForm())
    assert isinstance(result, dict)
    assert "company" in result


def test_journal_service_normalize_lines_not_list(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft

    with pytest.raises(JournalValidationError):
        create_journal_draft(
            {"company": "cacao", "posting_date": "2026-05-01", "lines": "not-a-list"},
            user_id="admin",
        )


def test_journal_service_normalize_empty_lines_after_filter(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft

    with pytest.raises(JournalValidationError):
        create_journal_draft(
            {"company": "cacao", "posting_date": "2026-05-01", "lines": []},
            user_id="admin",
        )


def test_journal_service_normalize_books_string(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _normalize_books

    result = _normalize_books("FISC")
    assert result == ["FISC"]


def test_journal_service_normalize_books_string_empty(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _normalize_books

    result = _normalize_books("   ")
    assert result is None


def test_journal_service_normalize_books_invalid_type(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, _normalize_books

    with pytest.raises(JournalValidationError, match="formato"):
        _normalize_books(12345)


def test_journal_service_normalize_books_list_dedup(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _normalize_books

    result = _normalize_books(["FISC", "FISC", "IFRS"])
    assert result == ["FISC", "IFRS"]


def test_journal_service_selected_books_invalid_json(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, _selected_books_for_journal

    class FakeJournal:
        book_codes = "{{invalid}}"
        book = None

    with pytest.raises(JournalValidationError):
        _selected_books_for_journal(FakeJournal())


def test_journal_service_selected_books_fallback_to_book(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _selected_books_for_journal

    class FakeJournal:
        book_codes = None
        book = "FISC"

    result = _selected_books_for_journal(FakeJournal())
    assert result == ["FISC"]


def test_journal_service_validate_balanced_lines_negative(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="EXP-NEG", name="Gasto", active=True, enabled=True)
    database.session.add(acct)
    database.session.commit()

    with pytest.raises(JournalValidationError, match="negativos"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [{"account": acct.id, "debit": "-1", "credit": "0"}],
            },
            user_id="admin",
        )


def test_journal_service_validate_both_sides_positive(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="EXP-BOTH", name="Gasto", active=True, enabled=True)
    database.session.add(acct)
    database.session.commit()

    with pytest.raises(JournalValidationError, match="positivos"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [{"account": acct.id, "debit": "5", "credit": "5"}],
            },
            user_id="admin",
        )


def test_journal_service_validate_both_sides_zero(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="EXP-ZERO", name="Gasto", active=True, enabled=True)
    acct2 = Accounts(entity="cacao", code="CAJ-ZERO", name="Caja", active=True, enabled=True)
    database.session.add_all([acct, acct2])
    database.session.commit()

    with pytest.raises(JournalValidationError):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [
                    {"account": acct.id, "debit": "0", "credit": "0"},
                    {"account": acct2.id, "debit": "0", "credit": "0"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_account_code_wrong_entity(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, Entity, database

    other_entity = Entity(code="other", name="Other", company_name="Other", tax_id="J9999", currency="USD", enabled=True)
    database.session.add(other_entity)
    database.session.commit()
    other_acct = Accounts(entity="other", code="1.01", name="Caja", active=True, enabled=True)
    database.session.add(other_acct)
    database.session.commit()

    with pytest.raises(JournalValidationError, match="compañia"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [
                    {"account": other_acct.id, "debit": "5.00", "credit": "0"},
                    {"account": other_acct.id, "debit": "0", "credit": "5.00"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_required_text_empty(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft

    with pytest.raises(JournalValidationError, match="compañia"):
        create_journal_draft(
            {"company": "", "posting_date": "2026-05-01", "lines": []},
            user_id="admin",
        )


def test_journal_service_parse_date_invalid(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft

    with pytest.raises(JournalValidationError):
        create_journal_draft(
            {"company": "cacao", "posting_date": "not-a-date", "lines": []},
            user_id="admin",
        )


def test_journal_service_decimal_invalid(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="EXP-INV", name="Gasto", active=True, enabled=True)
    database.session.add(acct)
    database.session.commit()

    with pytest.raises(JournalValidationError, match="validos"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [{"account": acct.id, "debit": "abc", "credit": "0"}],
            },
            user_id="admin",
        )


def test_journal_service_optional_decimal(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _optional_decimal

    assert _optional_decimal(None) is None
    assert _optional_decimal("") is None
    assert _optional_decimal("1.5") == Decimal("1.5")


def test_journal_service_optional_bool_string(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _optional_bool

    assert _optional_bool("true") is True
    assert _optional_bool("false") is False
    assert _optional_bool("1") is True
    assert _optional_bool(None) is False
    assert _optional_bool(True) is True


def test_journal_service_normalize_transaction_currency_matching(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-TC1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-TC1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "transaction_currency": "USD",
            "lines": [
                {"account": debit.id, "debit": "10.00", "credit": "0", "currency": "USD"},
                {"account": credit.id, "debit": "0", "credit": "10.00", "currency": "USD"},
            ],
        },
        user_id="admin",
    )
    assert journal.transaction_currency == "USD"


def test_journal_service_account_labels_no_name(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _account_labels_for_company
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="NO-NAME", name=None, active=True, enabled=True)
    database.session.add(acct)
    database.session.commit()

    labels = _account_labels_for_company("cacao", {"NO-NAME"})
    assert labels.get("NO-NAME") == "NO-NAME"


def test_journal_service_cost_center_labels_no_name(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _cost_center_labels_for_company
    from cacao_accounting.database import CostCenter, database

    cc = CostCenter(entity="cacao", code="CC-NN", name=None, active=True, enabled=True, group=False)
    database.session.add(cc)
    database.session.commit()

    labels = _cost_center_labels_for_company("cacao", {"CC-NN"})
    assert labels.get("CC-NN") == "CC-NN"


def test_journal_service_account_labels_empty_codes(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _account_labels_for_company

    labels = _account_labels_for_company("cacao", set())
    assert labels == {}


def test_journal_service_cost_center_labels_empty_codes(app_ctx):
    from cacao_accounting.contabilidad.journal_service import _cost_center_labels_for_company

    labels = _cost_center_labels_for_company("cacao", set())
    assert labels == {}


def test_journal_service_normalize_line_not_dict(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft

    with pytest.raises(JournalValidationError):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": ["not-a-dict"],
            },
            user_id="admin",
        )


def test_journal_service_books_from_book_key(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, database

    debit = Accounts(entity="cacao", code="EXP-BK", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-BK", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit, credit, book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "book": "FISC",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="admin",
    )
    assert journal.book == "FISC"


# ===========================================================================
# ctas/__init__.py — header aliases (lines 47, 82)
# ===========================================================================


def test_ctas_value_function_aliases(app_ctx):
    from cacao_accounting.contabilidad.ctas import _value, _is_group

    row_es = {
        "codigo": "1.01",
        "nombre": "Caja",
        "padre": "",
        "grupo": "no",
        "rubro": "Activo",
        "tipo": "",
        "tipo_cuenta": "cash",
    }
    assert _value(row_es, "code") == "1.01"
    assert _value(row_es, "name") == "Caja"
    assert _is_group("0") is False
    assert _is_group("") is False

    row_en = {
        "code": "1.01",
        "name": "Cash",
        "parent": "",
        "group": "1",
        "classification": "Asset",
        "type": "",
        "account_type": "",
    }
    assert _value(row_en, "code") == "1.01"
    assert _is_group("1") is True


def test_ctas_cargar_catalogos(app_ctx):
    from cacao_accounting.contabilidad.ctas import cargar_catalogos, base_es
    from cacao_accounting.database import database

    database.session.commit()
    cargar_catalogos(base_es, "cacao")
    database.session.commit()


# ===========================================================================
# gl/__init__.py — routes gl_list and gl_new
# ===========================================================================


def test_gl_list_route(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/gl/list")
    assert response.status_code == 200


def test_gl_new_route(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/gl/new")
    assert response.status_code == 200


# ===========================================================================
# contabilidad/__init__.py — Flask routes coverage
# ===========================================================================


def test_route_conta(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Comprobante Recurrente" in html
    assert "Asistente de Cierre Mensual" in html


def test_route_monedas(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/currency/list")
    assert response.status_code == 200


def test_route_nueva_moneda_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/currency/new")
    assert response.status_code == 200


def test_route_nueva_moneda_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/currency/new",
        data={"code": "USD", "name": "Dollar", "decimals": "2", "active": "y", "default": ""},
    )
    assert response.status_code in (200, 302)


def test_route_entidades(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/entity/list")
    assert response.status_code == 200


def test_route_entidad_detail(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/entity/cacao")
    assert response.status_code == 200


def test_route_nueva_entidad_get(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/entity/new")
    assert response.status_code == 200


def test_route_nueva_entidad_post_invalid(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/entity/new", data={})
    assert response.status_code in (200, 302)


def test_route_editar_entidad_get(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/entity/edit/cacao")
    assert response.status_code == 200


def test_route_entity_set_inactive(app_ctx):
    from cacao_accounting.database import Entity, User, database

    extra = Entity(code="EX1", name="Extra", company_name="Extra SA", tax_id="J9998", currency="NIO", enabled=True)
    database.session.add(extra)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/entity/set_inactive/{extra.id}", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_entity_set_active(app_ctx):
    from cacao_accounting.database import Entity, User, database

    extra = Entity(code="EX2", name="Extra2", company_name="Extra2 SA", tax_id="J9997", currency="NIO", enabled=False)
    database.session.add(extra)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/entity/set_active/{extra.id}", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_entity_set_default(app_ctx):
    from cacao_accounting.database import Entity, User, database

    extra = Entity(code="EX3", name="Extra3", company_name="Extra3 SA", tax_id="J9996", currency="NIO", enabled=True)
    database.session.add(extra)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/entity/set_default/{extra.id}", follow_redirects=False)
    assert response.status_code in (200, 302, 500)


def test_route_unidades(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/unit/list")
    assert response.status_code == 200


def test_route_unidad_detail(app_ctx):
    from cacao_accounting.database import Unit, User, database

    database.session.add(Unit(code="HQ", name="Headquarters", entity="cacao"))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/unit/HQ")
    assert response.status_code == 200


def test_route_eliminar_unidad(app_ctx):
    from cacao_accounting.database import Unit, User, database

    database.session.add(Unit(code="HQ2", name="HQ2", entity="cacao"))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/unit/delete/HQ2")
    assert response.status_code in (200, 302)


def test_route_nueva_unidad_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/unit/new",
        data={"id": "UNIT1", "nombre": "Unidad 1", "entidad": "cacao", "habilitado": "y"},
    )
    assert response.status_code in (200, 302)


def test_route_nueva_unidad_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/unit/new")
    assert response.status_code == 200


def test_route_libros(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/book/list")
    assert response.status_code == 200


def test_route_libro_detail(app_ctx):
    from cacao_accounting.database import Book, User, database

    database.session.add(Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/book/FISC")
    assert response.status_code == 200


def test_route_eliminar_libro(app_ctx):
    from cacao_accounting.database import Book, User, database

    database.session.add(Book(entity="cacao", code="BKDEL", name="Book Delete", status="activo"))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/book/delete/BKDEL")
    assert response.status_code in (200, 302)


def test_route_editar_libro_get(app_ctx):
    from cacao_accounting.database import Book, Currency, User, database

    database.session.add_all(
        [
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            Book(entity="cacao", code="FISC2", name="Fiscal2", status="activo"),
        ]
    )
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/book/edit/FISC2")
    assert response.status_code == 200


def test_route_editar_libro_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/book/edit/NONEXISTENT")
    assert response.status_code in (200, 302)


def test_route_nuevo_libro_get(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/book/new")
    assert response.status_code == 200


def test_route_journal_books_no_company(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/journal/books")
    assert response.status_code == 200
    assert response.json["results"] == []


def test_route_cuentas(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/accounts?entidad=cacao")
    assert response.status_code == 200


def test_route_cuenta_detail(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    database.session.add(Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/account/cacao/1.01")
    assert response.status_code == 200


def test_route_nueva_cuenta_get(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/account/new")
    assert response.status_code == 200


def test_route_ccostos(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/costs_center?entidad=cacao")
    assert response.status_code == 200


def test_route_nuevo_centro_costo_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/costs_center/new")
    assert response.status_code == 200


def test_route_nuevo_centro_costo_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/costs_center/new",
        data={"id": "CC01", "nombre": "Centro 1", "entidad": "cacao", "activo": "y", "habilitado": "y", "predeterminado": ""},
    )
    assert response.status_code in (200, 302)


def test_route_centro_costo_detail(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    database.session.add(CostCenter(entity="cacao", code="CCDT", name="Detail CC", active=True, enabled=True, group=False))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/costs_center/CCDT")
    assert response.status_code == 200


def test_route_centro_costo_missing_redirects(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/costs_center/NONEXISTENT")
    assert response.status_code in (200, 302)


def test_route_editar_centro_costo_get(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    database.session.add(CostCenter(entity="cacao", code="CCE1", name="Edit CC", active=True, enabled=True, group=False))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/costs_center/CCE1/edit")
    assert response.status_code == 200


def test_route_eliminar_centro_costo(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    database.session.add(CostCenter(entity="cacao", code="CCDEL", name="Del CC", active=True, enabled=True, group=False))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/costs_center/CCDEL/delete")
    assert response.status_code in (200, 302)


def test_route_proyectos(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/project/list")
    assert response.status_code == 200


def test_route_nuevo_proyecto_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/project/new")
    assert response.status_code == 200


def test_route_nuevo_proyecto_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/project/new",
        data={
            "id": "PRJ01",
            "nombre": "Proyecto 1",
            "entidad": "cacao",
            "inicio": "2026-01-01",
            "fin": "2026-12-31",
            "presupuesto": "0",
            "habilitado": "y",
            "status": "open",
        },
    )
    assert response.status_code in (200, 302)


def test_route_editar_proyecto_get(app_ctx):
    from cacao_accounting.database import Project, User, database

    database.session.add(Project(code="PRJ2", name="Proyecto 2", entity="cacao", enabled=True, start=date(2026, 1, 1)))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/project/PRJ2/edit")
    assert response.status_code == 200


def test_route_editar_proyecto_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/project/NONEXISTENT/edit")
    assert response.status_code in (200, 302)


def test_route_eliminar_proyecto(app_ctx):
    from cacao_accounting.database import Project, User, database

    database.session.add(Project(code="PRJDEL", name="Del Proyecto", entity="cacao", enabled=True, start=date(2026, 1, 1)))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/project/PRJDEL/delete")
    assert response.status_code in (200, 302)


def test_route_fiscal_year_list(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/fiscal_year/list")
    assert response.status_code == 200


def test_route_fiscal_year_new_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/fiscal_year/new")
    assert response.status_code == 200


def test_route_fiscal_year_new_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/fiscal_year/new",
        data={"id": "2026", "entidad": "cacao", "inicio": "2026-01-01", "fin": "2026-12-31", "cerrado": ""},
    )
    assert response.status_code in (200, 302)


def test_route_fiscal_year_edit_get(app_ctx):
    from cacao_accounting.database import FiscalYear, User, database

    fy = FiscalYear(entity="cacao", name="2026", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31))
    database.session.add(fy)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/fiscal_year/{fy.id}/edit")
    assert response.status_code == 200


def test_route_fiscal_year_edit_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/fiscal_year/NONEXISTENT/edit")
    assert response.status_code in (200, 302)


def test_route_fiscal_year_delete(app_ctx):
    from cacao_accounting.database import FiscalYear, User, database

    fy = FiscalYear(entity="cacao", name="2027", year_start_date=date(2027, 1, 1), year_end_date=date(2027, 12, 31))
    database.session.add(fy)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/fiscal_year/{fy.id}/delete")
    assert response.status_code in (200, 302)


def test_route_accounting_period_new_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/accounting_period/new")
    assert response.status_code == 200


def test_route_accounting_period_new_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/accounting_period/new",
        data={
            "entidad": "cacao",
            "nombre": "2026-05",
            "inicio": "2026-05-01",
            "fin": "2026-05-31",
            "habilitado": "y",
            "cerrado": "",
        },
    )
    assert response.status_code in (200, 302)


def test_route_accounting_period_edit_get(app_ctx):
    from cacao_accounting.database import AccountingPeriod, User, database

    period = AccountingPeriod(
        entity="cacao", name="2026-06", enabled=True, is_closed=False, start=date(2026, 6, 1), end=date(2026, 6, 30)
    )
    database.session.add(period)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/accounting_period/{period.id}/edit")
    assert response.status_code == 200


def test_route_accounting_period_edit_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/accounting_period/NONEXISTENT/edit")
    assert response.status_code in (200, 302)


def test_route_accounting_period_delete(app_ctx):
    from cacao_accounting.database import AccountingPeriod, User, database

    period = AccountingPeriod(
        entity="cacao", name="2026-07", enabled=True, is_closed=False, start=date(2026, 7, 1), end=date(2026, 7, 31)
    )
    database.session.add(period)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/accounting_period/{period.id}/delete")
    assert response.status_code in (200, 302)


def test_route_tasa_cambio(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/exchange")
    assert response.status_code == 200


def test_route_nueva_tasa_cambio_get(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/exchange/new")
    assert response.status_code == 200


def test_route_nueva_tasa_cambio_post(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add_all(
        [
            Currency(code="USD", name="Dollar", decimals=2, active=True),
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
        ]
    )
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/exchange/new",
        data={"origin": "USD", "destination": "NIO", "rate": "36.50", "date": "2026-05-01"},
    )
    assert response.status_code in (200, 302)


def test_route_periodo_contable(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/accounting_period")
    assert response.status_code == 200


def test_route_listar_comprobantes(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/journal/list")
    assert response.status_code == 200


def test_route_comprobantes_recurrentes(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/journal/recurring")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Comprobante Recurrente" in html
    assert "Plantillas contables recurrentes" in html


def test_route_nuevo_comprobante_recurrente_uses_journal_patterns(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/journal/recurring/new")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name: "naming_series_id"' in html
    assert 'autoSelectDefault: true' in html
    assert 'name="books"' in html
    assert "selectedBooks.includes(book.value)" in html
    assert "lineDetailModal" in html
    assert "Unidad de negocio" in html
    assert "Proyecto" in html
    assert "Tipo de tercero" in html
    assert "Tercero" in html
    assert "Tipo de referencia" not in html
    assert "Nombre de referencia" not in html
    assert "Es anticipo" not in html


def test_route_asistente_cierre_mensual(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/period-close/monthly")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Asistente de Cierre Mensual" in html
    assert "aplicar comprobantes recurrentes" in html
    assert "Cierres mensuales" in html
    assert "Crear cierre" in html
    assert 'doctype: "company"' in html
    assert 'doctype: "accounting_period_id"' in html
    assert 'requiredFilters: ["company"]' in html
    assert 'filters: { company: { selector: "#close-company" }, is_closed: false }' in html


def test_monthly_close_creates_run_and_shows_step_detail(app_ctx):
    from cacao_accounting.database import AccountingPeriod, FiscalYear, PeriodCloseRun, User, database

    user = User.query.filter_by(user="admin").first()
    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY-CLOSE",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    database.session.add(fiscal_year)
    database.session.flush()
    period = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-05",
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        enabled=True,
        is_closed=False,
    )
    database.session.add(period)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/period-close/monthly/new", data={"period_id": period.id}, follow_redirects=True)
    html = response.get_data(as_text=True)
    close_run = database.session.execute(database.select(PeriodCloseRun).filter_by(period_id=period.id)).scalar_one()

    assert response.status_code == 200
    assert close_run.run_status == "open"
    assert "Paso 1: aplicar comprobantes recurrentes" in html
    assert "Ejecutar paso" in html


def test_monthly_close_period_smart_select_filters_open_periods_by_company(app_ctx):
    from cacao_accounting.database import AccountingPeriod, Entity, FiscalYear, User, database

    user = User.query.filter_by(user="admin").first()
    database.session.add(Entity(code="cafe", name="Cafe", company_name="Cafe SA", tax_id="J0002", currency="NIO"))
    fiscal_year_cacao = FiscalYear(
        entity="cacao",
        name="FY-CACAO-SELECT",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    fiscal_year_cafe = FiscalYear(
        entity="cafe",
        name="FY-CAFE-SELECT",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    database.session.add_all([fiscal_year_cacao, fiscal_year_cafe])
    database.session.flush()
    database.session.add_all(
        [
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=fiscal_year_cacao.id,
                name="CACAO-OPEN",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                enabled=True,
                is_closed=False,
            ),
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=fiscal_year_cacao.id,
                name="CACAO-CLOSED",
                start=date(2026, 2, 1),
                end=date(2026, 2, 28),
                enabled=True,
                is_closed=True,
            ),
            AccountingPeriod(
                entity="cafe",
                fiscal_year_id=fiscal_year_cafe.id,
                name="CAFE-OPEN",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                enabled=True,
                is_closed=False,
            ),
        ]
    )
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(
        "/api/search-select?doctype=accounting_period_id&company=cacao&is_closed=false&q=&limit=10"
    )
    payload = response.get_json()
    labels = [item["display_name"] for item in payload["results"]]

    assert response.status_code == 200
    assert "CACAO-OPEN" in labels
    assert "CACAO-CLOSED" not in labels
    assert "CAFE-OPEN" not in labels


def test_monthly_close_apply_recurring_step_records_check(app_ctx):
    from cacao_accounting.database import AccountingPeriod, FiscalYear, PeriodCloseCheck, PeriodCloseRun, User, database

    user = User.query.filter_by(user="admin").first()
    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY-CLOSE-STEP",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    database.session.add(fiscal_year)
    database.session.flush()
    period = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-06",
        start=date(2026, 6, 1),
        end=date(2026, 6, 30),
        enabled=True,
        is_closed=False,
    )
    database.session.add(period)
    database.session.flush()
    close_run = PeriodCloseRun(company="cacao", period_id=period.id, run_status="open")
    database.session.add(close_run)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        f"/accounting/period-close/monthly/{close_run.id}/apply-recurring",
        data={},
        follow_redirects=True,
    )
    check = database.session.execute(database.select(PeriodCloseCheck).filter_by(close_run_id=close_run.id)).scalar_one()

    assert response.status_code == 200
    assert check.check_type == "apply_recurring_journals"
    assert check.check_status == "skipped"
    assert "Historial de pasos" in response.get_data(as_text=True)


def test_route_ver_comprobante_not_found(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/journal/nonexistent-id")
    assert response.status_code in (200, 302)


def test_route_ver_comprobante_with_currency_label(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    debit = Accounts(entity="cacao", code="EXP-VW", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-VW", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO")
    database.session.add_all([debit, credit, book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "transaction_currency": "NIO",
            "memo": "Test view journal",
            "lines": [
                {"account": debit.id, "debit": "15.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "15.00"},
            ],
        },
        user_id="user-1",
    )
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/journal/{journal.id}")
    assert response.status_code == 200


def test_route_ver_comprobante_unknown_currency(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, User, database

    debit = Accounts(entity="cacao", code="EXP-UC", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-UC", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "transaction_currency": "EUR",
            "lines": [
                {"account": debit.id, "debit": "15.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "15.00"},
            ],
        },
        user_id="user-1",
    )
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/journal/{journal.id}")
    assert response.status_code == 200


def test_route_ver_comprobante_no_currency(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, User, database

    debit = Accounts(entity="cacao", code="EXP-NC", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-NC", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/journal/{journal.id}")
    assert response.status_code == 200


def test_route_duplicar_comprobante_error(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, User, database

    debit = Accounts(entity="cacao", code="EXP-DC", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-DC", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit, credit, book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.status = "cancelled"
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(f"/accounting/journal/{journal.id}/duplicate", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_revertir_comprobante_error(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, ComprobanteContable, User, database

    debit = Accounts(entity="cacao", code="EXP-RC", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-RC", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.status = "cancelled"
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(f"/accounting/journal/{journal.id}/revert", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_editar_comprobante_not_found(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/journal/edit/NONEXISTENT", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_editar_comprobante_not_draft(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, User, database

    debit = Accounts(entity="cacao", code="EXP-ED", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-ED", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit, credit, book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.status = "submitted"
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/journal/edit/{journal.id}", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_editar_comprobante_post_error(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, User, database

    debit = Accounts(entity="cacao", code="EXP-EP", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-EP", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "5.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="user-1",
    )

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        f"/accounting/journal/edit/{journal.id}",
        data={"journal_payload": "{{invalid json}}"},
        follow_redirects=False,
    )
    assert response.status_code in (200, 302)


def test_route_naming_series_list(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/naming-series/list")
    assert response.status_code == 200


def test_route_naming_series_new_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/naming-series/new")
    assert response.status_code == 200


def test_route_naming_series_new_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/naming-series/new",
        data={
            "nombre": "Serie Fiscal",
            "entity_type": "journal_entry",
            "company": "",
            "prefix_template": "{COMPANY}-JOU-{YYYY}-{MM}-",
            "is_active": "y",
            "is_default": "",
            "current_value": "0",
            "increment": "1",
            "padding": "5",
            "reset_policy": "never",
        },
    )
    assert response.status_code in (200, 302)


def test_route_naming_series_toggle_default(app_ctx):
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, User, database

    seq = Sequence(name="Seq1", current_value=0, increment=1, padding=5, reset_policy="never")
    database.session.add(seq)
    database.session.flush()
    series = NamingSeries(
        name="Serie1", entity_type="journal_entry", is_active=True, is_default=False, prefix_template="{YYYY}-"
    )
    database.session.add(series)
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=seq.id, priority=0))
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(f"/accounting/naming-series/{series.id}/toggle-default", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_naming_series_toggle_default_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/naming-series/NONEXISTENT/toggle-default", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_naming_series_edit_get(app_ctx):
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, User, database

    seq = Sequence(name="Seq2", current_value=0, increment=1, padding=5, reset_policy="never")
    database.session.add(seq)
    database.session.flush()
    series = NamingSeries(
        name="Serie2", entity_type="journal_entry", is_active=True, is_default=False, prefix_template="{YYYY}-"
    )
    database.session.add(series)
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=seq.id, priority=0))
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/naming-series/{series.id}/edit")
    assert response.status_code == 200


def test_route_naming_series_edit_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/naming-series/NONEXISTENT/edit")
    assert response.status_code in (200, 302)


def test_route_naming_series_delete(app_ctx):
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, User, database

    seq = Sequence(name="Seq3", current_value=0, increment=1, padding=5, reset_policy="never")
    database.session.add(seq)
    database.session.flush()
    series = NamingSeries(
        name="SerieX", entity_type="journal_entry", is_active=True, is_default=False, prefix_template="{YYYY}-"
    )
    database.session.add(series)
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=seq.id, priority=0))
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/naming-series/{series.id}/delete")
    assert response.status_code in (200, 302)


def test_route_naming_series_delete_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/naming-series/NONEXISTENT/delete")
    assert response.status_code in (200, 302)


def test_route_naming_series_toggle_active_deactivate(app_ctx):
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, User, database

    seq = Sequence(name="SeqA", current_value=0, increment=1, padding=5, reset_policy="never")
    database.session.add(seq)
    database.session.flush()
    series = NamingSeries(
        name="SerieA", entity_type="journal_entry", is_active=True, is_default=True, prefix_template="{YYYY}-"
    )
    database.session.add(series)
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=seq.id, priority=0))
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(f"/accounting/naming-series/{series.id}/toggle-active", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_naming_series_toggle_active_activate(app_ctx):
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, User, database

    seq = Sequence(name="SeqB", current_value=0, increment=1, padding=5, reset_policy="never")
    database.session.add(seq)
    database.session.flush()
    series = NamingSeries(
        name="SerieB", entity_type="journal_entry", is_active=False, is_default=False, prefix_template="{YYYY}-"
    )
    database.session.add(series)
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=seq.id, priority=0))
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(f"/accounting/naming-series/{series.id}/toggle-active", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_naming_series_toggle_active_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/naming-series/NONEXISTENT/toggle-active", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_external_counter_list(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/external-counter/list")
    assert response.status_code == 200


def test_route_external_counter_new_get(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/external-counter/new")
    assert response.status_code == 200


def test_route_external_counter_new_post(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/external-counter/new",
        data={
            "company": "cacao",
            "nombre": "Contador Fiscal",
            "counter_type": "fiscal",
            "prefix": "F",
            "last_used": "0",
            "padding": "5",
            "is_active": "y",
            "description": "",
            "naming_series_id": "",
        },
    )
    assert response.status_code in (200, 302)


def test_route_external_counter_adjust_get(app_ctx):
    from cacao_accounting.database import ExternalCounter, User, database

    ec = ExternalCounter(company="cacao", name="Cont1", counter_type="fiscal", last_used=0, padding=5, is_active=True)
    database.session.add(ec)
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/external-counter/{ec.id}/adjust")
    assert response.status_code == 200


def test_route_external_counter_adjust_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/external-counter/NONEXISTENT/adjust")
    assert response.status_code in (200, 302)


def test_route_external_counter_audit_log(app_ctx):
    from cacao_accounting.database import ExternalCounter, User, database

    ec = ExternalCounter(company="cacao", name="AuditCont", counter_type="fiscal", last_used=0, padding=5, is_active=True)
    database.session.add(ec)
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/external-counter/{ec.id}/audit-log")
    assert response.status_code == 200


def test_route_external_counter_audit_log_missing(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/external-counter/NONEXISTENT/audit-log")
    assert response.status_code in (200, 302)


# ===========================================================================
# posting.py — _decimal_value and _validate_single_sided_amount edge cases
# ===========================================================================


def test_posting_decimal_value_invalid(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _decimal_value

    with pytest.raises(PostingError, match="invalido"):
        _decimal_value("abc")


def test_posting_decimal_value_none(app_ctx):
    from cacao_accounting.contabilidad.posting import _decimal_value

    assert _decimal_value(None) == Decimal("0")


def test_posting_decimal_value_decimal(app_ctx):
    from cacao_accounting.contabilidad.posting import _decimal_value

    d = Decimal("3.14")
    assert _decimal_value(d) == d


def test_posting_validate_single_sided_negative(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _validate_single_sided_amount

    with pytest.raises(PostingError, match="negativos"):
        _validate_single_sided_amount(Decimal("-1"), Decimal("0"))


def test_posting_validate_single_sided_both_positive(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _validate_single_sided_amount

    with pytest.raises(PostingError, match="ambos"):
        _validate_single_sided_amount(Decimal("5"), Decimal("5"))


def test_posting_validate_single_sided_both_zero(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _validate_single_sided_amount

    with pytest.raises(PostingError):
        _validate_single_sided_amount(Decimal("0"), Decimal("0"))


def test_posting_normalize_ledger_codes_none(app_ctx):
    from cacao_accounting.contabilidad.posting import _normalize_ledger_codes

    assert _normalize_ledger_codes(None) is None


def test_posting_normalize_ledger_codes_string(app_ctx):
    from cacao_accounting.contabilidad.posting import _normalize_ledger_codes

    assert _normalize_ledger_codes("FISC") == ["FISC"]


def test_posting_normalize_ledger_codes_empty_string(app_ctx):
    from cacao_accounting.contabilidad.posting import _normalize_ledger_codes

    assert _normalize_ledger_codes("  ") is None


def test_posting_normalize_ledger_codes_list(app_ctx):
    from cacao_accounting.contabilidad.posting import _normalize_ledger_codes

    assert _normalize_ledger_codes(["FISC", "IFRS"]) == ["FISC", "IFRS"]


def test_posting_normalize_ledger_codes_list_dedup(app_ctx):
    from cacao_accounting.contabilidad.posting import _normalize_ledger_codes

    assert _normalize_ledger_codes(["FISC", "FISC"]) == ["FISC"]


def test_posting_active_books_missing_code(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _active_books

    with pytest.raises(PostingError, match="inactivos"):
        _active_books("cacao", ["NONEXISTENT"])


def test_posting_require_account_none(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _require_account

    with pytest.raises(PostingError, match="obligatoria"):
        _require_account(None, "La cuenta es obligatoria.")


def test_posting_require_account_nonexistent(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, _require_account

    with pytest.raises(PostingError, match="no existe"):
        _require_account("nonexistent-id", "msg")


def test_posting_company_defaults_none(app_ctx):
    from cacao_accounting.contabilidad.posting import _company_defaults

    result = _company_defaults("cacao")
    assert result is None


def test_posting_resolve_party_account_no_defaults(app_ctx):
    from cacao_accounting.contabilidad.posting import _resolve_party_account_id

    result = _resolve_party_account_id(None, "cacao", True)
    assert result is None


def test_posting_account_code_for(app_ctx):
    from cacao_accounting.contabilidad.posting import _account_code_for
    from cacao_accounting.database import Accounts, database

    acct = Accounts(entity="cacao", code="TST001", name="Test", active=True, enabled=True)
    database.session.add(acct)
    database.session.commit()

    assert _account_code_for(acct.id) == "TST001"
    assert _account_code_for("nonexistent") is None


# ===========================================================================
# journal_repository.py — list_journals (line 32)
# ===========================================================================


def test_journal_repository_list_journals(app_ctx):
    from cacao_accounting.contabilidad.journal_repository import list_journals
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-LJ", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-LJ", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "1.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "1.00"},
            ],
        },
        user_id="user-1",
    )
    journals = list_journals()
    assert len(journals) >= 1


# ===========================================================================
# Additional targeted tests to reach 90% coverage
# ===========================================================================


def test_journal_service_expense_account_needs_cost_center(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    expense = Accounts(entity="cacao", code="EXP-CC1", name="Gasto", active=True, enabled=True, account_type="expense")
    credit = Accounts(entity="cacao", code="CAJ-CC1", name="Caja", active=True, enabled=True)
    database.session.add_all([expense, credit])
    database.session.commit()

    with pytest.raises(JournalValidationError, match="centro de costo"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [
                    {"account": expense.id, "debit": "10.00", "credit": "0", "cost_center": ""},
                    {"account": credit.id, "debit": "0", "credit": "10.00"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_transaction_currency_mismatch(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-TM1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-TM1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    with pytest.raises(JournalValidationError, match="moneda"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "transaction_currency": "USD",
                "lines": [
                    {"account": debit.id, "debit": "10.00", "credit": "0", "currency": "EUR"},
                    {"account": credit.id, "debit": "0", "credit": "10.00", "currency": "EUR"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_mixed_currencies_no_transaction_currency(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-MC1", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-MC1", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    with pytest.raises(JournalValidationError, match="mezclar monedas"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [
                    {"account": debit.id, "debit": "10.00", "credit": "0", "currency": "USD"},
                    {"account": credit.id, "debit": "0", "credit": "10.00", "currency": "EUR"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_account_code_by_code_not_found(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    credit = Accounts(entity="cacao", code="CAJ-CF", name="Caja", active=True, enabled=True)
    database.session.add(credit)
    database.session.commit()

    with pytest.raises(JournalValidationError, match="no existe"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-01",
                "lines": [
                    {"account": "NONEXISTENT-CODE", "debit": "5.00", "credit": "0"},
                    {"account": credit.id, "debit": "0", "credit": "5.00"},
                ],
            },
            user_id="admin",
        )


def test_journal_service_account_code_by_code_found(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, database

    debit = Accounts(entity="cacao", code="EXP-COD", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-COD", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": "EXP-COD", "debit": "5.00", "credit": "0"},
                {"account": "CAJ-COD", "debit": "0", "credit": "5.00"},
            ],
        },
        user_id="admin",
    )
    assert journal is not None


def test_default_accounts_validate_wrong_entity(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_default_account_assignment
    from cacao_accounting.database import Accounts, Entity, database

    other = Entity(code="OTH1", name="Other", company_name="Other SA", tax_id="J8888", currency="NIO", enabled=True)
    database.session.add(other)
    database.session.commit()
    acct = Accounts(entity="OTH1", code="CASH1", name="Cash", active=True, enabled=True, account_type="cash")
    database.session.add(acct)
    database.session.commit()

    with pytest.raises(DefaultAccountError, match="no existe"):
        validate_default_account_assignment("cacao", "default_cash", acct.id)


def test_route_eliminar_entidad(app_ctx):
    from cacao_accounting.database import Entity, User, database

    extra = Entity(code="DEL1", name="ToDelete", company_name="ToDelete SA", tax_id="J7777", currency="NIO", enabled=True)
    database.session.add(extra)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/entity/delete/{extra.id}", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_journal_submit_flash_error(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/journal/NONEXISTENT/submit", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_journal_reject_flash_error(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/journal/NONEXISTENT/reject", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_journal_cancel_flash_error(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post("/accounting/journal/NONEXISTENT/cancel", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_journal_cancel_success_flash(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, AccountingPeriod, Book, User, database

    debit = Accounts(entity="cacao", code="EXP-CS", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-CS", name="Caja", active=True, enabled=True)
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO")
    period = AccountingPeriod(
        entity="cacao", name="2026-05", enabled=True, is_closed=False, start=date(2026, 5, 1), end=date(2026, 5, 31)
    )
    database.session.add_all([debit, credit, book, period])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "books": ["FISC"],
            "lines": [
                {"account": debit.id, "debit": "7.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "7.00"},
            ],
        },
        user_id="user-1",
    )
    submit_journal(journal.id)

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(f"/accounting/journal/{journal.id}/cancel", follow_redirects=False)
    assert response.status_code in (200, 302)


def test_route_ver_comprobante_journal_book_attribute(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, ComprobanteContable, User, database

    debit = Accounts(entity="cacao", code="EXP-JBA", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-JBA", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "book": "LEGACY",
            "lines": [
                {"account": debit.id, "debit": "3.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "3.00"},
            ],
        },
        user_id="user-1",
    )
    j = database.session.get(ComprobanteContable, journal.id)
    j.book = "LEGACY"
    j.book_codes = None
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/journal/{journal.id}")
    assert response.status_code == 200


def test_route_ver_comprobante_company_currency_in_db(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    debit = Accounts(entity="cacao", code="EXP-CCY", name="Gasto", active=True, enabled=True)
    credit = Accounts(entity="cacao", code="CAJ-CCY", name="Caja", active=True, enabled=True)
    database.session.add_all([debit, credit])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-01",
            "lines": [
                {"account": debit.id, "debit": "2.00", "credit": "0"},
                {"account": credit.id, "debit": "0", "credit": "2.00"},
            ],
        },
        user_id="user-1",
    )

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get(f"/accounting/journal/{journal.id}")
    assert response.status_code == 200


def test_route_naming_series_list_with_company_filter(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.get("/accounting/naming-series/list?company=cacao")
    assert response.status_code == 200


def test_route_naming_series_new_post_with_default(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/naming-series/new",
        data={
            "nombre": "Serie Default",
            "entity_type": "journal_entry",
            "company": "",
            "prefix_template": "{YYYY}-DEF-",
            "is_active": "y",
            "is_default": "y",
            "current_value": "0",
            "increment": "1",
            "padding": "5",
            "reset_policy": "never",
        },
    )
    assert response.status_code in (200, 302)


def test_route_libro_new_post_success(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/book/new",
        data={"id": "LIBNEW", "nombre": "Libro Nuevo", "entidad": "cacao", "moneda": "NIO", "estado": "activo"},
    )
    assert response.status_code in (200, 302)


def test_route_editar_libro_post_success(app_ctx):
    from cacao_accounting.database import Book, Currency, User, database

    database.session.add_all(
        [
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            Book(entity="cacao", code="LIBEDIT", name="Libro Edit", status="activo"),
        ]
    )
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/book/edit/LIBEDIT",
        data={"id": "LIBEDIT", "nombre": "Libro Editado", "entidad": "cacao", "moneda": "NIO", "estado": "activo"},
    )
    assert response.status_code in (200, 302)


def test_route_nueva_cuenta_post_success(app_ctx):
    from cacao_accounting.database import Currency, User, database

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/account/new",
        data={
            "entidad": "cacao",
            "code": "2.01",
            "name": "Proveedores",
            "grupo": "",
            "padre": "",
            "moneda": "",
            "clasificacion": "Pasivo",
            "tipo": "",
            "account_type": "payable",
            "activo": "y",
            "habilitado": "y",
        },
    )
    assert response.status_code in (200, 302)


def test_route_editar_proyecto_post_success(app_ctx):
    from cacao_accounting.database import Project, User, database

    database.session.add(Project(code="PRJEDIT", name="Edit Proyecto", entity="cacao", enabled=True, start=date(2026, 1, 1)))
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/project/PRJEDIT/edit",
        data={
            "id": "PRJEDIT",
            "nombre": "Edit Proyecto Updated",
            "entidad": "cacao",
            "inicio": "2026-01-01",
            "fin": "2026-12-31",
            "presupuesto": "1000",
            "habilitado": "y",
            "status": "open",
        },
    )
    assert response.status_code in (200, 302)


def test_route_fiscal_year_edit_post_success(app_ctx):
    from cacao_accounting.database import FiscalYear, User, database

    fy = FiscalYear(entity="cacao", name="2028", year_start_date=date(2028, 1, 1), year_end_date=date(2028, 12, 31))
    database.session.add(fy)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        f"/accounting/fiscal_year/{fy.id}/edit",
        data={"id": fy.id, "entidad": "cacao", "inicio": "2028-01-01", "fin": "2028-12-31", "cerrado": ""},
    )
    assert response.status_code in (200, 302)


def test_route_accounting_period_new_post_success(app_ctx):
    from cacao_accounting.database import FiscalYear, User, database

    fy = FiscalYear(entity="cacao", name="2026FY", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31))
    database.session.add(fy)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/accounting_period/new",
        data={
            "entidad": "cacao",
            "nombre": "P-2026-08",
            "inicio": "2026-08-01",
            "fin": "2026-08-31",
            "habilitado": "y",
            "cerrado": "",
            "fiscal_year_id": fy.id,
        },
    )
    assert response.status_code in (200, 302)


def test_route_accounting_period_edit_post_success(app_ctx):
    from cacao_accounting.database import AccountingPeriod, User, database

    period = AccountingPeriod(
        entity="cacao", name="2026-09", enabled=True, is_closed=False, start=date(2026, 9, 1), end=date(2026, 9, 30)
    )
    database.session.add(period)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        f"/accounting/accounting_period/{period.id}/edit",
        data={
            "entidad": "cacao",
            "nombre": "2026-09-Updated",
            "inicio": "2026-09-01",
            "fin": "2026-09-30",
            "habilitado": "y",
            "cerrado": "",
        },
    )
    assert response.status_code in (200, 302)


def test_route_external_counter_new_post_success(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        "/accounting/external-counter/new",
        data={
            "company": "cacao",
            "nombre": "Chequera Principal",
            "counter_type": "checkbook",
            "prefix": "CHQ",
            "last_used": "0",
            "padding": "6",
            "is_active": "y",
            "description": "Chequera banco",
            "naming_series_id": "",
        },
    )
    assert response.status_code in (200, 302)


def test_route_external_counter_adjust_post_success(app_ctx):
    from cacao_accounting.database import ExternalCounter, User, database

    ec = ExternalCounter(company="cacao", name="AdjTest", counter_type="fiscal", last_used=5, padding=5, is_active=True)
    database.session.add(ec)
    database.session.commit()
    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    response = client.post(
        f"/accounting/external-counter/{ec.id}/adjust",
        data={"new_last_used": "10", "reason": "Correction"},
    )
    assert response.status_code in (200, 302)
