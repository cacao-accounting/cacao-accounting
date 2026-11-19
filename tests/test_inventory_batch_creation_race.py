# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2173: una carrera al crear lotes responde un conflicto controlado.

Dos solicitudes pueden validar el mismo par (item, lote) antes de insertar.
La restricción única evita el duplicado; la solicitud perdedora debe revertir
y devolver `InventoryServiceError`, no propagar `IntegrityError`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, UOM, database
from cacao_accounting.inventario import service
from cacao_accounting.inventario.service import BatchParams, InventoryServiceError, create_batch


def test_concurrent_batch_creation_returns_a_business_conflict(tmp_path, monkeypatch):
    """Solo un lote se crea y el perdedor no deja la sesión en error."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'batch-race.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code=f"ITEM-{suffix}",
                name="Artículo con lote",
                item_type="goods",
                is_stock_item=True,
                has_batch=True,
                default_uom="EA",
            )
        )
        database.session.commit()
        item_code = f"ITEM-{suffix}"
        database.session.remove()

    barrier = Barrier(2)
    validate_batch_params = service.validate_batch_params

    def synchronized_validation(params):
        item = validate_batch_params(params)
        barrier.wait(timeout=10)
        return item

    monkeypatch.setattr(service, "validate_batch_params", synchronized_validation)

    def create() -> str:
        with app.app_context():
            try:
                create_batch(BatchParams(item_code=item_code, batch_no="LOTE-RACE"))
                database.session.commit()
                return "created"
            except InventoryServiceError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))

    assert sorted(results) == ["created", "rejected"]

    with app.app_context():
        assert (
            database.session.execute(
                database.select(database.func.count()).select_from(service.Batch).filter_by(item_code=item_code)
            ).scalar_one()
            == 1
        )
