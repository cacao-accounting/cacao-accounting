# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#332: carreras en INSERT de StockBin y validación de bodega en el posting."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event, Lock, local
from time import monotonic, sleep
from uuid import uuid4

import pytest
from flask_login import login_user
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from test_purchase_receipt_return_cancel_postgresql import _drop, _isolated_url

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _insert_stock_bin_race_safe,
    post_stock_entry,
)
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    UOM,
    User,
    Warehouse,
    database,
)


def _sembrar_item_bodega(artefacto: str, bodega: str, uom: str) -> None:
    """Crea el item y la bodega referenciados por el bin (#332)."""
    database.session.add(UOM(code=uom, name="Unidad 332"))
    database.session.flush()
    database.session.add(Item(code=artefacto, name="Articulo 332", item_type="goods", is_stock_item=True, default_uom=uom))
    database.session.flush()
    database.session.add(Warehouse(code=bodega, name="Bodega 332", company="cacao"))
    database.session.flush()


def test_insert_stock_bin_race_safe_retoma_bin_existente(app):
    """Si otra transacción insertó el bin antes, se devuelve el registro existente (#332)."""
    with app.app_context():
        _sembrar_item_bodega("ART-332", "BOD-332", "UND332A")
        existing = StockBin(company="cacao", item_code="ART-332", warehouse="BOD-332", actual_qty=Decimal("7"))
        database.session.add(existing)
        database.session.commit()
        row = _insert_stock_bin_race_safe(company="cacao", item_code="ART-332", warehouse="BOD-332")
        assert row.id == existing.id


def test_insert_stock_bin_race_safe_crea_bin_nuevo(app):
    """Sin bin existente, el insert se confirma y devuelve el nuevo registro (#332)."""
    with app.app_context():
        _sembrar_item_bodega("ART-332B", "BOD-332B", "UND332B")
        row = _insert_stock_bin_race_safe(company="cacao", item_code="ART-332B", warehouse="BOD-332B")
        assert row.actual_qty == Decimal("0")


@pytest.fixture
def pg_stock_bin_app():
    """Crea una base PostgreSQL aislada con maestros y ningún StockBin."""
    url, nombre = _isolated_url()
    aplicacion = None
    try:
        aplicacion = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "TESTING": True,
                "SECRET_KEY": "test-2358-stock-bin-race",
                "MODO_ESCRITORIO": False,
            }
        )
        with aplicacion.app_context():
            database.create_all()
            database.session.add_all(
                [
                    Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                    Entity(
                        code="cacao",
                        name="Cacao",
                        company_name="Cacao SA",
                        tax_id="J-2358",
                        currency="NIO",
                        enabled=True,
                    ),
                    UOM(code="UND2358", name="Unidad 2358"),
                    Item(
                        code="ART-2358",
                        name="Artículo 2358",
                        item_type="goods",
                        is_stock_item=True,
                        default_uom="UND2358",
                    ),
                    Warehouse(code="BOD-2358", name="Bodega 2358", company="cacao"),
                ]
            )
            database.session.commit()
            assert database.session.execute(database.select(StockBin)).scalars().all() == []
            database.session.remove()
        yield aplicacion
    finally:
        if aplicacion is not None:
            with aplicacion.app_context():
                database.session.remove()
                database.engine.dispose()
        _drop(url, nombre)


def _confirmar_bloqueo_stock_bin(monitor, pid: int, pid_bloqueador: int, timeout: float) -> str:
    """Exige evidencia PostgreSQL de que el segundo INSERT espera al primero."""
    limite = monotonic() + timeout
    ultima_fila = None
    while monotonic() < limite:
        with monitor.connect() as conexion:
            ultima_fila = (
                conexion.execute(
                    text(
                        "SELECT state, wait_event_type, wait_event, pg_blocking_pids(pid) AS blockers "
                        "FROM pg_stat_activity WHERE pid = :pid"
                    ),
                    {"pid": pid},
                )
                .mappings()
                .one_or_none()
            )
        if ultima_fila is not None:
            bloqueantes = [int(valor) for valor in (ultima_fila["blockers"] or [])]
            if ultima_fila["state"] == "active" and ultima_fila["wait_event_type"] == "Lock" and pid_bloqueador in bloqueantes:
                return str(ultima_fila["wait_event"])
        sleep(0.05)
    pytest.fail(f"La sesión {pid} no bloqueó contra {pid_bloqueador}: {ultima_fila}")
    return ""


