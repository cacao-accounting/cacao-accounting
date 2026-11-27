# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""#1854/#2304: duplicar StockEntry deja evento ?nico; bater?a aislada."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.audit_trail_service import format_document_timeline
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    AuditTrail,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    Item,
    Modules,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    UOM,
    User,
    database,
)
from cacao_accounting.inventario.routes import inventario_entrada_duplicar


@pytest.fixture
def isolated_app():
    app = create_app(
        {
            **configuracion,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="C?rdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao",
                tax_id="J0310000000000",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.commit()
        database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.commit()
        database.session.add(Item(code="ART01", name="Articulo 1", item_type="goods", default_uom="UND"))
        fy = FiscalYear(
            entity="cacao",
            name="FY2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fy)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                fiscal_year_id=fy.id,
                entity="cacao",
                name="2026-05",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                is_closed=False,
                enabled=True,
            )
        )
        admin = User(id="admin-1854", user="admin1854", name="Admin", active=True, classification="admin")
        admin.password = b"x"
        database.session.add(admin)
        database.session.add(Modules(module="inventory", default=True, enabled=True))
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _seed_entry(app) -> dict[str, str]:
    sufijo = uuid4().hex[:10]
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 15),
            document_no=f"SE-ORIGEN-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            remarks=f"Movimiento origen {sufijo}",
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code="ART01",
                qty=Decimal("2"),
                uom="UND",
                qty_in_base_uom=Decimal("2"),
                basic_rate=Decimal("10"),
                amount=Decimal("20"),
            )
        )
        database.session.commit()
        return {"entry": entry.id, "document_no": entry.document_no, "remarks": entry.remarks}


def _configurar_modo(app, monkeypatch, escritorio: bool) -> None:
    monkeypatch.setitem(app.config, "MODO_ESCRITORIO", escritorio)
    monkeypatch.setitem(app.config, "INTERNAL_CONTROLS_ENFORCE", not escritorio)


@pytest.mark.parametrize("escritorio", [True, False])
def test_duplicar_stock_entry_deja_un_created_visible_en_ambos_modos(isolated_app, monkeypatch, escritorio):
    origen = _seed_entry(isolated_app)
    _configurar_modo(isolated_app, monkeypatch, escritorio)

    from cacao_accounting.inventario import routes as inv_routes

    monkeypatch.setattr(inv_routes, "exige_acceso_compania", lambda *a, **k: None)
    with isolated_app.test_request_context(f"/inventory/stock-entry/{origen['entry']}/duplicate", method="POST"):
        login_user(database.session.get(User, "admin-1854"))
        respuesta = inventario_entrada_duplicar(origen["entry"])

    assert respuesta.status_code == 302
    with isolated_app.app_context():
        duplicados = (
            database.session.execute(
                select(StockEntry).where(
                    StockEntry.company == "cacao",
                    StockEntry.remarks == origen["remarks"],
                    StockEntry.id != origen["entry"],
                )
            )
            .scalars()
            .all()
        )
        assert len(duplicados) == 1
        duplicado = duplicados[0]
        assert duplicado.docstatus == 0

        eventos = (
            database.session.execute(
                select(AuditTrail).filter_by(document_type="stock_entry", document_id=duplicado.id, action="created")
            )
            .scalars()
            .all()
        )
        assert len(eventos) == 1
        assert eventos[0].actor_user_id is not None
        assert origen["document_no"] in (eventos[0].comment or "")

        lineas = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=duplicado.id)).scalars().all()
        assert len(lineas) == 1
        assert lineas[0].item_code == "ART01" and lineas[0].amount == Decimal("20.0000")

        assert (
            not database.session.execute(
                select(StockLedgerEntry.id).where(
                    StockLedgerEntry.voucher_type == "stock_entry", StockLedgerEntry.voucher_id == duplicado.id
                )
            )
            .scalars()
            .all()
        )
        assert (
            not database.session.execute(
                select(GLEntry.id).where(GLEntry.voucher_type == "stock_entry", GLEntry.voucher_id == duplicado.id)
            )
            .scalars()
            .all()
        )

        timeline = format_document_timeline("stock_entry", duplicado.id)
        creados = [fila["event"] for fila in timeline if fila["event"].action == "created"]
        assert len(creados) == 1
        assert origen["document_no"] in (creados[0].comment or "")


def test_duplicacion_fallida_no_persiste_documento_ni_eventos(isolated_app, monkeypatch):
    origen = _seed_entry(isolated_app)
    _configurar_modo(isolated_app, monkeypatch, escritorio=False)
    from cacao_accounting.inventario import routes as inv_routes

    monkeypatch.setattr(inv_routes, "exige_acceso_compania", lambda *a, **k: None)
    with isolated_app.test_request_context(f"/inventory/stock-entry/{origen['entry']}/duplicate", method="POST"):
        login_user(database.session.get(User, "admin-1854"))
        ids_antes = set(database.session.execute(select(StockEntry.id)).scalars().all())

        def _falla_commit(*args, **kwargs):
            raise RuntimeError("fallo de commit")

        monkeypatch.setattr(database.session, "commit", _falla_commit)
        with pytest.raises(RuntimeError, match="fallo de commit"):
            inventario_entrada_duplicar(origen["entry"])

        database.session.rollback()
        ids_despues = set(database.session.execute(select(StockEntry.id)).scalars().all())
        assert ids_despues == ids_antes
        eventos = (
            database.session.execute(
                select(AuditTrail.id).where(
                    AuditTrail.document_type == "stock_entry",
                    AuditTrail.action == "created",
                    AuditTrail.document_id.notin_(ids_antes),
                )
            )
            .scalars()
            .all()
        )
        assert eventos == []
