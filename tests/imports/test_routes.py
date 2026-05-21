# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from cacao_accounting import create_app
from cacao_accounting.database import database
from cacao_accounting.modulos import init_modulos
from pathlib import Path

def test_imports_disabled_in_desktop_mode():
    app = create_app({
        "TESTING": True,
        "MODO_ESCRITORIO": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    with app.app_context():
        database.create_all()
    with app.test_client() as client:
        response = client.get("/imports/")
        assert response.status_code == 403

def test_imports_enabled_in_web_mode():
    app = create_app({
        "TESTING": True,
        "MODO_ESCRITORIO": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    with app.app_context():
        database.create_all()
        init_modulos() # Ensure "imports" module is in the DB
    with app.test_client() as client:
        # Should be 302 redirect to login if not logged in, but not 403
        response = client.get("/imports/")
        assert response.status_code == 302
        assert "/login" in response.location


def test_new_template_has_single_record_type_field():
    template_path = Path(__file__).resolve().parents[2] / "cacao_accounting" / "imports" / "templates" / "imports" / "new.html"
    content = template_path.read_text(encoding="utf-8")
    assert content.count('name="record_type"') == 1