@pytest.mark.database
def test_primer_stock_bin_concurrente_acumula_ambos_deltas(pg_stock_bin_app, monkeypatch):
    """Dos sesiones compiten por el primer bin y ninguna pierde su delta (#2358)."""
    real_insert = _insert_stock_bin_race_safe
    ganador_inserto = Event()
    liberar_ganador = Event()
    perdedor_va_insertar = Event()
    estado_hilo = local()
    resultados: dict[str, object] = {}
    candado = Lock()

    def insert_coordinado(company: str, item_code: str, warehouse: str):
        """Pausa al ganador sin confirmar y deja que el perdedor llegue al INSERT real."""
        if getattr(estado_hilo, "ganador", False):
            fila = real_insert(company, item_code, warehouse)
            ganador_inserto.set()
            if not liberar_ganador.wait(timeout=25):
                raise TimeoutError("No se liberó la transacción ganadora.")
            return fila
        if not ganador_inserto.wait(timeout=15):
            raise TimeoutError("El ganador no insertó el bin.")
        perdedor_va_insertar.set()
        return real_insert(company, item_code, warehouse)

    monkeypatch.setattr(posting_service, "_insert_stock_bin_race_safe", insert_coordinado)

    def aplicar_delta(ganador: bool, qty_change: Decimal, value_change: Decimal) -> dict[str, object]:
        """Aplica el upsert real en una sesión independiente y confirma su transacción."""
        estado_hilo.ganador = ganador
        rol = "ganador" if ganador else "perdedor"
        with pg_stock_bin_app.app_context():
            try:
                conexion = database.session.connection()
                pid = int(conexion.execute(text("SELECT pg_backend_pid()")).scalar_one())
                aislamiento = str(conexion.execute(text("SHOW transaction_isolation")).scalar_one())
                with candado:
                    resultados[f"{rol}_pid"] = pid
                    resultados[f"{rol}_aislamiento"] = aislamiento
                qty_after, value_after = posting_service._upsert_stock_bin(
                    company="cacao",
                    item_code="ART-2358",
                    warehouse="BOD-2358",
                    qty_change=qty_change,
                    valuation_rate=Decimal("10"),
                    value_change=value_change,
                )
                database.session.commit()
                return {"estado": "confirmado", "qty_after": qty_after, "value_after": value_after}
            except IntegrityError as exc:
                database.session.rollback()
                return {"estado": "integrity_error_escapado", "detalle": repr(exc)}
            except Exception as exc:  # pragma: no cover - diagnóstico de la carrera
                database.session.rollback()
                return {"estado": "error", "detalle": repr(exc)}
            finally:
                database.session.remove()

    monitor = create_engine(pg_stock_bin_app.config["SQLALCHEMY_DATABASE_URI"])
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            try:
                futuro_ganador = workers.submit(aplicar_delta, True, Decimal("2"), Decimal("20"))
                assert ganador_inserto.wait(timeout=15), "el ganador no insertó el primer bin"
                futuro_perdedor = workers.submit(aplicar_delta, False, Decimal("3"), Decimal("45"))
                assert perdedor_va_insertar.wait(timeout=15), "el perdedor no llegó al helper de inserción"

                pid_ganador = int(resultados["ganador_pid"])
                pid_perdedor = int(resultados["perdedor_pid"])
                assert pid_ganador != pid_perdedor
                assert str(resultados["ganador_aislamiento"]).lower() == "read committed"
                assert str(resultados["perdedor_aislamiento"]).lower() == "read committed"
                assert _confirmar_bloqueo_stock_bin(monitor, pid_perdedor, pid_ganador, timeout=15)
                liberar_ganador.set()
                resultado_ganador = futuro_ganador.result(timeout=25)
                resultado_perdedor = futuro_perdedor.result(timeout=25)
            finally:
                liberar_ganador.set()
    finally:
        monitor.dispose()

    assert resultado_ganador == {"estado": "confirmado", "qty_after": Decimal("2"), "value_after": Decimal("20")}
    assert resultado_perdedor == {"estado": "confirmado", "qty_after": Decimal("5"), "value_after": Decimal("65")}
    with pg_stock_bin_app.app_context():
        filas = (
            database.session.execute(database.select(StockBin).filter_by(item_code="ART-2358", warehouse="BOD-2358"))
            .scalars()
            .all()
        )
        assert len(filas) == 1
        fila = filas[0]
        assert fila.company == "cacao"
        assert fila.actual_qty == Decimal("5")
        assert fila.stock_value == Decimal("65")
        assert fila.valuation_rate == Decimal("13")


def test_post_stock_entry_rechaza_bodega_ajena_al_company(app, entorno_contable):
    """El posting rechaza bodegas que no pertenecen a la compañía del documento (#332)."""
    with app.app_context():
        artefacto = f"332A-{uuid4().hex[:6].upper()}"
        bodega = f"332W-{uuid4().hex[:6].upper()}"
        sufijo = uuid4().hex[:6].upper()
        otra_compania = f"C{sufijo}"
        database.session.add_all(
            [
                Entity(
                    code=otra_compania,
                    name="Cafe",
                    company_name=f"Cafe {sufijo} SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                ),
                Item(code=artefacto, name="Articulo 332", item_type="goods", is_stock_item=True, default_uom="UND"),
                Warehouse(code=bodega, name="Bodega ajena 332", company=otra_compania),
            ]
        )
        database.session.commit()
        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date(2026, 5, 20),
            to_warehouse=bodega,
            from_warehouse=bodega,
            document_no=f"332P-{uuid4().hex[:8]}",
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=1,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=artefacto,
                source_warehouse=bodega,
                target_warehouse=bodega,
                qty=Decimal("5"),
                uom="UND",
                qty_in_base_uom=Decimal("5"),
                basic_rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        database.session.commit()
        with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
            login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
            with pytest.raises(PostingError, match="no pertenece a la compañía"):
                post_stock_entry(entry)
