# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Tests para issue #773: maestro de lotes y trazabilidad de lote en reportes.

Valida:
1. Servicio de creación de lotes con validaciones contra el maestro de items.
2. Rutas web del maestro de lotes (listar, crear y ver con saldo por bodega).
3. Kardex con columnas de lote y número de serie.
4. Reporte de lotes con saldo por lote y bodega.
5. Importador resuelve el número de lote del archivo al registro del maestro.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    Entity,
    Item,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    BatchParams,
    batch_balance_rows,
    create_batch,
    validate_batch_params,
)


@pytest.fixture()
def app_ctx():
    """App de pruebas con datos semilla para el maestro de lotes."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        _seed_test_data()
        yield app
        database.session.remove()
        database.drop_all()


def _seed_test_data():
    """Crea catalogos base: items controlados, bodegas y un lote con movimientos."""
    company = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one_or_none()
    if company is None:
        company = Entity(code="cacao", name="Cacao Corp", company_name="Cacao Corp", tax_id="J031-773", currency="NIO")
        database.session.add(company)

    uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none()
    if uom is None:
        database.session.add(UOM(code="UND", name="Unidad"))

    database.session.add_all(
        [
            Item(
                code="ITEM-LOT",
                name="Item con lote",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                has_batch=True,
            ),
            Item(
                code="ITEM-EXP",
                name="Item con vencimiento",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                has_batch=True,
                has_expiry_date=True,
            ),
            Item(
                code="ITEM-NB",
                name="Item sin control de lote",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
            ),
            Item(
                code="ITEM-SVC",
                name="Servicio",
                item_type="service",
                is_stock_item=False,
                default_uom="UND",
            ),
            Warehouse(code="WH-A", name="Bodega A", company="cacao", is_active=True),
            Warehouse(code="WH-B", name="Bodega B", company="cacao", is_active=True),
        ]
    )
    database.session.flush()

    lot_a = Batch(item_code="ITEM-LOT", batch_no="LOT-A", is_active=True)
    lot_empty = Batch(item_code="ITEM-LOT", batch_no="LOT-EMPTY", is_active=True)
    database.session.add_all([lot_a, lot_empty])
    database.session.flush()

    # Saldo por bodega: +3 en WH-A y +2 en WH-B.
    database.session.add_all(
        [
            _sle(lot_a.id, "WH-A", Decimal("3"), "seed", "sle-a1"),
            _sle(lot_a.id, "WH-B", Decimal("2"), "seed", "sle-b1"),
        ]
    )

    # Par de anulación: original cancelado + reversa del mismo voucher.
    cancelled = _sle(lot_a.id, "WH-A", Decimal("5"), "seed", "sle-cancel", is_cancelled=True)
    database.session.add(cancelled)
    database.session.flush()
    database.session.add(
        _sle(lot_a.id, "WH-A", Decimal("-5"), "seed", "sle-cancel", is_reversal=True, reversal_of=cancelled.id)
    )

    database.session.commit()


def _sle(batch_id, warehouse, qty_change, voucher_type, voucher_id, is_cancelled=False, is_reversal=False, reversal_of=None):
    """Crea una fila del ledger físico asociada a un lote."""
    return StockLedgerEntry(
        posting_date=date.today(),
        item_code="ITEM-LOT",
        warehouse=warehouse,
        company="cacao",
        batch_id=batch_id,
        qty_change=qty_change,
        qty_after_transaction=qty_change,
        valuation_rate=Decimal("1"),
        stock_value_difference=qty_change,
        stock_value=qty_change,
        voucher_type=voucher_type,
        voucher_id=voucher_id,
        is_cancelled=is_cancelled,
        is_reversal=is_reversal,
        reversal_of=reversal_of,
    )


def _login(client):
    return client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)


# <------------------------------------------------------------------------------------------> #
# Servicio: creación y validación de lotes
# <------------------------------------------------------------------------------------------> #


def test_create_batch_persists_trimmed_fields(app_ctx):
    """El lote se crea con el número normalizado y las fechas declaradas."""
    expiry = date.today() + timedelta(days=90)
    batch = create_batch(
        BatchParams(item_code="ITEM-LOT", batch_no="  LOT-NEW  ", expiry_date=expiry, description="Primer lote")
    )
    database.session.commit()

    stored = database.session.get(Batch, batch.id)
    assert stored.batch_no == "LOT-NEW"
    assert stored.item_code == "ITEM-LOT"
    assert stored.expiry_date == expiry
    assert stored.is_active is True


def test_create_batch_rejects_duplicate_item_and_batch_no(app_ctx):
    """La combinación item + número de lote es única."""
    create_batch(BatchParams(item_code="ITEM-LOT", batch_no="LOT-DUP"))
    database.session.commit()

    with pytest.raises(InventoryServiceError, match="ya existe"):
        create_batch(BatchParams(item_code="ITEM-LOT", batch_no="LOT-DUP"))


def test_create_batch_rejects_item_without_batch_control(app_ctx):
    """Un item sin control de lote no admite lotes."""
    with pytest.raises(InventoryServiceError, match="control de lote"):
        create_batch(BatchParams(item_code="ITEM-NB", batch_no="LOT-X"))


def test_create_batch_rejects_service_item(app_ctx):
    """Un servicio no es inventariable y no admite lotes."""
    with pytest.raises(InventoryServiceError, match="control de lote"):
        create_batch(BatchParams(item_code="ITEM-SVC", batch_no="LOT-X"))


def test_create_batch_rejects_unknown_item(app_ctx):
    """El item debe existir en el maestro."""
    with pytest.raises(InventoryServiceError, match="no existe"):
        create_batch(BatchParams(item_code="ITEM-404", batch_no="LOT-X"))


def test_create_batch_requires_expiry_when_item_controls_expiry(app_ctx):
    """Los items con control de vencimiento exigen fecha de vencimiento en el lote."""
    with pytest.raises(InventoryServiceError, match="vencimiento"):
        create_batch(BatchParams(item_code="ITEM-EXP", batch_no="LOT-EXP"))


def test_create_batch_rejects_expiry_before_manufacturing(app_ctx):
    """La fecha de vencimiento no puede ser anterior a la de fabricación."""
    with pytest.raises(InventoryServiceError, match="fabricación"):
        create_batch(
            BatchParams(
                item_code="ITEM-EXP",
                batch_no="LOT-EXP",
                expiry_date=date.today(),
                manufacturing_date=date.today() + timedelta(days=1),
            )
        )


def test_validate_batch_params_rejects_empty_batch_no(app_ctx):
    """El número de lote es obligatorio."""
    with pytest.raises(InventoryServiceError, match="obligatorio"):
        validate_batch_params(BatchParams(item_code="ITEM-LOT", batch_no="   "))


def test_batch_balance_rows_splits_warehouses_and_nets_cancellations(app_ctx):
    """El saldo por bodega excluye los pares de anulación del mismo período."""
    lot_a = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalar_one()

    balances = batch_balance_rows(lot_a.id)
    by_warehouse = {row["warehouse"]: row for row in balances}

    assert by_warehouse["WH-A"]["balance_qty"] == Decimal("3")
    assert by_warehouse["WH-B"]["balance_qty"] == Decimal("2")
    assert by_warehouse["WH-A"]["stock_value"] == Decimal("3")


def test_batch_balance_rows_empty_for_batch_without_movements(app_ctx):
    """Un lote sin movimientos no reporta saldos."""
    lot_empty = database.session.execute(
        database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-EMPTY")
    ).scalar_one()

    assert batch_balance_rows(lot_empty.id) == []


# <------------------------------------------------------------------------------------------> #
# Rutas web del maestro de lotes
# <------------------------------------------------------------------------------------------> #


def test_batch_list_route_renders(app_ctx):
    """El listado de lotes renderiza y muestra los lotes existentes."""
    with app_ctx.test_client() as client:
        _login(client)
        response = client.get("/inventory/batch/list")

        assert response.status_code == 200
        assert b"LOT-A" in response.data


def test_batch_new_route_creates_batch_and_redirects_to_detail(app_ctx):
    """El POST del formulario crea el lote y redirige al detalle."""
    with app_ctx.test_client() as client:
        _login(client)
        response = client.post(
            "/inventory/batch/new",
            data={
                "item_code": "ITEM-LOT",
                "batch_no": "LOT-FORM",
                "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
                "manufacturing_date": date.today().isoformat(),
                "description": "Lote creado desde el formulario",
                "is_active": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        batch = database.session.execute(
            database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-FORM")
        ).scalar_one()
        assert response.headers["Location"].endswith(f"/inventory/batch/{batch.id}")
        assert batch.is_active is True


def test_batch_new_route_rejects_duplicate_with_flash(app_ctx):
    """Un lote duplicado muestra error y no persiste."""
    with app_ctx.test_client() as client:
        _login(client)
        response = client.post(
            "/inventory/batch/new",
            data={"item_code": "ITEM-LOT", "batch_no": "LOT-A", "is_active": "y"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"ya existe" in response.data
        batches = (
            database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalars().all()
        )
        assert len(batches) == 1


def test_batch_new_route_rejects_empty_batch_no(app_ctx):
    """El número de lote vacío es rechazado por el formulario."""
    with app_ctx.test_client() as client:
        _login(client)
        response = client.post(
            "/inventory/batch/new",
            data={"item_code": "ITEM-LOT", "batch_no": "", "is_active": "y"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Revise los datos del formulario" in response.data


def test_batch_detail_route_shows_balance_per_warehouse(app_ctx):
    """El detalle muestra el saldo por bodega y los movimientos del lote."""
    lot_a = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalar_one()

    with app_ctx.test_client() as client:
        _login(client)
        response = client.get(f"/inventory/batch/{lot_a.id}")

        assert response.status_code == 200
        assert b"WH-A" in response.data
        assert b"WH-B" in response.data


def test_batch_detail_route_404_for_unknown_batch(app_ctx):
    """Un lote inexistente responde 404."""
    with app_ctx.test_client() as client:
        _login(client)
        response = client.get("/inventory/batch/NO-EXISTE")

        assert response.status_code == 404


def test_inventory_home_links_to_batch_list(app_ctx):
    """La página del módulo incluye el acceso al maestro de lotes."""
    with app_ctx.test_client() as client:
        _login(client)
        response = client.get("/inventory", follow_redirects=True)

        assert response.status_code == 200
        assert b"/inventory/batch/list" in response.data


# <------------------------------------------------------------------------------------------> #
# Kardex con trazabilidad de lote y serial
# <------------------------------------------------------------------------------------------> #


def test_kardex_includes_batch_and_serial_columns(app_ctx):
    """El kardex proyecta el número de lote y el serial de cada movimiento."""
    from cacao_accounting.reportes.services import KardexFilters, get_kardex

    lot_a = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalar_one()
    database.session.add(
        StockLedgerEntry(
            posting_date=date.today(),
            item_code="ITEM-LOT",
            warehouse="WH-A",
            company="cacao",
            batch_id=lot_a.id,
            serial_no="SN-773",
            qty_change=Decimal("1"),
            qty_after_transaction=Decimal("1"),
            valuation_rate=Decimal("1"),
            stock_value_difference=Decimal("1"),
            stock_value=Decimal("1"),
            voucher_type="seed",
            voucher_id="sle-kardex",
        )
    )
    database.session.commit()

    report = get_kardex(KardexFilters(company="cacao", item_code="ITEM-LOT"))

    assert "batch_no" in report.columns
    assert "serial_no" in report.columns
    target = [row.values for row in report.rows if row.values["voucher_id"] == "sle-kardex"]
    assert len(target) == 1
    assert target[0]["batch_no"] == "LOT-A"
    assert target[0]["serial_no"] == "SN-773"


# <------------------------------------------------------------------------------------------> #
# Reporte de lotes con saldo por lote y bodega
# <------------------------------------------------------------------------------------------> #


def test_batch_report_shows_balance_per_warehouse(app_ctx):
    """El reporte de lotes muestra el saldo por lote y bodega."""
    from cacao_accounting.reportes.services import OperationalReportFilters, get_batch_report

    report = get_batch_report(OperationalReportFilters(company="cacao"))

    rows = [row.values for row in report.rows]
    lot_a_rows = [row for row in rows if row["batch_no"] == "LOT-A"]
    assert {(row["warehouse"], row["balance_qty"]) for row in lot_a_rows} == {("WH-A", Decimal("3")), ("WH-B", Decimal("2"))}
    assert Decimal("5") == sum(row["stock_value"] for row in lot_a_rows)


def test_batch_report_includes_batches_without_movements(app_ctx):
    """Los lotes sin movimientos se listan con saldo cero."""
    from cacao_accounting.reportes.services import OperationalReportFilters, get_batch_report

    report = get_batch_report(OperationalReportFilters(company="cacao"))

    empty_rows = [row.values for row in report.rows if row.values["batch_no"] == "LOT-EMPTY"]
    assert len(empty_rows) == 1
    assert empty_rows[0]["balance_qty"] == Decimal("0")


def test_batch_report_filters_by_item(app_ctx):
    """El filtro por item restringe el reporte a los lotes de ese item."""
    from cacao_accounting.reportes.services import OperationalReportFilters, get_batch_report

    report = get_batch_report(OperationalReportFilters(company="cacao", item_code="ITEM-EXP"))

    assert report.rows == []


def test_batch_report_filters_by_warehouse(app_ctx):
    """El filtro por bodega restringe las filas de saldo a esa bodega."""
    from cacao_accounting.reportes.services import OperationalReportFilters, get_batch_report

    report = get_batch_report(OperationalReportFilters(company="cacao", warehouse="WH-A"))

    lot_a_rows = [row.values for row in report.rows if row.values["batch_no"] == "LOT-A"]
    assert lot_a_rows == [
        {
            "item_code": "ITEM-LOT",
            "batch_no": "LOT-A",
            "warehouse": "WH-A",
            "expiry_date": None,
            "is_active": True,
            "balance_qty": Decimal("3"),
            "stock_value": Decimal("3"),
        }
    ]


# <------------------------------------------------------------------------------------------> #
# Importador: resolución del número de lote al maestro
# <------------------------------------------------------------------------------------------> #


def _purchase_receipt_adapter():
    from cacao_accounting.imports.adapters.transaction_documents import PurchaseReceiptAdapter

    return PurchaseReceiptAdapter()


class _ImportLine:
    """Línea mínima con campo batch_id para el adaptador de importaciones."""

    def __init__(self, item_code):
        self.item_code = item_code
        self.batch_id = None


def test_import_adapter_resolves_batch_no_to_master_pk(app_ctx):
    """La columna lote se resuelve al identificador interno del maestro."""
    lot_a = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalar_one()
    adapter = _purchase_receipt_adapter()
    line = _ImportLine("ITEM-LOT")

    adapter._apply_item_batch_serial_fields(line, {"lote": "LOT-A"})  # noqa: SLF001

    assert line.batch_id == lot_a.id


def test_import_adapter_rejects_unknown_batch(app_ctx):
    """Un lote inexistente en el maestro rechaza la fila."""
    adapter = _purchase_receipt_adapter()
    line = _ImportLine("ITEM-LOT")

    with pytest.raises(ValueError, match="no existe en el maestro de lotes"):
        adapter._apply_item_batch_serial_fields(line, {"lote": "LOT-404"})  # noqa: SLF001


def test_import_adapter_validate_document_flags_batch_errors(app_ctx):
    """La validación de documento reporta lotes faltantes o desconocidos."""
    adapter = _purchase_receipt_adapter()
    lot_a = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalar_one()
    lot_a.is_active = False
    database.session.commit()

    errors = adapter.validate_document(
        [
            {
                "document_ref": "PR-773",
                "fecha": date.today().isoformat(),
                "producto": "ITEM-LOT",
                "cantidad": "1",
                "precio_unitario": "1",
                "bodega": "WH-A",
                "lote": "",
            },
            {
                "document_ref": "PR-773",
                "fecha": date.today().isoformat(),
                "producto": "ITEM-LOT",
                "cantidad": "1",
                "precio_unitario": "1",
                "bodega": "WH-A",
                "lote": "LOT-A",
            },
        ],
        {"company_id": "cacao"},
    )

    assert any("requiere lote" in message for message in errors)
    assert any("está inactivo" in message for message in errors)


def test_import_adapter_validate_document_accepts_known_active_batch(app_ctx):
    """Un lote conocido y activo no genera errores de lote en la validación."""
    adapter = _purchase_receipt_adapter()

    errors_valid = adapter.validate_document(
        [
            {
                "document_ref": "PR-773-OK",
                "fecha": date.today().isoformat(),
                "producto": "ITEM-LOT",
                "cantidad": "1",
                "precio_unitario": "1",
                "bodega": "WH-A",
                "lote": "LOT-A",
            }
        ],
        {"company_id": "cacao"},
    )
    errors_unknown = adapter.validate_document(
        [
            {
                "document_ref": "PR-773-UNKNOWN",
                "fecha": date.today().isoformat(),
                "producto": "ITEM-LOT",
                "cantidad": "1",
                "precio_unitario": "1",
                "bodega": "WH-A",
                "lote": "LOT-404",
            }
        ],
        {"company_id": "cacao"},
    )

    assert not any("lote" in message for message in errors_valid)
    assert any("no existe en el maestro de lotes" in message for message in errors_unknown)


def test_import_adapter_skips_batch_validation_when_not_enabled(app_ctx):
    """Los documentos sin campos de lote no ejecutan la validación de lote."""
    from cacao_accounting.imports.adapters.transaction_documents import (
        TransactionDocumentAdapter,
        TransactionImportConfig,
    )

    adapter = TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_order",
            header_model=object,
            item_model=object,
            parent_field="purchase_order_id",
        )
    )

    assert adapter._validate_row_batch("ITEM-LOT", "LOT-A") == []  # noqa: SLF001


def test_import_adapter_skips_batch_validation_for_uncontrolled_items(app_ctx):
    """Items sin control de lote o inexistentes no generan errores de lote."""
    adapter = _purchase_receipt_adapter()

    assert adapter._validate_row_batch("", "LOT-A") == []  # noqa: SLF001
    assert adapter._validate_row_batch("ITEM-404", "LOT-A") == []  # noqa: SLF001
    assert adapter._validate_row_batch("ITEM-SVC", "LOT-A") == []  # noqa: SLF001
    assert adapter._validate_row_batch("ITEM-NB", "") == []  # noqa: SLF001


def test_import_adapter_resolves_empty_batch_to_none(app_ctx):
    """Una fila sin lote persiste batch_id nulo."""
    adapter = _purchase_receipt_adapter()
    line = _ImportLine("ITEM-LOT")

    adapter._apply_item_batch_serial_fields(line, {"lote": ""})  # noqa: SLF001

    assert line.batch_id is None


def test_import_adapter_rejects_inactive_batch_on_build(app_ctx):
    """Un lote inactivo rechaza la construcción de la línea importada."""
    adapter = _purchase_receipt_adapter()
    lot_a = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-LOT", batch_no="LOT-A")).scalar_one()
    lot_a.is_active = False
    database.session.commit()
    line = _ImportLine("ITEM-LOT")

    with pytest.raises(ValueError, match="está inactivo"):
        adapter._apply_item_batch_serial_fields(line, {"lote": "LOT-A"})  # noqa: SLF001
