# SPDX-License-Identifier: Apache-2.0

"""Tests de integración para el Portal de Clientes y Portal de Proveedores."""

import sys
import os
from datetime import date
from decimal import Decimal

sys.path.append(os.path.join(os.path.dirname(__file__)))

from z_func import init_test_db
from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    User,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    Entity,
)
from cacao_accounting.auth.roles import asigna_rol_a_usuario
from cacao_accounting.auth import proteger_passwd

app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "test-secret-key-portal",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)


def test_portal_security_and_access():
    """Prueba el acceso y restricciones del Portal de Clientes y Proveedores."""
    with app.app_context():
        init_test_db(app)

        # 1. Crear terceros (Clientes y Proveedores)
        c1 = Party(code="CUST-001", name="Cliente 1", is_customer=True, is_active=True)
        c2 = Party(code="CUST-002", name="Cliente 2", is_customer=True, is_active=True)
        p1 = Party(code="SUPP-001", name="Proveedor 1", is_supplier=True, is_active=True)
        database.session.add_all([c1, c2, p1])
        database.session.flush()

        # 2. Crear Usuarios asociados a los terceros
        pwd = proteger_passwd("password123")
        u_cust1 = User(user="cliente1", name="Cliente Uno", password=pwd, active=True, party_id=c1.id)
        u_cust2 = User(user="cliente2", name="Cliente Dos", password=pwd, active=True, party_id=c2.id)
        u_supp1 = User(user="proveedor1", name="Proveedor Uno", password=pwd, active=True, party_id=p1.id)
        database.session.add_all([u_cust1, u_cust2, u_supp1])
        database.session.flush()

        # 3. Asignar roles especiales a los usuarios
        asigna_rol_a_usuario("cliente1", "customer")
        asigna_rol_a_usuario("cliente2", "customer")
        asigna_rol_a_usuario("proveedor1", "supplier")

        # 4. Crear facturas de venta y de compra para las pruebas
        comp = database.session.execute(database.select(Entity)).scalars().first()
        comp_code = comp.code if comp else "TEST"

        inv_c1 = SalesInvoice(
            customer_id=c1.id,
            customer_name=c1.name,
            company=comp_code,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=Decimal("100.00"),
        )
        inv_c2 = SalesInvoice(
            customer_id=c2.id,
            customer_name=c2.name,
            company=comp_code,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=Decimal("200.00"),
        )
        inv_p1 = PurchaseInvoice(
            supplier_id=p1.id,
            supplier_name=p1.name,
            company=comp_code,
            posting_date=date.today(),
            document_type="purchase_invoice",
            docstatus=1,
            grand_total=Decimal("500.00"),
        )
        database.session.add_all([inv_c1, inv_c2, inv_p1])
        database.session.flush()

        # Guardar líneas para simular detalle
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=inv_c1.id, item_code="ITM-1", qty=1, rate=Decimal("100.00"), amount=Decimal("100.00")
            )
        )
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=inv_c2.id, item_code="ITM-2", qty=1, rate=Decimal("200.00"), amount=Decimal("200.00")
            )
        )
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=inv_p1.id, item_code="ITM-3", qty=1, rate=Decimal("500.00"), amount=Decimal("500.00")
            )
        )
        database.session.commit()

        # --- PRUEBAS CON CLIENTE 1 ---
        with app.test_client() as client:
            # Login
            resp = client.post("/login", data={"usuario": "cliente1", "acceso": "password123"}, follow_redirects=True)
            # Debe redireccionar automáticamente a /portal/customer
            assert b"Portal del Cliente" in resp.data

            # Puede acceder a su propio dashboard
            dashboard_resp = client.get("/portal/customer")
            assert dashboard_resp.status_code == 200
            assert b"100.00" in dashboard_resp.data

            # No debe ver la factura del cliente 2 en su listado
            assert b"200.00" not in dashboard_resp.data

            # Puede acceder al detalle de su propia factura
            detail_resp = client.get(f"/portal/customer/invoice/{inv_c1.id}")
            assert detail_resp.status_code == 200
            assert b"Cliente 1" in detail_resp.data

            # NO puede acceder al detalle de la factura del cliente 2 (403 Forbidden)
            forbidden_resp = client.get(f"/portal/customer/invoice/{inv_c2.id}")
            assert forbidden_resp.status_code == 403

            # NO puede acceder al portal de proveedores (403 Forbidden)
            no_supplier_resp = client.get("/portal/supplier")
            assert no_supplier_resp.status_code == 403

            client.get("/logout")

        # --- PRUEBAS CON PROVEEDOR 1 ---
        with app.test_client() as client:
            # Login
            resp = client.post("/login", data={"usuario": "proveedor1", "acceso": "password123"}, follow_redirects=True)
            # Debe redireccionar automáticamente a /portal/supplier
            assert b"Portal del Proveedor" in resp.data

            # Puede acceder a su propio dashboard
            dashboard_resp = client.get("/portal/supplier")
            assert dashboard_resp.status_code == 200
            assert b"500.00" in dashboard_resp.data

            # Puede acceder al detalle de su propia factura
            detail_resp = client.get(f"/portal/supplier/invoice/{inv_p1.id}")
            assert detail_resp.status_code == 200
            assert b"Proveedor 1" in detail_resp.data

            # NO puede acceder al portal de clientes (403 Forbidden)
            no_customer_resp = client.get("/portal/customer")
            assert no_customer_resp.status_code == 403

            client.get("/logout")


