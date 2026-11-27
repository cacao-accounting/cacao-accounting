# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1877: el allowance de líneas solo existe dentro del servicio de posting.

Una transición ORM ``draft -> posted`` no debe habilitar por sí sola la
reescritura de líneas. La autorización se abre únicamente mientras
``submit_document()`` ejecuta su unidad de trabajo, y se limpia al terminar
o revertir. La prueba usa el servicio real y sustituye solo el escritor GL,
cuyo detalle contable no es el contrato de este issue.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.posting_service import submit_document
from cacao_accounting.database import Currency, Entity, Item, StockEntry, StockEntryItem, UOM, database


@pytest.fixture
def app_controles():
    """Aplicación Cloud con controles internos activos (#1877)."""
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
            "SECRET_KEY": "test-worker-secret",
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
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
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _seed_draft(app) -> tuple[str, str]:
    """Crea un movimiento en borrador con una línea editable por el posting."""
    with app.app_context():
        database.session.add(UOM(code="UNI-X", name="Unidad X"))
        database.session.flush()
        database.session.add(
            Item(code="ART-X", name="Articulo X", item_type="goods", is_stock_item=False, default_uom="UNI-X")
        )
        database.session.flush()
        entry = StockEntry(company="cacao", purpose="stock_reconciliation", posting_date=date(2026, 5, 15), docstatus=0)
        database.session.add(entry)
        database.session.flush()
        item = StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ART-X",
            qty=Decimal("10"),
            uom="UNI-X",
            qty_in_base_uom=Decimal("10"),
        )
        database.session.add(item)
        database.session.commit()
        return entry.id, item.id


def _posting_writer(document, ledger_code=None):
    """Simula la escritura interna de snapshots que realiza el posting real."""
    del ledger_code
    item = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=document.id)).scalar_one()
    item.current_qty = Decimal("10")
    item.counted_qty = Decimal("8")
    item.qty = Decimal("2")
    database.session.flush()
    return []


def test_transicion_orm_sin_posting_no_autoriza_editar_lineas(app_controles):
    """Un draft->posted directo no obtiene el allowance del servicio."""
    entry_id, item_id = _seed_draft(app_controles)

    with app_controles.app_context():
        entry = database.session.get(StockEntry, entry_id)
        item = database.session.get(StockEntryItem, item_id)
        entry.docstatus = 1
        database.session.flush()

        item.current_qty = Decimal("5")
        with pytest.raises(ValueError, match="inmutables"):
            database.session.flush()
        database.session.rollback()


def test_submit_document_permite_sus_escrituras_y_bloquea_las_externas(app_controles, monkeypatch):
    """El posting real escribe sus líneas; después del commit quedan bloqueadas."""
    entry_id, item_id = _seed_draft(app_controles)
    monkeypatch.setattr(posting_service, "post_document_to_gl", _posting_writer)

    with app_controles.app_context():
        entry = database.session.get(StockEntry, entry_id)
        assert submit_document(entry) == []
        assert entry.docstatus == 1
        database.session.commit()

        item = database.session.get(StockEntryItem, item_id)
        assert item.current_qty == Decimal("10")
        assert item.counted_qty == Decimal("8")
        item.current_qty = Decimal("5")
        with pytest.raises(ValueError, match="inmutables"):
            database.session.flush()
        database.session.rollback()


def test_fallo_del_posting_revierte_estado_y_limpia_el_allowance(app_controles, monkeypatch):
    """Si el posting falla, no queda docstatus posteado ni permiso residual."""
    entry_id, item_id = _seed_draft(app_controles)

    def _falla(document, ledger_code=None):
        del ledger_code
        item = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=document.id)).scalar_one()
        item.current_qty = Decimal("99")
        database.session.flush()
        raise RuntimeError("fallo de posting")

    monkeypatch.setattr(posting_service, "post_document_to_gl", _falla)

    with app_controles.app_context():
        entry = database.session.get(StockEntry, entry_id)
        with pytest.raises(RuntimeError, match="fallo de posting"):
            submit_document(entry)
        database.session.rollback()

    with app_controles.app_context():
        entry = database.session.get(StockEntry, entry_id)
        item = database.session.get(StockEntryItem, item_id)
        assert entry.docstatus == 0
        assert item.current_qty != Decimal("99")

        monkeypatch.setattr(posting_service, "post_document_to_gl", _posting_writer)
        assert submit_document(entry) == []
        assert entry.docstatus == 1


def test_allowance_no_sobrevive_al_retorno_del_posting(app_controles, monkeypatch):
    """Fuera de `authorized_posting()` la l??nea queda protegida aunque la transacci??n siga abierta (#1877)."""
    entry_id, item_id = _seed_draft(app_controles)
    monkeypatch.setattr(posting_service, "post_document_to_gl", _posting_writer)

    with app_controles.app_context():
        entry = database.session.get(StockEntry, entry_id)
        assert submit_document(entry) == []
        item = database.session.get(StockEntryItem, item_id)
        item.current_qty = Decimal("1")
        with pytest.raises(ValueError, match="inmutables"):
            database.session.flush()
        database.session.rollback()
