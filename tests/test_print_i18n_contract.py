# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for localized printable template labels (#1932)."""

from __future__ import annotations

from pathlib import Path

from flask import render_template
from flask_babel import force_locale

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.printing.registry import PRINTABLE_DOCUMENTS, init_printing_registry
from cacao_accounting.printing.seed import (
    JOURNAL_TEMPLATE,
    LINES_TEMPLATE,
    ROOT_TEMPLATE_MAP,
    SEED_TEMPLATE_VERSION,
    _ensure_system_template,
)
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


def test_todas_las_variantes_de_plantilla_rinden_en_espanol_e_ingles(app):
    """Every built-in print template resolves its gettext labels in both locales."""
    init_printing_registry()
    service = PrintService()
    service.env.filters["money"] = lambda value, _currency: str(value)
    localized_roots = set()

    with app.app_context():
        for definition in PRINTABLE_DOCUMENTS.values():
            root_name = definition["root_context_name"]
            localized_roots.add(root_name)
            template = JOURNAL_TEMPLATE if root_name == "journal_entry" else ROOT_TEMPLATE_MAP[root_name]
            context = definition["sample_context_builder"]()

            with force_locale("es"):
                spanish = service.env.from_string(template).render(**context)
            with force_locale("en"):
                english = service.env.from_string(template).render(**context)

            if root_name == "journal_entry":
                assert "Cuenta" in spanish and "Account" in english
                assert "Debe" in spanish and "Debit" in english
            elif root_name == "invoice":
                assert "Precio unitario" in spanish and "Unit Price" in english
            elif root_name == "withholding_certificate":
                assert "Retención" in spanish and "Withholding" in english
            elif root_name == "payment":
                assert "Beneficiario" in spanish and "Payee" in english
            elif root_name == "check":
                assert "Cheque N.º" in spanish and "Check No." in english
            elif root_name == "revaluation":
                assert "Tasa anterior" in spanish and "Old rate" in english

    assert localized_roots == set(ROOT_TEMPLATE_MAP) | {"journal_entry"}


def test_listado_de_plantillas_localiza_fallbacks_de_tipo_y_estado(app):
    """Unknown legacy type/status codes in the admin list render as localized labels."""
    template = PrintTemplate(
        id=9,
        company_code=None,
        document_type="unknown_legacy_type",
        code="LEGACY-1",
        name="Legacy",
        template_body="<p>Legacy</p>",
        status="unknown_legacy_status",
        is_system=False,
        is_default=False,
        version=1,
    )
    rendered = {}
    for locale in ("es", "en"):
        with app.test_request_context("/admin/print-templates"), force_locale(locale):
            rendered[locale] = render_template(
                "admin/print_template_list.html",
                templates=[template],
                document_labels={},
                bank_labels={},
            )

    assert "Tipo documental desconocido" in rendered["es"]
    assert "Estado desconocido" in rendered["es"]
    assert "Unknown document type" in rendered["en"]
    assert "Unknown status" in rendered["en"]
    assert "unknown_legacy_type" not in rendered["es"] + rendered["en"]
    assert ">unknown_legacy_status<" not in rendered["es"] + rendered["en"]


def test_seed_actualiza_plantillas_de_sistema_de_versiones_anteriores(app):
    """Every built-in system template is replaced when the seed version advances."""
    with app.app_context():
        init_printing_registry()
        templates = []
        for document_type in PRINTABLE_DOCUMENTS:
            templates.append(
                PrintTemplate(
                    company_code=None,
                    document_type=document_type,
                    code=f"system_default_{document_type}",
                    name="Legacy system template",
                    template_body="old template body",
                    stylesheet_body="old style",
                    status="published",
                    is_system=True,
                    is_default=True,
                    version=SEED_TEMPLATE_VERSION - 1,
                )
            )
        database.session.add_all(templates)
        database.session.commit()

        for document_type, definition in PRINTABLE_DOCUMENTS.items():
            _ensure_system_template(document_type, definition["label"], definition["root_context_name"])
        for template in templates:
            database.session.refresh(template)

        assert all(template.version == SEED_TEMPLATE_VERSION for template in templates)
        assert all(template.template_body != "old template body" for template in templates)
        sales_template = next(template for template in templates if template.document_type == "sales_invoice")
        journal_template = next(template for template in templates if template.document_type == "journal_entry")
        assert "Precio unitario" in sales_template.template_body
        assert "Cuenta" in journal_template.template_body
        for template in templates:
            database.session.delete(template)
        database.session.commit()