def test_user_classification_and_roles_restriction():
    """Verifica que el administrador puede seleccionar clasificación de usuario y solo 'system' puede tener roles."""
    with app.test_client() as client:
        # Login como administrador
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # 1. Crear un usuario de tipo customer
        form_data = {
            "usuario": "portal_c3",
            "name": "Portal C3",
            "e_mail": "c3@portal.com",
            "classification": "customer",
            "active": "y",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        resp = client.post("/settings/users/new", data=form_data, follow_redirects=True)
        assert resp.status_code == 200
        client.get("/logout")

    # Verificar fuera del bloque client
    with app.app_context():
        u = database.session.execute(database.select(User).filter_by(user="portal_c3")).scalar_one_or_none()
        assert u is not None
        assert u.classification == "customer"
        uid = u.id

    with app.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
        # Intentar asignar roles al usuario de tipo customer
        # Debe redireccionar y mostrar la advertencia
        roles_resp = client.post(f"/settings/users/{uid}/roles", data={"roles": []}, follow_redirects=True)
        assert b"Solo los usuarios de tipo" in roles_resp.data
        client.get("/logout")


def test_portal_desktop_restriction():
    """Verifica que el portal de clientes/proveedores esté restringido en modo Desktop."""
    from cacao_accounting.runtime_mode import is_desktop_mode

    with app.app_context():
        # Forzar modo escritorio temporalmente en la config de la app
        app.config["MODO_ESCRITORIO"] = True
        try:
            assert is_desktop_mode() is True

            # Intentar login en modo escritorio como portal de cliente
            from cacao_accounting.auth.helpers import puede_iniciar_en_escritorio

            u = database.session.execute(database.select(User).filter_by(user="cliente1")).scalar_one_or_none()
            assert u is not None
            assert puede_iniciar_en_escritorio(u) is False

            # Intentar login en modo escritorio como portal de proveedor
            u2 = database.session.execute(database.select(User).filter_by(user="proveedor1")).scalar_one_or_none()
            assert u2 is not None
            assert puede_iniciar_en_escritorio(u2) is False

            # Intentar acceder a rutas del portal en modo escritorio directamente
            with app.test_client() as client:
                client.post("/login", data={"usuario": "cliente1", "acceso": "password123"})
                # Intentar acceder directamente a /portal/customer (debe dar 403 o no loguearse)
                resp = client.get("/portal/customer")
                assert resp.status_code in (403, 302)

        finally:
            # Restaurar estado
            app.config["MODO_ESCRITORIO"] = False
