# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Impresión de portal: alcance de compañía sobre el tercero compartido.

Escenario de negocio (#1562, consolidación #1649): un usuario de portal
que comparte el mismo tercero con varias compañías solo puede imprimir
documentos de SU compañía; pedir la impresión con la compañía ajena
debe rechazarse aunque el documento pertenezca a su tercero.
"""

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database
from cacao_accounting.printing.service import PrintPermissionError, PrintService


@pytest.fixture
def portal_compartido():
    """Aplicación con factura compartida entre dos compañías del mismo tercero."""
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
        from cacao_accounting.database import Entity, SalesInvoice, User

        database.session.add_all(
            [
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
                SalesInvoice(
                    company="cacao",
                    document_no="INV-CA-1",
                    posting_date=date(2026, 10, 1),
                    docstatus=1,
                    customer_id="SHARED-PARTY",
                    customer_name="Cliente compartido",
                    grand_total=100,
                    total=100,
                ),
                SalesInvoice(
                    company="secreta",
                    document_no="INV-SE-1",
                    posting_date=date(2026, 10, 1),
                    docstatus=1,
                    customer_id="SHARED-PARTY",
                    customer_name="Cliente compartido",
                    grand_total=999,
                    total=999,
                ),
                User(
                    id="portal",
                    user="portal",
                    name="Portal Cliente",
                    password=b"x",
                    classification="customer",
                    party_id="SHARED-PARTY",
                    company="cacao",
                    active=True,
                ),
            ]
        )
        database.session.commit()
        usuario = database.session.execute(database.select(User).filter_by(user="portal")).scalar_one()
    yield application, usuario
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _factura(application, company: str):
    with application.app_context():
        from cacao_accounting.database import SalesInvoice, database

        registro = database.session.execute(database.select(SalesInvoice).filter_by(company=company)).scalar_one()
        return registro


def test_portal_rechaza_la_impresion_de_la_compania_ajena(portal_compartido):
    """El repro del issue: tercero compartido no concede la compañía ajena."""
    application, usuario = portal_compartido
    factura = _factura(application, "secreta")
    with application.app_context():
        definicion = {"permission": "sales.print"}
        with pytest.raises(PrintPermissionError) as excinfo:
            PrintService()._authorize_document(
                "sales_invoice",
                factura.id,
                usuario,
                "secreta",
                definicion,
            )
    assert "company" in str(excinfo.value).lower()


def test_portal_imprime_su_propia_compania(portal_compartido):
    """Control positivo: su propia compañía factura normalmente."""
    application, usuario = portal_compartido
    factura = _factura(application, "cacao")
    with application.app_context():
        PrintService()._authorize_document(
            "sales_invoice",
            factura.id,
            usuario,
            "cacao",
            {"permission": "sales.print"},
        )


def test_portal_rechaza_sin_compania(portal_compartido):
    """Un usuario de portal sin compañía no autoriza impresión alguna."""
    application, usuario = portal_compartido
    factura = _factura(application, "cacao")

    with application.app_context():
        from cacao_accounting.database import User

        usuario_sin = database.session.execute(database.select(User).filter_by(user="portal")).scalar_one()
        usuario_sin.company = None
        database.session.commit()
        with pytest.raises(PrintPermissionError):
            PrintService()._authorize_document(
                "sales_invoice",
                factura.id,
                usuario_sin,
                "cacao",
                {"permission": "sales.print"},
            )
