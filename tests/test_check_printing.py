# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Tests for check printing functionality, multi-language number-to-words and editable formats."""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.database import PaymentEntry, database
from cacao_accounting.printing.context import (
    build_check_print_context,
    build_check_sample_context,
    numero_a_letras,
)
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.printing.registry import get_printable_document, init_printing_registry
from cacao_accounting.printing.seed import seed_print_templates
from cacao_accounting.printing.service import PrintService


@pytest.fixture
def app_ctx():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-key", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
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
    template = database.session.execute(
        select(PrintTemplate).filter_by(document_type="check", is_system=True)
    ).scalars().first()
    assert template is not None
    assert template.is_system is True

    # Simulate modifying layout positioning in template body & stylesheet
    template.template_body += "\n<!-- Custom position for pre-printed stock -->"
    template.is_system = False
    database.session.commit()

    updated = database.session.get(PrintTemplate, template.id)
    assert updated.is_system is False
    assert "Custom position" in updated.template_body
