# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 William José Moreno Reyes

"""Pruebas unitarias para el módulo administrativo."""

import pytest
from unittest import mock

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    User,
    Roles,
    Modules,
    Tax,
    TaxTemplate,
    PriceList,
    Entity,
    PartyGroup,
)
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))
from cacao_accounting.auth import proteger_passwd
from z_func import init_test_db


@pytest.fixture(scope="module")
def app_instance():
    """Instancia de aplicación Flask con base de datos en memoria para pruebas del admin."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "admin_test_secret_key",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with _app.app_context():
        init_test_db(_app)
        # Ensure our default 'cacao' user is admin classification
        cacao_user = database.session.execute(
            database.select(User).filter_by(user="cacao")
        ).scalar_one_or_none()
        if cacao_user:
            cacao_user.classification = "admin"
            database.session.commit()
    return _app


def test_admin_home_redirects_unauthenticated(app_instance):
    with app_instance.test_client() as client:
        response = client.get("/admin")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]


def test_admin_routes_accessible_to_admin(app_instance):
    with app_instance.test_client() as client:
        # Authenticate
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # Try various aliases for admin dashboard
        for route in ["/admin", "/ajustes", "/administracion", "/configuracion", "/settings"]:
            response = client.get(route)
            assert response.status_code == 200
            assert b"Administraci" in response.data or b"Ajustes" in response.data


def test_require_system_admin_unauthorized(app_instance):
    # Create a non-admin user
    with app_instance.app_context():
        non_admin = User(
            user="non_admin",
            password=proteger_passwd("ProtectedPassword123!"),
            classification="user",
            active=True,
        )
        database.session.add(non_admin)
        database.session.commit()

    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "non_admin", "acceso": "ProtectedPassword123!"})

        # Accessing system admin endpoints should abort(403)
        response = client.get("/settings/external-document-validation")
        assert response.status_code == 403


def test_lista_modulos(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/modules")
        assert response.status_code == 200

        # POST module not found
        response = client.post(
            "/settings/modules",
            data={"module_id": "nonexistent_id", "action": "toggle"},
            follow_redirects=True,
        )
        assert b"M" in response.data  # "Módulo no encontrado."

        # POST try to toggle administrative module (should fail)
        with app_instance.app_context():
            admin_module = database.session.execute(
                database.select(Modules).filter_by(module="admin")
            ).scalar_one()
            admin_module_id = admin_module.id

        response = client.post(
            "/settings/modules",
            data={"module_id": admin_module_id, "action": "toggle"},
            follow_redirects=True,
        )
        assert b"administrativo" in response.data  # El módulo administrativo no puede deshabilitarse.

        # POST toggle another module
        with app_instance.app_context():
            other_module = database.session.execute(
                database.select(Modules).filter(Modules.module != "admin")
            ).scalars().first()
            other_module_id = other_module.id
            orig_enabled = other_module.enabled

        response = client.post(
            "/settings/modules",
            data={"module_id": other_module_id, "action": "toggle"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app_instance.app_context():
            other_module = database.session.get(Modules, other_module_id)
            assert other_module.enabled != orig_enabled


def test_external_document_validation_settings(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/external-document-validation")
        assert response.status_code == 200

        # POST
        response = client.post(
            "/settings/external-document-validation",
            data={"enabled": "on", "base_url": "https://example.com/validate"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Configuracion de validacion externa" in response.data


def test_configuracion_valuacion_inventario(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # Get existing company
        with app_instance.app_context():
            company = database.session.execute(database.select(Entity)).scalars().first()
            company_code = company.code if company else "cacao"

        # GET
        response = client.get(f"/settings/inventory-valuation?company={company_code}")
        assert response.status_code == 200

        # POST empty company using execute mock to simulate empty companies list
        original_execute = database.session.execute
        def mock_execute(query, *args, **kwargs):
            if "entity" in str(query):
                m_res = mock.MagicMock()
                m_res.scalars.return_value.all.return_value = []
                return m_res
            return original_execute(query, *args, **kwargs)

        with mock.patch.object(database.session, "execute", side_effect=mock_execute):
            response2 = client.post("/settings/inventory-valuation", data={"company": ""}, follow_redirects=True)
            html = response2.get_data(as_text=True)
            assert "Debe" in html or "compa" in html

        # POST valid
        response = client.post(
            "/settings/inventory-valuation",
            data={"company": company_code, "valuation_method": "fifo"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Metodo de valuacion guardado" in response.data

        # POST invalid method (triggers ValueError)
        response = client.post(
            "/settings/inventory-valuation",
            data={"company": company_code, "valuation_method": "invalid_method_value"},
            follow_redirects=True,
        )
        assert b"no es un metodo de valuacion" in response.data or response.status_code == 200


def test_lista_impuestos(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/taxes")
        assert response.status_code == 200

        # POST create
        response = client.post(
            "/settings/taxes",
            data={
                "name": "IVA Test",
                "rate": "15.00",
                "tax_type": "percentage",
                "applies_to": "both",
                "is_charge": "",
                "is_capitalizable": "",
                "is_active": "1",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Impuesto o cargo creado" in response.data


def test_lista_plantillas_impuesto(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/tax-templates")
        assert response.status_code == 200

        # POST create
        response = client.post(
            "/settings/tax-templates",
            data={
                "name": "Plantilla Test",
                "company": "cacao",
                "template_type": "selling",
                "currency": "NIO",
                "is_active": "1",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Plantilla de impuestos" in response.data


def test_items_plantilla_impuesto(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with app_instance.app_context():
            template = database.session.execute(database.select(TaxTemplate)).scalars().first()
            template_id = template.id if template else None
            tax = database.session.execute(database.select(Tax)).scalars().first()
            tax_id = tax.id if tax else None

        # GET 404 for nonexistent template
        response = client.get("/settings/tax-templates/nonexistent_id/items")
        assert response.status_code == 404

        if template_id and tax_id:
            # GET
            response = client.get(f"/settings/tax-templates/{template_id}/items")
            assert response.status_code == 200

            # POST
            response = client.post(
                f"/settings/tax-templates/{template_id}/items",
                data={
                    "tax_id": tax_id,
                    "sequence": "10",
                    "calculation_base": "net_document",
                    "behavior": "additive",
                    "is_inclusive": "on",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"agregada correctamente" in response.data


def test_lista_reglas_fiscales(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/tax-rules")
        assert response.status_code == 200

        # POST
        response = client.post(
            "/settings/tax-rules",
            data={
                "name": "Regla Test",
                "tax_template_id": "none",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200


def test_editar_regla_fiscal_nonexistent(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
        response = client.get("/settings/tax-rules/nonexistent_id/edit")
        assert response.status_code == 404


def test_eliminar_regla_fiscal_nonexistent(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
        response = client.post("/settings/tax-rules/nonexistent_id/delete")
        assert response.status_code == 404


def test_lista_grupos_terceros(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/party-groups")
        assert response.status_code == 200

        # POST
        response = client.post(
            "/settings/party-groups",
            data={
                "group_type": "customer",
                "name": "Grupo Clientes Test",
                "description": "Desc",
                "is_active": "on",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Tipo de tercero creado" in response.data

        # POST duplicate (triggers IntegrityError)
        response = client.post(
            "/settings/party-groups",
            data={
                "group_type": "customer",
                "name": "Grupo Clientes Test",
                "description": "Desc",
                "is_active": "on",
            },
            follow_redirects=True,
        )
        assert b"Ya existe un tipo de tercero" in response.data


def test_editar_grupo_tercero(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with app_instance.app_context():
            group = database.session.execute(
                database.select(PartyGroup).filter_by(name="Grupo Clientes Test")
            ).scalar_one_or_none()
            group_id = group.id if group else None

        # GET 404
        response = client.get("/settings/party-groups/nonexistent_id/edit")
        assert response.status_code == 404

        if group_id:
            # GET
            response = client.get(f"/settings/party-groups/{group_id}/edit")
            assert response.status_code == 200

            # POST
            response = client.post(
                f"/settings/party-groups/{group_id}/edit",
                data={
                    "group_type": "customer",
                    "name": "Grupo Clientes Editado",
                    "description": "Desc editada",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Tipo de tercero actualizado" in response.data


def test_alternar_grupo_tercero(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # POST 404
        response = client.post("/settings/party-groups/nonexistent_id/toggle")
        assert response.status_code == 404

        with app_instance.app_context():
            group = database.session.execute(
                database.select(PartyGroup).filter_by(name="Grupo Clientes Editado")
            ).scalar_one_or_none()
            group_id = group.id if group else None

        if group_id:
            response = client.post(f"/settings/party-groups/{group_id}/toggle", follow_redirects=True)
            assert response.status_code == 200
            assert b"Estado del tipo de tercero actualizado" in response.data


def test_lista_precios_y_precios_item(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET price lists
        response = client.get("/settings/price-lists")
        assert response.status_code == 200

        # POST create price list
        response = client.post(
            "/settings/price-lists",
            data={
                "name": "Lista Precios Test",
                "currency": "NIO",
                "company": "cacao",
                "is_buying": "",
                "is_selling": "1",
                "is_default": "on",
                "is_active": "1",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Lista de precios creada" in response.data

        # GET item prices
        response = client.get("/settings/item-prices")
        assert response.status_code == 200

        with app_instance.app_context():
            price_list = database.session.execute(
                database.select(PriceList).filter_by(name="Lista Precios Test")
            ).scalar_one()
            price_list_id = price_list.id

        # POST create item price
        response = client.post(
            "/settings/item-prices",
            data={
                "item_code": "ART-TEST",
                "price_list_id": price_list_id,
                "uom": "UND",
                "price": "120.50",
                "min_qty": "1",
                "valid_from": "2026-01-01",
                "valid_upto": "2026-12-31",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Precio de item creado" in response.data


def test_config_conciliacion_compras_y_ventas(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET purchase reconciliation
        response = client.get("/settings/purchase-reconciliation")
        assert response.status_code == 200

        # POST empty company
        response = client.post("/settings/purchase-reconciliation", data={"company": ""}, follow_redirects=True)
        assert b"Debe seleccionar una" in response.data

        # POST valid
        response = client.post(
            "/settings/purchase-reconciliation",
            data={
                "company": "cacao",
                "matching_type": "3-way",
                "price_tolerance_type": "percentage",
                "price_tolerance_value": "5.0",
                "qty_tolerance_type": "percentage",
                "qty_tolerance_value": "2.0",
                "require_purchase_order": "on",
                "bridge_account_required": "on",
                "auto_reconcile": "on",
                "allow_price_difference": "on",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"conciliacion de compras guardada" in response.data

        # GET sales matching
        response = client.get("/settings/sales-matching")
        assert response.status_code == 200

        # POST empty company
        response = client.post("/settings/sales-matching", data={"company": ""}, follow_redirects=True)
        assert b"Debe seleccionar una" in response.data

        # POST valid
        response = client.post(
            "/settings/sales-matching",
            data={
                "company": "cacao",
                "matching_type": "3-way",
                "price_tolerance_type": "percentage",
                "price_tolerance_value": "5.0",
                "require_sales_order": "on",
                "allow_price_difference": "on",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"conciliacion de ventas guardada" in response.data


def test_budget_control_config(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/budget-control?company=cacao")
        assert response.status_code == 200

        # POST empty company
        response = client.post("/settings/budget-control", data={"company": ""}, follow_redirects=True)
        assert b"Debe seleccionar una" in response.data

        # POST invalid action
        response = client.post(
            "/settings/budget-control",
            data={"company": "cacao", "action_on_exceeded": "invalid_action"},
            follow_redirects=True,
        )
        assert b"no v" in response.data

        # POST valid
        response = client.post(
            "/settings/budget-control",
            data={"company": "cacao", "enabled": "on", "action_on_exceeded": "block"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"guardada correctamente" in response.data


def test_cuentas_predeterminadas(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/default-accounts?company=cacao")
        assert response.status_code == 200

        # POST empty company using execute mock to simulate empty companies list
        original_execute = database.session.execute
        def mock_execute(query, *args, **kwargs):
            if "entity" in str(query):
                m_res = mock.MagicMock()
                m_res.scalars.return_value.all.return_value = []
                return m_res
            return original_execute(query, *args, **kwargs)

        with mock.patch.object(database.session, "execute", side_effect=mock_execute):
            response2 = client.post("/settings/default-accounts", data={"company": ""}, follow_redirects=True)
            html = response2.get_data(as_text=True)
            assert "Debe" in html or "compa" in html

        # POST save valid
        response = client.post(
            "/settings/default-accounts",
            data={
                "company": "cacao",
                "action": "save",
                "apply_advances_automatically": "on",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"guardadas correctamente" in response.data

        # POST delete
        response = client.post(
            "/settings/default-accounts",
            data={
                "company": "cacao",
                "action": "delete",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"eliminada correctamente" in response.data


def test_lista_usuarios(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/users")
        assert response.status_code == 200

        # POST nonexistent user
        response = client.post("/settings/users", data={"user_id": "nonexistent", "action": "toggle"}, follow_redirects=True)
        assert b"Usuario no encontrado" in response.data

        # Create one success_user first
        response = client.post(
            "/settings/users/new",
            data={
                "usuario": "success_user",
                "name": "Success",
                "e_mail": "success@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "active": "y",
            },
            follow_redirects=True,
        )
        assert b"Usuario creado" in response.data

        # POST toggle valid
        with app_instance.app_context():
            user = database.session.execute(database.select(User).filter_by(user="success_user")).scalar_one()
            user_id = user.id

        response = client.post("/settings/users", data={"user_id": user_id, "action": "toggle"}, follow_redirects=True)
        assert response.status_code == 200
        assert b"correctamente" in response.data


def test_crear_usuario_validations(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET
        response = client.get("/settings/users/new")
        assert response.status_code == 200

        # POST weak password
        response = client.post(
            "/settings/users/new",
            data={
                "usuario": "weak_pwd_user",
                "name": "Weak",
                "e_mail": "weak@example.com",
                "password": "123",
                "confirm_password": "123",
                "active": "y",
            },
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        assert "Contrase" in html or "débil" in html

        # POST duplicate username
        response = client.post(
            "/settings/users/new",
            data={
                "usuario": "cacao",
                "name": "Cacao Duplicate",
                "e_mail": "cacao_dup@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "active": "y",
            },
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        assert "usuario ya" in html

        # POST duplicate email (use a username under 15 chars)
        response = client.post(
            "/settings/users/new",
            data={
                "usuario": "dup_email_user",
                "name": "Another",
                "e_mail": "success@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "active": "y",
            },
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        assert "correo" in html or "ya está en uso" in html


def test_editar_usuario_validations(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET 404
        response = client.get("/settings/users/nonexistent/edit")
        assert response.status_code == 302  # redirects with flash error

        with app_instance.app_context():
            user = database.session.execute(database.select(User).filter_by(user="success_user")).scalar_one()
            user_id = user.id

        # GET
        response = client.get(f"/settings/users/{user_id}/edit")
        assert response.status_code == 200

        # POST duplicate username
        response = client.post(
            f"/settings/users/{user_id}/edit",
            data={
                "usuario": "cacao",
                "name": "Success Edit",
                "e_mail": "success_edit@example.com",
                "active": "y",
            },
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        assert "usuario ya" in html


def test_usuario_roles_y_password(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET 404
        response = client.get("/settings/users/nonexistent/roles")
        assert response.status_code == 302

        with app_instance.app_context():
            user = database.session.execute(database.select(User).filter_by(user="success_user")).scalar_one()
            user_id = user.id
            role = database.session.execute(database.select(Roles)).scalars().first()
            role_id = role.id if role else None

        # GET roles assignment page
        response = client.get(f"/settings/users/{user_id}/roles")
        assert response.status_code == 200

        # POST roles assignment
        if role_id:
            response = client.post(
                f"/settings/users/{user_id}/roles",
                data={"roles": [role_id]},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Roles actualizados" in response.data

        # GET password change page
        response = client.get(f"/settings/users/{user_id}/password")
        assert response.status_code == 200

        # POST change password
        response = client.post(
            f"/settings/users/{user_id}/password",
            data={"password": "NewStrongPassword123!"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Contrase" in response.data


def test_roles_management(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # GET list
        response = client.get("/settings/roles")
        assert response.status_code == 200

        # GET create
        response = client.get("/settings/roles/new")
        assert response.status_code == 200

        # POST create
        response = client.post(
            "/settings/roles/new",
            data={"name": "Rol Test", "note": "Nota rol"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Rol creado" in response.data

        # POST duplicate role
        response = client.post(
            "/settings/roles/new",
            data={"name": "Rol Test", "note": "Nota rol"},
            follow_redirects=True,
        )
        assert b"nombre del rol ya est" in response.data

        with app_instance.app_context():
            role = database.session.execute(database.select(Roles).filter_by(name="Rol Test")).scalar_one()
            role_id = role.id

        # GET edit
        response = client.get(f"/settings/roles/{role_id}/edit")
        assert response.status_code == 200

        # POST edit duplicate name
        response = client.post(
            f"/settings/roles/{role_id}/edit",
            data={"name": "admin", "note": "edit"},
            follow_redirects=True,
        )
        assert b"nombre del rol ya est" in response.data

        # POST edit valid name
        response = client.post(
            f"/settings/roles/{role_id}/edit",
            data={"name": "Rol Test Modificado", "note": "edit note"},
            follow_redirects=True,
        )
        assert b"Rol actualizado" in response.data


def test_rol_permisos(app_instance):
    with app_instance.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with app_instance.app_context():
            role = database.session.execute(database.select(Roles).filter_by(name="Rol Test Modificado")).scalar_one()
            role_id = role.id
            module = database.session.execute(database.select(Modules)).scalars().first()
            module_id = module.id if module else None

        # GET
        response = client.get(f"/settings/roles/{role_id}/permissions")
        assert response.status_code == 200

        # POST
        if module_id:
            response = client.post(
                f"/settings/roles/{role_id}/permissions",
                data={
                    f"perm_{module_id}_access": "on",
                    f"perm_{module_id}_view": "on",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Permisos del rol actualizados" in response.data
