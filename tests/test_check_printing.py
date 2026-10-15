# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Tests for check printing functionality, multi-language number-to-words and editable formats."""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.database import Bank, BankAccount, ExternalCounter, PaymentEntry, User, database
from cacao_accounting.printing.admin_routes import _bank_account_options, _clear_default
from cacao_accounting.printing.context import (
    build_check_print_context,
    build_check_sample_context,
    numero_a_letras,
)
from cacao_accounting.printing.exceptions import PrintingError
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.printing.registry import get_printable_document, init_printing_registry
from cacao_accounting.printing.seed import seed_print_templates
from cacao_accounting.printing.service import PrintService


@pytest.fixture
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


def test_numero_a_letras_multilingual():
    """Test Spanish and English number-to-words conversion helper."""
    # Spanish
    assert numero_a_letras(0, "NIO", lang="es") == "CERO NIO CON 00/100"
    assert numero_a_letras(1250.50, "NIO", lang="es") == "UN MIL DOSCIENTOS CINCUENTA NIO CON 50/100"
    assert numero_a_letras(100, "USD", lang="es") == "CIEN USD CON 00/100"
    assert numero_a_letras(21, "NIO", lang="es") == "VEINTIUNO NIO CON 00/100"
    assert numero_a_letras(1000000, "NIO", lang="es") == "UN MILLÓN NIO CON 00/100"
    assert numero_a_letras(2500000.75, "USD", lang="es") == "DOS MILLONES QUINIENTOS MIL USD CON 75/100"
    assert numero_a_letras(-50.25, "NIO", lang="es") == "MENOS CINCUENTA NIO CON 25/100"

    # English
    assert numero_a_letras(0, "USD", lang="en") == "ZERO USD AND 00/100"
    assert numero_a_letras(1250.50, "USD", lang="en") == "ONE THOUSAND TWO HUNDRED FIFTY USD AND 50/100"
    assert numero_a_letras(100, "USD", lang="en") == "ONE HUNDRED USD AND 00/100"
    assert numero_a_letras(21, "USD", lang="en") == "TWENTY ONE USD AND 00/100"
    assert numero_a_letras(1000000, "USD", lang="en") == "ONE MILLION USD AND 00/100"
    assert numero_a_letras(-50.25, "USD", lang="en") == "MINUS FIFTY USD AND 25/100"


def test_check_printable_document_registration(app_ctx):
    """Test check printable document registration and schema in registry."""
    init_printing_registry()
    doc_def = get_printable_document("check")
    assert doc_def is not None
    assert str(doc_def["label"]) == "Impresión de cheque"
    assert doc_def["module"] == "cash"
    assert "check" in doc_def["schema"]


def test_check_sample_context():
    """Test building sample context for check format design."""
    sample = build_check_sample_context()
    assert "check" in sample
    check = sample["check"]
    assert check["number"] == "10539"
    assert check["amount"] == Decimal("1250.50")
    words = check["amount_in_words"]
    assert "1250" in words or "DOSCIENTOS" in words or "HUNDRED" in words


