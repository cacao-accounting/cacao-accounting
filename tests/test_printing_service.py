# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from cacao_accounting.printing.exceptions import PrintTemplateNotFoundError
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
