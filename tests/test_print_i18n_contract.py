# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for localized printable template labels (#1932)."""

from __future__ import annotations

from pathlib import Path

from flask_babel import force_locale

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.printing.registry import PRINTABLE_DOCUMENTS, init_printing_registry
from cacao_accounting.printing.seed import LINES_TEMPLATE, SEED_TEMPLATE_VERSION, _ensure_system_template
from cacao_accounting.printing.service import PrintService

ROOT = Path(__file__).resolve().parents[1]


def test_default_template_labels_use_spanish_msgids():
    """The built-in template labels are source-language gettext strings."""
    source = (ROOT / "cacao_accounting" / "printing" / "seed.py").read_text(encoding="utf-8")
    for label in ("Cuenta", "Descripci\u00f3n", "Cantidad", "Precio unitario", "Impuestos", "Total general"):
        assert f'_("{label}")' in source


def test_english_catalog_has_print_label_translations():
    """The English catalog contains the translations used by the print template."""
    catalog = (ROOT / "cacao_accounting" / "translations" / "en" / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
    for label in ("Cuenta", "Descripci\u00f3n", "Cantidad", "Precio unitario", "Impuestos", "Total general"):
        assert f'msgid "{label}"' in catalog


def test_print_template_renders_localized_labels_and_unknown_status(app):
    """A real sandboxed Jinja render uses gettext and hides unknown status codes."""
    service = PrintService()
    service.env.filters["money"] = lambda value, _currency: str(value)
    context = {
        "title": "Factura",
        "doc": {
            "status": "unknown_legacy_status",
            "number": "INV-1",
            "date": "2026-11-23",
            "items": [],
            "currency": "NIO",
            "subtotal": 100,
            "taxes": 15,
            "grand_total": 115,
        },
        "company": {"name": "Cacao", "tax_id": "J-1", "address": "Managua", "default_currency": "NIO"},
        "audit": {
            "printed_by": "Ana",
            "printed_at": "2026-11-23",
            "created_by": "Ana",
            "created_at": "2026-11-23",
            "approved_by": "Ana",
            "approved_at": "2026-11-23",
        },
    }

    with app.app_context(), force_locale("es"):
        spanish = service.env.from_string(LINES_TEMPLATE).render(**context)
    with app.app_context(), force_locale("en"):
        english = service.env.from_string(LINES_TEMPLATE).render(**context)

    assert "Precio unitario" in spanish
    assert "Total general" in spanish
    assert "Estado desconocido" in spanish
    assert "Unit Price" in english
    assert "Grand total" in english
    assert "Unknown status" in english
    assert ">unknown_legacy_status<" not in spanish + english


def test_seed_actualiza_plantillas_de_sistema_de_versiones_anteriores(app):
    """Existing system templates are replaced when the seed version advances."""
    with app.app_context():
        init_printing_registry()
        definition = PRINTABLE_DOCUMENTS["sales_invoice"]
        template = PrintTemplate(
            company_code=None,
            document_type="sales_invoice",
            code="system_default_sales_invoice",
            name="Invoice basic",
            template_body="old template body",
            stylesheet_body="old style",
            status="published",
            is_system=True,
            is_default=True,
            version=SEED_TEMPLATE_VERSION - 1,
        )
        database.session.add(template)
        database.session.commit()

        _ensure_system_template("sales_invoice", definition["label"], definition["root_context_name"])
        database.session.refresh(template)

        assert template.version == SEED_TEMPLATE_VERSION
        assert "Precio unitario" in template.template_body
        assert template.template_body != "old template body"
        database.session.delete(template)
        database.session.commit()
