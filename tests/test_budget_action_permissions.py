# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1781: cada acción de presupuesto exige su propio permiso.

El guard de compañía resolvía `crear` para cualquier POST sin `/edit`. La
regresión cubre las acciones aprobar, cerrar, importar, eliminar línea y
editar con usuarios segregados, y conserva un control positivo de aprobación.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import render_template

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    Budget,
    BudgetLine,
    CostCenter,
    Currency,
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

PREFIJO = "/accounting/presupuestos"


@pytest.fixture
def escenario_presupuesto():
    """App con presupuesto en borrador, línea y usuarios por acción."""
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
    suffix = uuid4().hex[:6].upper()
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        modulo = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one()
        book = Book(code="DEFAULT_BOOK", name="Principal", entity="cacao", currency="NIO", status="activo", is_primary=True)
        fiscal = FiscalYear(
            id=f"FY-{suffix}",
            entity="cacao",
            name=suffix,
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        period = AccountingPeriod(
            id=f"P-{suffix}",
            entity="cacao",
            fiscal_year_id=f"FY-{suffix}",
            name="Mayo",
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
            enabled=True,
            is_closed=False,
        )
        centro = CostCenter(entity="cacao", code=f"CC{suffix}", name="Centro", active=True, enabled=True)
        cuenta = Accounts(
            entity="cacao",
            code=f"5{suffix}",
            name="Gasto",
            classification="expense",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([book, fiscal, centro, cuenta])
        database.session.flush()
        database.session.add(period)
        database.session.flush()

        def crear_usuario(nombre: str, **permisos: bool) -> str:
            user_id = f"{nombre}-{suffix}"
            role = Roles(name=f"rol-{nombre}-{suffix}", note=nombre)
            database.session.add_all(
                [
                    User(id=user_id, user=user_id, name=nombre, password=b"unused", active=True, company="cacao"),
                    role,
                ]
            )
            database.session.flush()
            database.session.add_all(
                [
                    RolesAccess(rol_id=role.id, module_id=modulo.id, **permisos),
                    RolesUser(user_id=user_id, role_id=role.id, active=True),
                    UserCompanyAccess(user_id=user_id, company_code="cacao"),
                ]
            )
            return user_id

        ids = {
            "lector": crear_usuario("lector", access=True, view=True),
            "creador": crear_usuario("creador", access=True, view=True, create=True),
            "aprobador": crear_usuario("aprobador", access=True, view=True, approve=True),
            "cerrador": crear_usuario("cerrador", access=True, view=True, close=True),
            "importador": crear_usuario("importador", access=True, view=True, import_=True),
            "eliminador": crear_usuario("eliminador", access=True, view=True, delete=True),
            "book": book.id,
            "fiscal": fiscal.id,
            "period": period.id,
            "centro": centro.id,
            "cuenta": cuenta.id,
            "suffix": suffix,
        }
        database.session.commit()
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _crear_presupuesto(app, ids: dict, estado: str = "draft") -> tuple[str, str]:
    """Crea un presupuesto con una línea y devuelve (budget_id, line_id)."""
    with app.app_context():
        budget = Budget(
            company="cacao",
            ledger_id=ids["book"],
            fiscal_year_id=ids["fiscal"],
            budget_code=f"B-{uuid4().hex[:6]}",
            name="Presupuesto de prueba",
            currency_id="NIO",
            status=estado,
            approved_by=None,
            approved_at=datetime(2026, 5, 1, tzinfo=timezone.utc) if estado == "approved" else None,
        )
        database.session.add(budget)
        database.session.flush()
        line = BudgetLine(
            budget_id=budget.id,
            account_id=ids["cuenta"],
            cost_center_id=ids["centro"],
            period_id=ids["period"],
            amount=Decimal("100"),
        )
        database.session.add(line)
        database.session.commit()
        return budget.id, line.id


def _login(application, user_id: str):
    """Cliente autenticado para el usuario."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


@pytest.mark.parametrize("accion", ["approve", "close", "import", "line_delete"])
def test_lector_no_ejecuta_acciones_restringidas(escenario_presupuesto, accion):
    """Un usuario de solo lectura recibe 403 en cada acción de escritura."""
    application, ids = escenario_presupuesto
    budget_id, line_id = _crear_presupuesto(application, ids)
    client = _login(application, ids["lector"])
    ruta = {
        "approve": f"{PREFIJO}/{budget_id}/approve",
        "close": f"{PREFIJO}/{budget_id}/close",
        "import": f"{PREFIJO}/{budget_id}/import",
        "line_delete": f"{PREFIJO}/line/{line_id}/delete",
    }[accion]

    assert client.post(ruta).status_code == 403


def test_lector_no_accede_a_editar(escenario_presupuesto):
    """La edición exige `editar`, no solo consultar."""
    application, ids = escenario_presupuesto
    budget_id, _ = _crear_presupuesto(application, ids)
    client = _login(application, ids["lector"])

    assert client.get(f"{PREFIJO}/{budget_id}/edit").status_code == 403


def test_creador_no_puede_aprobar(escenario_presupuesto):
    """`crear` no sustituye `autorizar`: el presupuesto permanece en borrador."""
    application, ids = escenario_presupuesto
    budget_id, _ = _crear_presupuesto(application, ids)
    client = _login(application, ids["creador"])

    assert client.post(f"{PREFIJO}/{budget_id}/approve").status_code == 403
    with application.app_context():
        assert database.session.get(Budget, budget_id).status == "draft"


def test_aprobador_aprueba_el_presupuesto(escenario_presupuesto):
    """Control positivo: `autorizar` ejecuta la transición."""
    application, ids = escenario_presupuesto
    budget_id, _ = _crear_presupuesto(application, ids)
    client = _login(application, ids["aprobador"])

    response = client.post(f"{PREFIJO}/{budget_id}/approve")

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(Budget, budget_id).status == "approved"


def test_lista_presupuestos_pagina_y_busqueda(escenario_presupuesto):
    """La segunda página renderiza enlaces válidos y conserva la búsqueda."""
    application, ids = escenario_presupuesto
    for _ in range(11):
        _crear_presupuesto(application, ids)
    client = _login(application, ids["lector"])

    response = client.get(f"{PREFIJO}/list?page=2&search=Presupuesto+de+prueba")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="/accounting/presupuestos/list?page=1&amp;search=Presupuesto+de+prueba"' in body
    assert 'href="/accounting/presupuestos/list?page=2&amp;search=Presupuesto+de+prueba"' in body


def test_vistas_presupuesto_formatean_montos_con_filtro_registrado(escenario_presupuesto):
    """Detalle y previsualización de importación renderizan importes monetarios."""
    application, ids = escenario_presupuesto
    budget_id, _ = _crear_presupuesto(application, ids)
    client = _login(application, ids["lector"])

    detail = client.get(f"{PREFIJO}/{budget_id}")

    assert detail.status_code == 200
    assert "100.00" in detail.get_data(as_text=True)

    with application.app_context():
        budget = database.session.get(Budget, budget_id)
        assert budget is not None
        row = SimpleNamespace(
            row_index=1,
            account_id=ids["cuenta"],
            cost_center_id=ids["centro"],
            period_id=ids["period"],
            business_unit_id=None,
            project_id=None,
            amount=Decimal("1250.5"),
        )
        with application.test_request_context(f"{PREFIJO}/{budget_id}/import"):
            preview = render_template(
                "contabilidad/presupuestos/import.html",
                budget=budget,
                columns=[],
                staged_lines=[row],
                import_id="import-preview",
                titulo="Importar",
            )

    assert "1,250.50" in preview


def test_cerrador_cierra_sin_permiso_crear(escenario_presupuesto):
    """#1781: `cerrar` basta para la transición y el presupuesto queda cerrado."""
    application, ids = escenario_presupuesto
    budget_id, _ = _crear_presupuesto(application, ids, estado="approved")
    client = _login(application, ids["cerrador"])

    response = client.post(f"{PREFIJO}/{budget_id}/close")

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(Budget, budget_id).status == "closed"


def test_importador_importa_sin_permiso_crear(escenario_presupuesto):
    """#1781: `importar` basta y la importación persiste la línea del lote."""
    from cacao_accounting.contabilidad.budget_import_service import BudgetImportService

    application, ids = escenario_presupuesto
    budget_id, _ = _crear_presupuesto(application, ids)
    with application.app_context():
        database.session.execute(database.delete(BudgetLine).where(BudgetLine.budget_id == budget_id))
        database.session.commit()
        cuenta = database.session.get(Accounts, ids["cuenta"])
        centro = database.session.get(CostCenter, ids["centro"])
        csv_content = ("Cuenta,Centro de Costo,Mayo,Total\n" f"{cuenta.code},{centro.code},250.00,250.00\n").encode("utf-8")
        lote = BudgetImportService().validate_import(budget_id, "gastos.csv", csv_content, user_id=ids["importador"])
        lote_id = lote.id
        antes = database.session.execute(
            database.select(database.func.count()).select_from(BudgetLine).where(BudgetLine.budget_id == budget_id)
        ).scalar_one()

    client = _login(application, ids["importador"])
    response = client.post(f"{PREFIJO}/{budget_id}/import", data={"import_id": lote_id})

    assert response.status_code == 302
    with application.app_context():
        despues = database.session.execute(
            database.select(database.func.count()).select_from(BudgetLine).where(BudgetLine.budget_id == budget_id)
        ).scalar_one()
        assert despues == antes + 1


def test_eliminador_borra_linea_sin_permiso_crear(escenario_presupuesto):
    """#1781: `eliminar` basta para borrar una línea del presupuesto."""
    application, ids = escenario_presupuesto
    _, line_id = _crear_presupuesto(application, ids)
    client = _login(application, ids["eliminador"])

    response = client.post(f"{PREFIJO}/line/{line_id}/delete")

    assert response.status_code != 403
    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(BudgetLine, line_id) is None
