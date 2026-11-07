# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance de compañía en terceros y transacciones bancarias.

Escenarios de negocio (#1525 y #1320, consolidación #1649): los tercero
son registros globales y su aislamiento vive en los vínculos
``CompanyParty``; los listados solo muestran los vinculados a compañías
del módulo autorizado para el usuario, el detalle exige un vínculo
autorizado, y el listado de transacciones bancarias deriva su alcance de
la compañía de la cuenta bancaria (el modelo no tiene columna company).
"""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CONTRASENA = "terceros-scope-2026"


@pytest.fixture
def terceros_cloud():
    """Cloud con dos compañías, tercero en ambas y cuentas bancarias con movimientos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import (
            Bank,
            BankAccount,
            BankTransaction,
            CompanyParty,
            Entity,
            Modules,
            Party,
            User,
            UserCompanyAccess,
        )

        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="secreta",
                    name="Compañía Secreta",
                    company_name="Compañía Secreta SA",
                    tax_id="J0009",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="vendedor",
                    user="vendedor",
                    name="Vendedor Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="comprador",
                    user="comprador",
                    name="Comprador Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="tesorero",
                    user="tesorero",
                    name="Tesorero Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="sinacceso",
                    user="sinacceso",
                    name="Usuario Sin Acceso",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="vendedor", company_code="cacao"),
                UserCompanyAccess(user_id="comprador", company_code="cacao"),
                UserCompanyAccess(user_id="tesorero", company_code="cacao"),
            ]
        )
        database.session.commit()
        cliente_cacao = Party(
            code="CL-CA",
            is_customer=True,
            name="Cliente Visible",
            comercial_name="Cliente Visible SA",
            tax_id="CL-CA-1",
            is_active=True,
        )
        cliente_secreto = Party(
            code="CL-SE",
            is_customer=True,
            name="Cliente Oculto",
            comercial_name="Cliente Oculto SA",
            tax_id="CL-SE-9",
            is_active=True,
        )
        proveedor_cacao = Party(
            code="PR-CA",
            is_supplier=True,
            name="Proveedor Visible",
            tax_id="PR-CA-1",
            is_active=True,
        )
        proveedor_secreto = Party(
            code="PR-SE",
            is_supplier=True,
            name="Proveedor Oculto",
            tax_id="PR-SE-9",
            is_active=True,
        )
        database.session.add_all([cliente_cacao, cliente_secreto, proveedor_cacao, proveedor_secreto])
        database.session.commit()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente_cacao.id, is_active=True),
                CompanyParty(company="secreta", party_id=cliente_secreto.id, is_active=True),
                CompanyParty(company="cacao", party_id=proveedor_cacao.id, is_active=True),
                CompanyParty(company="secreta", party_id=proveedor_secreto.id, is_active=True),
            ]
        )
        banco = Bank(name="Banco Nacional de Desarrollo", swift_code="BNDENI2N", is_active=True)
        database.session.add(banco)
        database.session.commit()
        cuenta_cacao = BankAccount(company="cacao", bank_id=banco.id, account_name="Cuenta Cacao", account_no="CA-1")
        cuenta_secreta = BankAccount(company="secreta", bank_id=banco.id, account_name="Cuenta Secreta", account_no="SE-1")
        database.session.add_all([cuenta_cacao, cuenta_secreta])
        database.session.commit()
        database.session.add_all(
            [
                BankTransaction(
                    bank_account_id=cuenta_cacao.id,
                    identity_key="MOV-CA-1",
                    posting_date=date(2026, 10, 1),
                    deposit=Decimal("500"),
                    description="Depósito en cuenta cacao",
                ),
                BankTransaction(
                    bank_account_id=cuenta_secreta.id,
                    identity_key="MOV-SE-1",
                    posting_date=date(2026, 10, 1),
                    withdrawal=Decimal("300"),
                    description="Retiro en cuenta secreta",
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        for usuario, rol in (
            ("vendedor", "sales_auxiliar"),
            ("comprador", "purchasing_auxiliar"),
            ("tesorero", "auxiliar_of_treasury"),
        ):
            asigna_rol_a_usuario(usuario, rol)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _como(client, usuario: str) -> None:
    assert client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True).status_code == 200


def _party_id(application, name: str) -> str:
    with application.app_context():
        from cacao_accounting.database import Party, database

        registro = database.session.execute(database.select(Party).filter_by(name=name)).scalar_one()
        return registro.id


def test_listado_de_clientes_scoped_por_companyparty(terceros_cloud):
    """#1525: el vendedor solo ve los clientes vinculados a sus compañías."""
    application = terceros_cloud
    client = application.test_client()
    _como(client, "vendedor")
    response = client.get("/sales/customer/list")
    texto = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Cliente Visible" in texto
    assert "Cliente Oculto" not in texto


def test_listado_de_proveedores_scoped_por_companyparty(terceros_cloud):
    """#1525: el comprador solo ve proveedores de sus compañías."""
    application = terceros_cloud
    client = application.test_client()
    _como(client, "comprador")
    response = client.get("/buying/supplier/list")
    texto = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Proveedor Visible" in texto
    assert "Proveedor Oculto" not in texto


def test_detalle_rechaza_terceros_sin_vinculo_autorizado(terceros_cloud):
    """El detalle del cliente oculto responde 403 para el vendedor."""
    application = terceros_cloud
    id_oculto = _party_id(application, "Cliente Oculto")
    client = application.test_client()
    _como(client, "vendedor")
    assert client.get(f"/sales/customer/{id_oculto}").status_code == 403


def test_detalle_muestra_terceros_con_vinculo_autorizado(terceros_cloud):
    """Control positivo: el detalle visible responde 200."""
    application = terceros_cloud
    id_visible = _party_id(application, "Cliente Visible")
    client = application.test_client()
    _como(client, "vendedor")
    assert client.get(f"/sales/customer/{id_visible}").status_code == 200


def test_usuario_sin_companias_no_puede_enumerar_terceros(terceros_cloud):
    """#1525: sin vínculos por compañía el listado queda vacío, no global."""
    application = terceros_cloud
    client = application.test_client()
    _como(client, "sinacceso")
    response = client.get("/sales/customer/list")
    texto = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Cliente Visible" not in texto
    assert "Cliente Oculto" not in texto


def test_transacciones_bancarias_scoped_por_cuenta(terceros_cloud):
    """#1320: el listado deriva la compañía de la cuenta bancaria."""
    application = terceros_cloud
    client = application.test_client()
    _como(client, "tesorero")
    response = client.get("/cash_management/bank-transaction/list")
    texto = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Depósito en cuenta cacao" in texto
    assert "Retiro en cuenta secreta" not in texto


def test_transacciones_bancarias_rechaza_compania_ajena(terceros_cloud):
    """El filtro Company=? sobre otra compañía responde 403."""
    application = terceros_cloud
    client = application.test_client()
    _como(client, "tesorero")
    assert client.get("/cash_management/bank-transaction/list?company=secreta").status_code == 403
