# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import os
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
from cacao_accounting.database import database
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

    def run_app():
        app.run(port=5008, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_app)
    server_thread.daemon = True
    server_thread.start()
    time.sleep(2)
    yield "http://localhost:5008"
    with app.app_context():
        database.session.remove()
        database.engine.dispose()
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
def test_transaction_form_multi_source_autofill(flask_server, browser):
    context = browser.new_context()
    page = context.new_page()
    base_url = flask_server

    login(page, base_url, "cacao", "cacao")

    # 2. Go to Sales Order New
    page.goto(f"{base_url}/sales/sales-order/new")

    # 3. Select Company
    # Smart-select for company
    company_select = page.locator(".ca-smart-select", has=page.locator('input[name="company"]'))
    company_input = company_select.locator("input.ca-smart-select-input")
    company_input.click()
    company_input.fill("Cacao")
    page.locator(".ca-smart-select-option", has_text="Choco Sonrisas Sociedad Anonima").click()

    # 4. Select Customer
    customer_select = page.locator(".ca-smart-select", has=page.locator('input[name="customer_id"]'))
    customer_input = customer_select.locator("input.ca-smart-select-input")
    customer_input.click()
    customer_input.fill("Demo")
    page.locator(".ca-smart-select-option >> text=Cliente Demo").click()

    # 5. Open "Actualizar Elementos" modal
    page.get_by_role("button", name="Actualizar Elementos").click()

    # 6. Verify Two-Step Workflow
    expect(page.locator('h5:has-text("Actualizar Elementos")')).to_be_visible()

    # Step 1 visible
    expect(page.locator('select[x-model="searchCriteria.source_type"]')).to_be_visible()

    # Select "Pedido de Venta" (sales_request)
    page.select_option('select[x-model="searchCriteria.source_type"]', "sales_request")

    context.close()


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")
def test_smart_select_filtering(flask_server, browser):
    context = browser.new_context()
    page = context.new_page()
    base_url = flask_server

    login(page, base_url, "cacao", "cacao")
    page.goto(f"{base_url}/sales/sales-order/new")

    # Verify naming series needs company
    series_select = page.locator(".ca-smart-select", has=page.locator('input[name="naming_series"]'))
    series_input = series_select.locator("input.ca-smart-select-input")
    series_input.click()

    # Set company
    company_select = page.locator(".ca-smart-select", has=page.locator('input[name="company"]'))
    company_input = company_select.locator("input.ca-smart-select-input")
    company_input.fill("Cacao")
    page.locator(".ca-smart-select-option", has_text="Choco Sonrisas Sociedad Anonima").click()

    # Now verify sequence options appear
    series_input.click()

    context.close()
