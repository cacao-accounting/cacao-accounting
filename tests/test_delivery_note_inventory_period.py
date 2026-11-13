# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El listado de remisiones ofrece período a usuarios Inventory-only.

Escenario de negocio (issue #2051): el listado autoriza Sales o Inventory, pero
el selector de período se construía solo con el primer módulo.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    Currency,
    DeliveryNote,
    Entity,
    FiscalYear,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Book(code="LIBRO", name="Libro principal", entity="cacao", currency="NIO", status="activo"),
                FiscalYear(
                    entity="cacao",
                    name="2026",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
                User(
                    id="inv",
                    user="inv",
                    name="Inventario",
                    password=b"x",
                    active=True,
                    classification="user",
                ),
                DeliveryNote(
                    company="cacao",
                    posting_date=date(2026, 10, 15),
                    docstatus=1,
                    document_no="DN-OCT",
                    customer_name="Cliente",
                    transaction_currency="NIO",
                ),
                DeliveryNote(
                    company="cacao",
                    posting_date=date(2026, 9, 15),
                    docstatus=1,
                    document_no="DN-SEP",
                    customer_name="Cliente",
                    transaction_currency="NIO",
                ),
            ]
        )
        database.session.flush()
        anio = database.session.execute(database.select(FiscalYear)).scalar_one()
        database.session.add_all(
            [
                AccountingPeriod(
                    entity="cacao",
                    fiscal_year_id=anio.id,
                    name="09-2026",
                    status="activo",
                    enabled=True,
                    start=date(2026, 9, 1),
                    end=date(2026, 9, 30),
                ),
                AccountingPeriod(
                    entity="cacao",
                    fiscal_year_id=anio.id,
                    name="10-2026",
                    status="activo",
                    enabled=True,
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                ),
            ]
        )
        database.session.flush()
        modulo_inventario = database.session.execute(database.select(Modules).filter_by(module="inventory")).scalar_one()
        rol = Roles(name="inventario-view", note="Consulta inventario")
        database.session.add(rol)
        database.session.flush()
        database.session.add(RolesAccess(rol_id=rol.id, module_id=modulo_inventario.id, view=True, edit=False))
        database.session.add(RolesUser(user_id="inv", role_id=rol.id, active=True))
        database.session.add(UserCompanyAccess(user_id="inv", company_code="cacao"))
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "inv"
        session["_fresh"] = True
    return client


def test_inventory_only_puede_elegir_periodo():
    """#2051: el picker se construye con ambos módulos autorizados."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/sales/delivery-note/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'id="list-company"' in html
        assert 'id="list-period-from"' in html
        assert 'id="list-period-to"' in html
        assert "DN-OCT" in html or "No se encontraron" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
