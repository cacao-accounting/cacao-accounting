# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from datetime import datetime

from cacao_accounting.printing.exceptions import PrintPermissionError, PrintTemplateNotFoundError
from cacao_accounting.printing.registry import register_printable_document
from cacao_accounting.printing.service import PrintService
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.database import database
import pytest
from cacao_accounting import create_app


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_print_service_html_structure():
    service = PrintService()
    html = service.build_print_html("<p>Hello</p>", "body { color: red; }")
    assert "<!doctype html>" in html
    assert "body { color: red; }" in html
    assert "<p>Hello</p>" in html
    assert 'href="/"' in html
    assert "window.print()" in html
    assert 'download="comprobante.pdf"' in html
    assert 'data-print-exclude="true"' in html
    assert '<main class="print-document">' in html


def test_template_resolution_fallback(app):
    with app.app_context():
        service = PrintService()
        register_printable_document(
            "test_doc",
            {
                "label": "Test Doc",
                "module": "tests",
                "root_context_name": "test",
                "permission": "tests.view",
                "context_builder": lambda *args, **kwargs: {},
                "sample_context_builder": lambda *args, **kwargs: {},
                "schema": {},
                "snippets": [],
            },
        )
        # Create a global default template
        tmpl = PrintTemplate(
            document_type="test_doc",
            code="test_code",
            name="Test",
            template_body="test",
            status="published",
            is_default=True,
            company_code=None,
        )
        database.session.add(tmpl)
        database.session.commit()

        resolved = service.resolve_template("test_doc", "any_company")
        assert resolved.code == "test_code"


def test_template_resolution_requires_registered_type(app):
    with app.app_context():
        service = PrintService()
        with pytest.raises(PrintTemplateNotFoundError):
            service.resolve_template("not_registered", "cacao")


def test_sales_order_print_requires_customer_ownership(app, monkeypatch):
    """A portal customer cannot print another customer's sales order."""
    from types import SimpleNamespace

    from cacao_accounting.printing.registry import get_printable_document

    with app.app_context():
        service = PrintService()
        document = SimpleNamespace(company="cacao", customer_id="party-owner")
        user = SimpleNamespace(classification="customer", party_id="party-other")
        monkeypatch.setattr(database.session, "get", lambda _model, _document_id: document)

        with pytest.raises(PrintPermissionError):
            service._authorize_document(
                "sales_order",
                "order-1",
                user,
                "cacao",
                get_printable_document("sales_order"),
            )


def test_print_context_includes_creation_and_approval_audit(app):
    """Printing exposes the creation and approval actors from AuditTrail."""
    from cacao_accounting.database import AuditTrail

    with app.app_context():
        database.session.add_all(
            [
                AuditTrail(
                    document_id="doc-1",
                    company="cacao",
                    document_type="sales_order",
                    action="created",
                    actor_user_id="creator",
                    actor_name="Creator",
                    timestamp=datetime(2026, 5, 26, 9, 0),
                ),
                AuditTrail(
                    document_id="doc-1",
                    company="cacao",
                    document_type="sales_order",
                    action="approved",
                    actor_user_id="approver",
                    actor_name="Approver",
                    timestamp=datetime(2026, 5, 26, 10, 0),
                ),
            ]
        )
        database.session.commit()
        context = {"audit": {"printed_by": "Printer", "printed_at": "2026-05-26 11:00"}}

        PrintService()._inject_audit_metadata(context, "doc-1", "cacao")

        assert context["audit"]["created_by"] == "Creator"
        assert context["audit"]["created_at"] == "2026-05-26 09:00"
        assert context["audit"]["approved_by"] == "Approver"
        assert context["audit"]["approved_at"] == "2026-05-26 10:00"


def test_public_validation_endpoint(client, app):
    from cacao_accounting.printing.models import PublicDocumentValidation
    from cacao_accounting.database import ComprobanteContable

    with app.app_context():
        # Create document to avoid 404 in validation service
        doc = ComprobanteContable(id="123", entity="cacao", status="posted")
        database.session.add(doc)
        val = PublicDocumentValidation(
            public_token="test-token",
            company_code="cacao",
            document_type="journal_entry",
            document_id="123",
            document_number="JOU-1",
            document_status="posted",
            validation_hash="744d03998b472e391b11e2f750d03c39379896792f39f37c35777174621c97a5",
        )
        database.session.add(val)
        database.session.commit()

    response = client.get("/public/validate_doc/test-token")
    assert response.status_code == 200
    assert b"JOU-1" in response.data


def test_all_printable_documents_sample_preview_and_watermarks(app):
    from cacao_accounting.printing.registry import PRINTABLE_DOCUMENTS
    from cacao_accounting.printing.seed import seed_print_templates

    with app.app_context():
        seed_print_templates()
        service = PrintService()

        for doc_type in PRINTABLE_DOCUMENTS:
            html = service.render_preview_html(
                document_type=doc_type,
                document_id=None,
                user="admin",
                company_code="cacao",
                sample=True,
            )
            assert "<!doctype html>" in html
            assert "watermark" in html or "status-badge" in html


def test_status_watermark_rendering_for_draft_and_cancelled(app):
    from cacao_accounting.printing.seed import seed_print_templates
    from cacao_accounting.printing.context import build_sales_invoice_sample_context

    with app.app_context():
        seed_print_templates()
        service = PrintService()

        context_draft = build_sales_invoice_sample_context()
        context_draft["invoice"]["status"] = "draft"
        template = service.resolve_template("sales_invoice", "cacao")
        rendered_draft = service.env.from_string(template.template_body).render(**context_draft)
        assert "watermark-draft" in rendered_draft
        assert "BORRADOR" in rendered_draft

        context_cancelled = build_sales_invoice_sample_context()
        context_cancelled["invoice"]["status"] = "cancelled"
        rendered_cancelled = service.env.from_string(template.template_body).render(**context_cancelled)
        assert "watermark-cancelled" in rendered_cancelled
        assert "ANULADO" in rendered_cancelled

        context_posted = build_sales_invoice_sample_context()
        context_posted["invoice"]["status"] = "posted"
        rendered_posted = service.env.from_string(template.template_body).render(**context_posted)
        assert "watermark" not in rendered_posted
        assert "status-posted" in rendered_posted


def test_seed_preserves_customized_system_template(app):
    from cacao_accounting.printing.seed import SEED_TEMPLATE_VERSION, seed_print_templates

    with app.app_context():
        seed_print_templates()
        template = PrintTemplate.query.filter_by(code="system_default_sales_invoice").first()
        assert template is not None
        assert template.version == SEED_TEMPLATE_VERSION
        original_body = template.template_body

        template.template_body = "CUSTOM BODY PRESERVED"
        template.version = SEED_TEMPLATE_VERSION
        database.session.commit()

        seed_print_templates()
        template = PrintTemplate.query.filter_by(code="system_default_sales_invoice").first()
        assert template.template_body == "CUSTOM BODY PRESERVED"
        assert template.template_body != original_body
