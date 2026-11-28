# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2175: los folios son únicos por compañía y tipo documental.

Escenario de negocio: dos compañías pueden usar el mismo prefijo y contador
independiente, por lo que sus folios comerciales pueden coincidir. Dentro de
una compañía, el mismo folio y tipo documental se rechaza aunque provenga de
otra serie. Los identificadores internos sin compañía conservan su unicidad
global.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    GeneratedIdentifierLog,
    NamingSeries,
    Sequence,
    SeriesSequenceMap,
    database,
)
from cacao_accounting.database.helpers import generate_identifier

GENERATED_IDENTIFIER_GLOBAL_INDEX = "uq_generated_identifier_log_global_identifier"

FECHA = date(2026, 10, 31)


def _app(uri: str):
    """Crea una aplicación con la base indicada."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def _serie(company: str | None, entity_type: str, prefix: str, suffix: str) -> tuple[NamingSeries, Sequence]:
    """Crea una serie con su secuencia y mapeo, ambas iniciando en cero."""
    series = NamingSeries(
        name=f"Serie {suffix}",
        entity_type=entity_type,
        company=company,
        prefix_template=prefix,
        is_active=True,
        is_default=False,
    )
    sequence = Sequence(name=f"Secuencia {suffix}", current_value=0, increment=1, padding=5, reset_policy="never")
    database.session.add_all([series, sequence])
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=sequence.id, priority=0))
    database.session.flush()
    return series, sequence


@pytest.fixture
def folios(tmp_path: Path):
    """Base con dos compañías y series con el mismo prefijo."""
    aplicación = _app(f"sqlite:///{tmp_path / 'folios.sqlite'}")
    with aplicación.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="A",
                    name="A",
                    company_name="A SA",
                    tax_id="J-A",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="B",
                    name="B",
                    company_name="B SA",
                    tax_id="J-B",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        serie_a, secuencia_a = _serie("A", "sales_invoice", "INV-", "A")
        serie_b, secuencia_b = _serie("B", "sales_invoice", "INV-", "B")
        serie_c, secuencia_c = _serie("A", "sales_invoice", "INV-", "C")
        serie_d, secuencia_d = _serie("A", "purchase_invoice", "INV-", "D")
        serie_global, secuencia_global = _serie(None, "item", "ITEM-", "G")
        database.session.commit()
        ids = {
            "a": (serie_a.id, secuencia_a.id),
            "b": (serie_b.id, secuencia_b.id),
            "c": (serie_c.id, secuencia_c.id),
            "d": (serie_d.id, secuencia_d.id),
            "global": (serie_global.id, secuencia_global.id),
        }
    yield aplicación, ids
    with aplicación.app_context():
        database.session.remove()
        database.engine.dispose()


def _generar(series_id: str, sequence_id: str, company: str | None, entity_type: str, entity_id: str) -> str:
    """Genera un folio y confirma la transacción."""
    folio = generate_identifier(
        entity_type=entity_type,
        entity_id=entity_id,
        posting_date=FECHA,
        company=company,
        naming_series_id=series_id,
        sequence_id=sequence_id,
    )
    database.session.commit()
    return folio


def test_permite_el_mismo_folio_entre_companias(folios):
    """Dos compañías con el mismo prefijo y contadores independientes coexisten."""
    aplicación, ids = folios
    with aplicación.app_context():
        assert _generar(*ids["a"], "A", "sales_invoice", "doc-a") == "INV-00001"
        assert _generar(*ids["b"], "B", "sales_invoice", "doc-b") == "INV-00001"
        filas = database.session.execute(database.select(GeneratedIdentifierLog.full_identifier)).scalars().all()
        assert filas.count("INV-00001") == 2


def test_rechaza_duplicado_de_la_misma_compania_y_tipo(folios):
    """Otra serie de la misma compañía no puede repetir el folio."""
    aplicación, ids = folios
    with aplicación.app_context():
        _generar(*ids["a"], "A", "sales_invoice", "doc-a")
        with pytest.raises(IntegrityError):
            _generar(*ids["c"], "A", "sales_invoice", "doc-c")
        database.session.rollback()
        assert len(database.session.execute(database.select(GeneratedIdentifierLog)).scalars().all()) == 1


def test_permite_el_mismo_folio_en_otro_tipo_documental(folios):
    """El ámbito documental separa folios iguales dentro de la misma compañía."""
    aplicación, ids = folios
    with aplicación.app_context():
        _generar(*ids["a"], "A", "sales_invoice", "doc-a")
        assert _generar(*ids["d"], "A", "purchase_invoice", "doc-d") == "INV-00001"


def test_identificadores_internos_conservan_unicidad_global(folios):
    """Una serie global sin compañía conserva la unicidad de sus códigos."""
    aplicación, ids = folios
    with aplicación.app_context():
        _generar(*ids["global"], None, "item", "item-1")
        otra_serie, otra_secuencia = _serie(None, "item", "ITEM-", "G2")
        database.session.commit()
        with pytest.raises(ValueError, match="ya existe"):
            _generar(otra_serie.id, otra_secuencia.id, None, "item", "item-2")
        database.session.rollback()
        assert len(database.session.execute(database.select(GeneratedIdentifierLog)).scalars().all()) == 1


def test_dos_companias_pueden_generar_el_mismo_folio_a_la_vez(tmp_path: Path):
    """La concurrencia entre compañías distintas no bloquea el mismo folio."""
    aplicación = _app(f"sqlite:///{tmp_path / 'concurrente-companias.sqlite'}")
    with aplicación.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="A",
                    name="A",
                    company_name="A SA",
                    tax_id="J-A",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="B",
                    name="B",
                    company_name="B SA",
                    tax_id="J-B",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        serie_a, secuencia_a = _serie("A", "sales_invoice", "INV-", "CA")
        serie_b, secuencia_b = _serie("B", "sales_invoice", "INV-", "CB")
        database.session.commit()
        ids = [("A", serie_a.id, secuencia_a.id), ("B", serie_b.id, secuencia_b.id)]

    barrier = Barrier(2, timeout=30)

    def ejecutar(indice: int):
        company, series_id, sequence_id = ids[indice]
        with aplicación.app_context():
            barrier.wait(timeout=10)
            try:
                generate_identifier(
                    entity_type="sales_invoice",
                    entity_id=f"doc-{company}",
                    posting_date=FECHA,
                    company=company,
                    naming_series_id=series_id,
                    sequence_id=sequence_id,
                )
                database.session.commit()
                return "ok"
            except SQLAlchemyError:
                database.session.rollback()
                return "error"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        resultados = list(workers.map(ejecutar, range(2)))

    assert resultados == ["ok", "ok"]
    with aplicación.app_context():
        filas = database.session.execute(
            database.select(GeneratedIdentifierLog.company, GeneratedIdentifierLog.full_identifier)
        ).all()
        assert sorted(filas) == [("A", "INV-00001"), ("B", "INV-00001")]
        database.session.remove()
        database.engine.dispose()


def test_guard_interno_no_depende_del_indice_parcial(tmp_path: Path):
    """La unicidad global interna se conserva aunque el motor no tenga índice parcial."""
    aplicación = _app(f"sqlite:///{tmp_path / 'sin-indice-global.sqlite'}")
    with aplicación.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        serie_uno, secuencia_uno = _serie(None, "item", "ITEM-", "G1")
        serie_dos, secuencia_dos = _serie(None, "item", "ITEM-", "G2")
        database.session.commit()
        with database.engine.begin() as connection:
            connection.exec_driver_sql(f"DROP INDEX {GENERATED_IDENTIFIER_GLOBAL_INDEX}")

        _generar(serie_uno.id, secuencia_uno.id, None, "item", "item-1")
        with pytest.raises(ValueError, match="ya existe"):
            _generar(serie_dos.id, secuencia_dos.id, None, "item", "item-2")
        database.session.remove()
        database.engine.dispose()
