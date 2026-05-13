# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import os

os.environ["CACAO_ACCOUNTING_DESKTOP"] = "False"

import tempfile
import threading
import time
import pytest

try:
    from playwright.sync_api import expect, sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from cacao_accounting import create_app
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.config import configuracion


@pytest.fixture(scope="module")
def flask_server():
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "playwright-test-key",
            "CACAO_ACCOUNTING_DESKTOP": "False",
        }
    )

    with app.app_context():
        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=True)
        from cacao_accounting.auth import proteger_passwd
        from cacao_accounting.auth.roles import asigna_rol_a_usuario
        from cacao_accounting.database import User, database

        # Ensure we have active users with roles
        user_list = [
            ("manager_ui", "manager123", "accounting_manager"),
            ("regular_ui", "regular123", "accounting_user"),
        ]
        for username, password, role in user_list:
            if not database.session.execute(database.select(User).filter_by(user=username)).first():
                u = User(user=username, password=proteger_passwd(password), active=True, classification="system")
                database.session.add(u)
                database.session.commit()
                try:
                    asigna_rol_a_usuario(username, role)
                except ValueError:
                    pass
        database.session.commit()

    def run_app():
        app.run(port=5006, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_app)
    server_thread.daemon = True
    server_thread.start()

    time.sleep(2)
    yield "http://localhost:5006"

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="module")
def browser():
    if not HAS_PLAYWRIGHT:
        pytest.skip("Playwright not installed")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            pytest.skip(f"Browser launch failed: {e}")
        yield browser
        browser.close()


def login(page, base_url, username, password):
    page.goto(f"{base_url}/login")
    page.locator('input[name="usuario"]').fill(username)
    page.locator('input[name="acceso"]').fill(password)
    page.get_by_role("button", name="Iniciar Sesión").click()
    # Wait for either home or app dashboard
    page.wait_for_url(lambda url: "/index" in url or "/app" in url or url.endswith("/"), timeout=15000)


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")
def test_reports_navigation(flask_server, browser):
    context = browser.new_context()
    page = context.new_page()
    base_url = flask_server

    login(page, base_url, "manager_ui", "manager123")

    # Go to accounting module
    page.goto(f"{base_url}/accounting/")

    # Check if report links exist
    expect(page.get_by_role("link", name="Balance General")).to_be_visible()

    # Navigate to Balance General
    page.get_by_role("link", name="Balance General").click()
    expect(page.locator("h5:has-text('Balance General')")).to_be_visible()

    context.close()

@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")
def test_journal_entry_list_visibility(flask_server, browser):
    context = browser.new_context()
    page = context.new_page()
    base_url = flask_server

    login(page, base_url, "manager_ui", "manager123")
    page.goto(f"{base_url}/accounting/journal/list")

    # Header should be visible (Title is h5)
    expect(page.locator("h5:has-text('Listado de Comprobantes Contables')")).to_be_visible()
    # 'Nuevo' button should be visible for manager
    expect(page.get_by_role("link", name="Nuevo")).to_be_visible()

    context.close()

@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")
def test_rbac_user_restricted_visibility(flask_server, browser):
    context = browser.new_context()
    page = context.new_page()
    base_url = flask_server

    login(page, base_url, "regular_ui", "regular123")
    page.goto(f"{base_url}/accounting/journal/list")

    # Can see list (Title is h5)
    expect(page.locator("h5:has-text('Listado de Comprobantes Contables')")).to_be_visible()
    # SHOULD NOT see 'Nuevo' button (accounting_user role has no 'create' permission)
    expect(page.get_by_role("link", name="Nuevo")).not_to_be_visible()

    context.close()
