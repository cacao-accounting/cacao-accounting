# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Montenegro Reyes

import os
import tempfile
import threading
import time
import pytest
from datetime import date
from decimal import Decimal
from werkzeug.serving import make_server

os.environ["CACAO_ACCOUNTING_DESKTOP"] = "False"

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

        # Grant access to books
        from cacao_accounting.database import Book, UserBookAccess

        books = database.session.execute(database.select(Book)).scalars().all()
        for username, _, _ in user_list:
            user = database.session.execute(database.select(User).filter_by(user=username)).scalars().first()
            if user:
                for book in books:
                    exists = database.session.execute(
                        database.select(UserBookAccess).filter_by(user_id=user.id, book_id=book.id)
                    ).first()
                    if not exists:
                        access = UserBookAccess(
                            user_id=user.id,
                            book_id=book.id,
                            can_read=True,
                            can_write=True,
                        )
                        database.session.add(access)
        database.session.commit()

        # Let's also ensure cacao has permissions
        user_cacao = database.session.execute(database.select(User).filter_by(user="cacao")).scalars().first()
        if user_cacao:
            for book in books:
                exists = database.session.execute(
                    database.select(UserBookAccess).filter_by(user_id=user_cacao.id, book_id=book.id)
                ).first()
                if not exists:
                    access = UserBookAccess(
                        user_id=user_cacao.id,
                        book_id=book.id,
                        can_read=True,
                        can_write=True,
                    )
                    database.session.add(access)
            database.session.commit()

        # Add stock so we have available stock for sales order reservation
        from cacao_accounting.database import StockEntry, StockEntryItem
        from cacao_accounting.contabilidad.posting import submit_document

        se = StockEntry(
            purpose="material_receipt", company="cacao", posting_date=date.today(), to_warehouse="PRINCIPAL", docstatus=0
        )
        database.session.add(se)
        database.session.flush()
        sei = StockEntryItem(
            stock_entry_id=se.id,
            item_code="ART-001",
            target_warehouse="PRINCIPAL",
            qty=Decimal("100"),
            uom="UND",
            qty_in_base_uom=Decimal("100"),
            basic_rate=Decimal("50"),
            amount=Decimal("5000"),
        )
        database.session.add(sei)
        database.session.commit()
        submit_document(se)
        database.session.commit()

    server = make_server("127.0.0.1", 5009, app)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    time.sleep(2)
    yield "http://localhost:5009"

    server.shutdown()
    server_thread.join(timeout=5)

    # Explicitly dispose SQLAlchemy connections so SQLite file is unlocked on Windows.
    from cacao_accounting.database import database

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
    page.wait_for_url(lambda url: "/index" in url or "/app" in url or url.endswith("/"), timeout=15000)


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")
def test_document_flow_happy_paths_o2c_and_s2p(flask_server, browser):
    os.makedirs("/home/jules/verification", exist_ok=True)
    context = browser.new_context()
    page = context.new_page()
    base_url = flask_server

    # 1. Login with cacao
    login(page, base_url, "cacao", "cacao")

    # ==========================================
    # FLOW 1: Order to Cash (O2C) Happy Path
    # ==========================================

    # Navigate to Sales Order list and click "Nuevo"
    page.goto(f"{base_url}/sales/sales-order/new?company=cacao")
    page.wait_for_timeout(500)

    # Select Company
    company_select = page.locator(".ca-smart-select", has=page.locator('input[name="company"]'))
    company_input = company_select.locator("input.ca-smart-select-input")
    company_input.click()
    company_input.fill("Cacao")
    page.locator(".ca-smart-select-option", has_text="Choco Sonrisas Sociedad Anonima").click()
    page.wait_for_timeout(500)

    # Select Customer
    customer_select = page.locator(".ca-smart-select", has=page.locator('input[name="customer_id"]'))
    customer_input = customer_select.locator("input.ca-smart-select-input")
    customer_input.click()
    customer_input.fill("Demo")
    page.locator(".ca-smart-select-option >> text=Cliente Demo").click()
    page.wait_for_timeout(500)

    # Use item list grid: select item using smart-select
    item_select = page.locator(".ca-smart-select", has=page.locator('input[name="item_code_0"]'))
    item_input = item_select.locator("input.ca-smart-select-input")
    item_input.click()
    item_input.fill("ART-001")
    page.locator(".ca-smart-select-option", has_text="ART-001").click()
    page.wait_for_timeout(500)

    page.locator('input[name="qty_0"]').fill("5")
    page.locator('input[name="rate_0"]').fill("100")
    page.wait_for_timeout(500)

    # Set Warehouse in the order form via line details modal
    page.locator("button:has(.bi-pencil)").first.click()
    page.wait_for_timeout(1000)
    page.locator('select[x-model="modalLine.warehouse"]').select_option("PRINCIPAL")
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Guardar detalle").click()
    page.wait_for_timeout(500)

    # Submit the form to create a new draft Sales Order
    page.get_by_role("button", name="Guardar").click()
    expect(page.locator(".badge.bg-secondary")).to_be_visible()

    # Approve (Submit) the Sales Order
    page.get_by_role("button", name="Aprobar").click()
    expect(page.locator(".badge.bg-success")).to_be_visible()

    # Now use "Crear" shortcut dropdown to create a Sales Invoice (Factura)
    page.get_by_role("button", name="Crear").click()
    page.wait_for_timeout(500)
    page.get_by_role("link", name="Crear Factura").click()
    page.wait_for_timeout(1500)

    # Select Customer in Sales Invoice (required)
    customer_select = page.locator(".ca-smart-select", has=page.locator('input[name="customer_id"]'))
    customer_input = customer_select.locator("input.ca-smart-select-input")
    customer_input.click()
    customer_input.fill("Demo")
    page.locator(".ca-smart-select-option >> text=Cliente Demo").click()
    page.wait_for_timeout(500)

    # Wait for the background prefill to load line items into the grid
    expect(page.locator('input[name="item_code_0"]')).to_have_value("ART-001")

    # Click "Guardar" to save it as draft
    page.get_by_role("button", name="Guardar").click()
    expect(page.locator(".badge.bg-secondary")).to_be_visible()

    # Approve the Sales Invoice
    try:
        page.get_by_role("button", name="Aprobar").click()
        expect(page.locator(".badge.bg-success")).to_be_visible()
    except Exception as e:
        with open("/home/jules/verification/page_error.html", "w") as f:
            f.write(page.content())
        raise e

    # Verify the document flow tree on the approved invoice
    # Wait for Alpine to initialize
    page.wait_for_function("window.Alpine !== undefined")
    page.wait_for_timeout(1500)

    # Locate the Collapsible header and toggle it open
    flow_header = page.locator(".ca-document-flow .ca-card-header")
    flow_header.scroll_into_view_if_needed()
    flow_header.click()
    page.wait_for_timeout(1500)

    # Assert that the Sales Order and the current Sales Invoice appear inside the document flow list
    # The current invoice is marked as "Actual" and the source order should be in the "Origen" section
    expect(page.locator(".ca-document-flow__section", has_text="Documento actual")).to_be_visible()
    expect(page.locator(".ca-document-flow__section", has_text="Origen / Documentos aplicados")).to_be_visible()

    # Capture O2C flow success screenshot
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)
    page.screenshot(path="/home/jules/verification/screenshots/verification_o2c.png")

    # ==========================================
    # FLOW 2: Source to Pay (S2P) Happy Path
    # ==========================================

    # Navigate to Purchase Order New
    page.goto(f"{base_url}/buying/purchase-order/new?company=cacao")
    page.wait_for_timeout(500)

    # Select Company
    company_select = page.locator(".ca-smart-select", has=page.locator('input[name="company"]'))
    company_input = company_select.locator("input.ca-smart-select-input")
    company_input.click()
    company_input.fill("Cacao")
    page.locator(".ca-smart-select-option", has_text="Choco Sonrisas Sociedad Anonima").click()
    page.wait_for_timeout(500)

    # Select Supplier
    supplier_select = page.locator(".ca-smart-select", has=page.locator('input[name="supplier_id"]'))
    supplier_input = supplier_select.locator("input.ca-smart-select-input")
    supplier_input.click()
    supplier_input.fill("Demo")
    page.locator(".ca-smart-select-option >> text=Proveedor Demo").click()
    page.wait_for_timeout(500)

    # Use item list grid: select item using smart-select
    item_select = page.locator(".ca-smart-select", has=page.locator('input[name="item_code_0"]'))
    item_input = item_select.locator("input.ca-smart-select-input")
    item_input.click()
    item_input.fill("ART-001")
    page.locator(".ca-smart-select-option", has_text="ART-001").click()
    page.wait_for_timeout(500)

    page.locator('input[name="qty_0"]').fill("10")
    page.locator('input[name="rate_0"]').fill("50")
    page.wait_for_timeout(500)

    # Submit to save Purchase Order
    page.get_by_role("button", name="Guardar").click()
    expect(page.locator(".badge.bg-secondary")).to_be_visible()

    # Approve the Purchase Order
    page.get_by_role("button", name="Aprobar").click()
    expect(page.locator(".badge.bg-success")).to_be_visible()

    # Use "Crear" dropdown to create a Purchase Receipt (Recepción)
    page.get_by_role("button", name="Crear").click()
    page.wait_for_timeout(500)
    page.get_by_role("link", name="Crear Recepción").click()
    page.wait_for_timeout(1500)

    # Select Supplier in Purchase Receipt
    supplier_select = page.locator(".ca-smart-select", has=page.locator('input[name="supplier_id"]'))
    supplier_input = supplier_select.locator("input.ca-smart-select-input")
    supplier_input.click()
    supplier_input.fill("Demo")
    page.locator(".ca-smart-select-option >> text=Proveedor Demo").click()
    page.wait_for_timeout(500)

    # Wait for the background prefill to load line items into the grid
    expect(page.locator('input[name="item_code_0"]')).to_have_value("ART-001")

    # Set Warehouse in the receipt form via line details modal
    page.locator("button:has(.bi-pencil)").first.click()
    page.wait_for_timeout(1000)
    page.locator('select[x-model="modalLine.warehouse"]').select_option("PRINCIPAL")
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Guardar detalle").click()
    page.wait_for_timeout(500)

    # Save Purchase Receipt
    page.get_by_role("button", name="Guardar").click()
    expect(page.locator(".badge.bg-secondary")).to_be_visible()

    # Approve Purchase Receipt
    page.get_by_role("button", name="Aprobar").click()
    expect(page.locator(".badge.bg-success")).to_be_visible()

    # Use "Crear" dropdown to create a Purchase Invoice (Factura de Compra)
    page.get_by_role("button", name="Crear").click()
    page.wait_for_timeout(500)
    page.get_by_role("link", name="Crear Factura").click()
    page.wait_for_timeout(1500)

    # Select Supplier in Purchase Invoice (required)
    supplier_select = page.locator(".ca-smart-select", has=page.locator('input[name="supplier_id"]'))
    supplier_input = supplier_select.locator("input.ca-smart-select-input")
    supplier_input.click()
    supplier_input.fill("Demo")
    page.locator(".ca-smart-select-option >> text=Proveedor Demo").click()
    page.wait_for_timeout(500)

    # Wait for the background prefill to load line items into the grid
    expect(page.locator('input[name="item_code_0"]')).to_have_value("ART-001")

    # Fill supplier invoice number (mandatory)
    page.locator('input[name="supplier_invoice_no"]').fill("SUP-INV-PLAYWRIGHT")
    page.wait_for_timeout(500)

    # Save Purchase Invoice
    page.get_by_role("button", name="Guardar").click()
    expect(page.locator(".badge.bg-secondary")).to_be_visible()

    # Approve Purchase Invoice
    page.get_by_role("button", name="Aprobar").click()
    expect(page.locator(".badge.bg-success")).to_be_visible()

    # Expand the Document Flow tree card on Purchase Invoice
    # Wait for Alpine to initialize
    page.wait_for_function("window.Alpine !== undefined")
    page.wait_for_timeout(1500)

    flow_header = page.locator(".ca-document-flow .ca-card-header")
    flow_header.scroll_into_view_if_needed()
    flow_header.click()
    page.wait_for_timeout(1500)

    # Check that document flow sections exist on this invoice
    expect(page.locator(".ca-document-flow__section", has_text="Documento actual")).to_be_visible()
    expect(page.locator(".ca-document-flow__section", has_text="Origen / Documentos aplicados")).to_be_visible()

    # Take second screenshot showing S2P Document Flow
    page.screenshot(path="/home/jules/verification/screenshots/verification_s2p.png")

    context.close()