def test_check_print_context_building(app_ctx):
    """Test check context generation from database PaymentEntry model."""
    payment = PaymentEntry(
        company="cacao",
        payment_type="pay",
        party_name="Distribuidora Central S.A.",
        paid_amount=Decimal("4500.00"),
        currency="NIO",
        posting_date=date(2026, 5, 26),
        mode_of_payment="check",
        external_number="CH-9876",
        remarks="Pago anticipado de suministros",
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()

    # Spanish context
    context_es = build_check_print_context(payment.id, "admin", "cacao", options={"lang": "es"})
    assert "check" in context_es
    check_es = context_es["check"]
    assert check_es["number"] == "CH-9876"
    assert check_es["payee_name"] == "Distribuidora Central S.A."
    assert check_es["amount"] == Decimal("4500.00")
    assert check_es["day"] == "26"
    assert check_es["month"] == "05"
    assert check_es["month_name"] == "Mayo"
    assert check_es["year"] == "2026"
    assert "CUATRO MIL QUINIENTOS NIO" in check_es["amount_in_words"]
    assert check_es["memo"] == "Pago anticipado de suministros"

    # English context
    context_en = build_check_print_context(payment.id, "admin", "cacao", options={"lang": "en"})
    check_en = context_en["check"]
    assert check_en["month_name"] == "May"
    assert "FOUR THOUSAND FIVE HUNDRED NIO AND 00/100" in check_en["amount_in_words"]


def test_check_template_seeding_and_rendering(app_ctx):
    """Test seeding system check template and rendering preview HTML."""
    seed_print_templates()
    service = PrintService()
    template = service.resolve_template("check", "cacao")
    assert template is not None
    assert template.document_type == "check"

    html = service.render_preview_html("check", None, "admin", "cacao", sample=True)
    assert "Comercial de Suministros S.A." in html
    assert "10539" in html


def test_customizing_system_check_template(app_ctx):
    """Test editing a system check template to adapt to pre-printed stock."""
    seed_print_templates()
    template = (
        database.session.execute(select(PrintTemplate).filter_by(document_type="check", is_system=True)).scalars().first()
    )
    assert template is not None
    assert template.is_system is True

    # Simulate modifying layout positioning in template body & stylesheet
    template.template_body += "\n<!-- Custom position for pre-printed stock -->"
    template.is_system = False
    database.session.commit()

    updated = database.session.get(PrintTemplate, template.id)
    assert updated.is_system is False
    assert "Custom position" in updated.template_body


def _make_bank_account(
    company: str,
    name: str = "Cuenta Cheques",
    counter_id: str | None = None,
    account_no: str = "100100998877",
) -> BankAccount:
    """Create a bank institution and account used to scope check formats."""
    bank = Bank(name=f"Banco {name}", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(
        bank_id=bank.id,
        company=company,
        account_name=name,
        account_no=account_no,
        currency="NIO",
        default_external_counter_id=counter_id,
    )
    database.session.add(account)
    database.session.commit()
    return account


def test_check_context_includes_bank_details(app_ctx):
    """El contexto del cheque resuelve el banco y el numero de cuenta correctos."""
    payout = _make_bank_account("cacao")
    payment = PaymentEntry(
        company="cacao",
        payment_type="pay",
        party_name="Proveedor S.A.",
        paid_amount=Decimal("100.00"),
        currency="NIO",
        mode_of_payment="check",
        bank_account_id=payout.id,
        external_number="CH-0001",
    )
    database.session.add(payment)
    database.session.commit()

    check = build_check_print_context(payment.id, "admin", "cacao")["check"]
    assert check["bank_name"] == "Banco Cuenta Cheques"
    assert check["bank_account_number"] == "100100998877"
    assert check["bank_account_id"] == payout.id


def test_check_number_falls_back_to_next_checkbook(app_ctx):
    """Sin numero asignado el cheque muestra el siguiente numero de la chequera."""
    counter = ExternalCounter(company="cacao", name="Chequera Banpro", counter_type="checkbook", last_used=10538, padding=8)
    database.session.add(counter)
    database.session.commit()
    payout = _make_bank_account("cacao", counter_id=counter.id)
    payment = PaymentEntry(
        company="cacao",
        payment_type="pay",
        party_name="Proveedor S.A.",
        paid_amount=Decimal("100.00"),
        currency="NIO",
        mode_of_payment="check",
        bank_account_id=payout.id,
        external_counter_id=counter.id,
    )
    database.session.add(payment)
    database.session.commit()

    check = build_check_print_context(payment.id, "admin", "cacao")["check"]
    assert check["next_check_number"] == "00010539"
    assert check["number"] == "00010539"


def test_check_print_requires_check_payment(app_ctx):
    """Solo se permite imprimir cheque si la forma de pago es cheque."""
    init_printing_registry()
    payment = PaymentEntry(
        company="cacao",
        payment_type="pay",
        party_name="Proveedor S.A.",
        paid_amount=Decimal("100.00"),
        currency="NIO",
        mode_of_payment="transfer",
    )
    database.session.add(payment)
    database.session.commit()

    with pytest.raises(PrintingError):
        PrintService().render_preview_html("check", payment.id, "admin", "cacao")


def _check_template(company: str | None, code: str, account_id: str | None, is_default: bool) -> PrintTemplate:
    template = PrintTemplate(
        company_code=company,
        document_type="check",
        bank_account_id=account_id,
        code=code,
        name=code,
        template_body="<div>CHECK {{ check.number }}</div>",
        status="published",
        is_default=is_default,
    )
    database.session.add(template)
    database.session.commit()
    return template


def test_check_template_resolution_per_bank_account(app_ctx):
    """Cada cuenta bancaria resuelve su propio formato con fallback a compania y global."""
    init_printing_registry()
    account_a = _make_bank_account("cacao", name="Cuenta A", account_no="1001")
    account_b = _make_bank_account("cacao", name="Cuenta B", account_no="1002")

    account_template = _check_template("cacao", "bank_a", account_a.id, is_default=True)
    company_template = _check_template("cacao", "company_default", None, is_default=True)

    service = PrintService()
    resolved_a = service.resolve_template("check", "cacao", bank_account_id=account_a.id)
    assert resolved_a.id == account_template.id

    resolved_b = service.resolve_template("check", "cacao", bank_account_id=account_b.id)
    assert resolved_b.id == company_template.id

    global_template = _check_template(None, "global_default", None, is_default=True)
    resolved_other = service.resolve_template("check", "otra", bank_account_id=None)
    assert resolved_other.id == global_template.id


def test_clear_default_scopes_by_bank_account(app_ctx):
    """El default de un formato de cheque se limpia solo dentro de su cuenta bancaria."""
    account_a = _make_bank_account("cacao", name="Cuenta A", account_no="2001")
    account_b = _make_bank_account("cacao", name="Cuenta B", account_no="2002")
    template_a = _check_template("cacao", "bank_a", account_a.id, is_default=True)
    template_b = _check_template("cacao", "bank_b", account_b.id, is_default=True)
    template_company = _check_template("cacao", "company", None, is_default=True)

    _clear_default(template_a)
    database.session.commit()

    assert database.session.get(PrintTemplate, template_a.id).is_default is False
    assert database.session.get(PrintTemplate, template_b.id).is_default is True
    assert database.session.get(PrintTemplate, template_company.id).is_default is True


def test_bank_account_options_include_bank_name(app_ctx):
    """El selector de formatos lista las cuentas con el nombre del banco."""
    _make_bank_account("cacao", name="Cuenta A")
    options = _bank_account_options()
    assert any("Banco Cuenta A" in option["label"] for option in options)
    assert all(option["company"] == "cacao" for option in options)


def test_numero_a_letras_apocope_and_large_numbers():
    """La conversion usa reglas numericas, no recortes de cadena."""
    assert numero_a_letras(21000, "NIO", lang="es") == "VEINTIÚN MIL NIO CON 00/100"
    assert numero_a_letras(31000, "NIO", lang="es") == "TREINTA Y UN MIL NIO CON 00/100"
    assert numero_a_letras(21000000, "NIO", lang="es") == "VEINTIÚN MILLONES NIO CON 00/100"
    assert numero_a_letras(1000000000, "USD", lang="es") == "UN MIL MILLONES USD CON 00/100"
    assert numero_a_letras(1000, "USD", lang="en") == "ONE THOUSAND USD AND 00/100"
    assert numero_a_letras(999999999, "USD", lang="en") == (
        "NINE HUNDRED NINETY NINE MILLION NINE HUNDRED NINETY NINE THOUSAND " "NINE HUNDRED NINETY NINE USD AND 00/100"
    )


def test_admin_create_and_duplicate_associates_bank_account(app_ctx):
    """El admin asocia un formato a una cuenta bancaria y lo duplica conservando la cuenta."""
    init_printing_registry()
    account = _make_bank_account("cacao", name="Cuenta A", account_no="3001")
    user = User(user="print_admin", e_mail="print_admin@example.com", password=b"secret", classification="admin", active=True)
    database.session.add(user)
    database.session.commit()

    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id

    response = client.post(
        "/admin/print-templates/new",
        data={
            "document_type": "check",
            "code": "bank_a",
            "name": "Formato Cheque A",
            "bank_account_id": account.id,
            "template_body": "<div>{{ check.number }}</div>",
            "paper_size": "letter",
            "orientation": "portrait",
        },
    )
    assert response.status_code in (200, 302)

    created = database.session.execute(select(PrintTemplate).filter_by(code="bank_a")).scalars().first()
    assert created is not None
    assert created.bank_account_id == account.id

    client.post(f"/admin/print-templates/{created.id}/duplicate")
    copy = database.session.execute(select(PrintTemplate).filter_by(code="bank_a_copy")).scalars().first()
    assert copy is not None
    assert copy.bank_account_id == account.id
    assert copy.is_default is False


def test_num2words_language_registry_and_regional_variants():
    """El registro de idiomas acepta variantes regionales y nuevos idiomas."""
    from dataclasses import replace

    from cacao_accounting.num2words import SPANISH, available_languages, numero_a_letras, register_language

    assert {"es", "en"}.issubset(set(available_languages()))
    assert numero_a_letras(5, "NIO", lang="es-NI") == "CINCO NIO CON 00/100"

    register_language(replace(SPANISH, code="xx", connector="WITH"))
    assert "xx" in available_languages()
    assert numero_a_letras(1, "NIO", lang="xx") == "UN NIO WITH 00/100"


def test_check_language_resolution_is_consistent(app_ctx):
    """Documento real y muestra resuelven el idioma con la misma funcion."""
    from cacao_accounting.printing.context import _resolve_lang

    assert _resolve_lang({"lang": "en"}) == "en"
    assert _resolve_lang(None) == _resolve_lang({})

    sample_en = build_check_sample_context(options={"lang": "en"})
    assert sample_en["check"]["month_name"] == "May"
