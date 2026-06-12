# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintTemplate, PrintTemplateVersion, PrintJobLog
from cacao_accounting.printing.service import PrintService
from cacao_accounting.printing.exceptions import TemplateValidationError


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


def test_template_security_validation(app):
    with app.app_context():
        service = PrintService()

        # Test script injection
        bad_html = "<div><script>alert(1)</script></div>"
        with pytest.raises(TemplateValidationError) as exc:
            service.validate_template(bad_html, "", "journal_entry")
        assert "etiquetas <script>" in str(exc.value)

        # Test inline event
        bad_html = '<div onclick="steal()">Click me</div>'
        with pytest.raises(TemplateValidationError) as exc:
            service.validate_template(bad_html, "", "journal_entry")
        assert "atributo 'onclick'" in str(exc.value)


def test_template_versioning(app):
    with app.app_context():
        service = PrintService()
        tmpl = PrintTemplate(
            document_type="journal_entry", code="vtest", name="Version Test", template_body="v1", status="draft"
        )
        database.session.add(tmpl)
        database.session.commit()

        # Create version before update
        service.create_version(tmpl, change_note="First version")

        tmpl.template_body = "v2"
        tmpl.version = 2
        database.session.commit()

        versions = (
            database.session.execute(database.select(PrintTemplateVersion).filter_by(template_id=tmpl.id)).scalars().all()
        )

        assert len(versions) == 1
        assert versions[0].template_body == "v1"


def test_print_job_logging(app):
    from cacao_accounting.database import User

    with app.app_context():
        service = PrintService()
        # Mock a user
        user = User(id="user1", user="admin")

        tmpl = PrintTemplate(
            document_type="journal_entry",
            code="logtest",
            name="Log Test",
            template_body="test",
            status="published",
            is_default=True,
        )
        database.session.add(tmpl)
        database.session.commit()

        # In a real app we'd need a real doc, but render_preview_html with sample=True works
        service.render_preview_html("journal_entry", None, user, "cacao", sample=True)

        logs = database.session.execute(database.select(PrintJobLog).filter_by(document_type="journal_entry")).scalars().all()

        assert len(logs) == 1
        assert logs[0].user_id == "user1"
        assert logs[0].output_format == "html_preview"
