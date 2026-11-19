# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1004: cada periodo de numeración conserva su propio consecutivo.

Un documento retroactivo de un periodo anterior no debe reiniciar el contador
vigente ni reutilizar un folio ya emitido. La clave del periodo se deriva de
la fecha contable y de la política efectiva de la secuencia.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    GeneratedIdentifierLog,
    NamingSeries,
    Sequence,
    SequencePeriodCounter,
    SeriesSequenceMap,
    database,
)
from cacao_accounting.database.helpers import generate_identifier


def _app(uri: str):
    """Crea una aplicación con el motor indicado y CSRF deshabilitado."""
    settings = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "MODO_ESCRITORIO": True,
    }
    if uri == "sqlite://":
        settings["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
    return create_app(settings)


def _configured_test_uri() -> str:
    """Devuelve el motor configurado; SQLite se aísla en memoria."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if make_url(configured_uri).get_backend_name() == "sqlite":
        return "sqlite://"
    return configured_uri


def _serie(prefix: str, policy: str, suffix: str, company: str = "A") -> tuple[NamingSeries, Sequence]:
    """Crea una serie con su secuencia y mapeo."""
    series = NamingSeries(
        name=f"Serie {suffix}",
        entity_type="sales_invoice",
        company=company,
        prefix_template=prefix,
        is_active=True,
        is_default=False,
    )
    sequence = Sequence(name=f"Secuencia {suffix}", current_value=0, increment=1, padding=5, reset_policy=policy)
    database.session.add_all([series, sequence])
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=sequence.id, priority=0))
    database.session.flush()
    return series, sequence


def _sembrar_base() -> dict[str, tuple[str, str]]:
    """Siembra compañía, moneda y tres políticas de numeración."""
    suffix = uuid4().hex[:6].upper()
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
        ]
    )
    database.session.flush()
    anual, secuencia_anual = _serie("SI-*YYYY*-", "yearly", f"AN{suffix}")
    mensual, secuencia_mensual = _serie("SM-*YYYY*-*MM*-", "monthly", f"ME{suffix}")
    global_, secuencia_global = _serie("SG-", "never", f"GL{suffix}")
    database.session.commit()
    return {
        "yearly": (anual.id, secuencia_anual.id),
        "monthly": (mensual.id, secuencia_mensual.id),
        "never": (global_.id, secuencia_global.id),
    }


def _generar(app, series_id: str, sequence_id: str, posting_date: date) -> str:
    """Genera un folio dentro de un contexto de aplicación y confirma."""
    with app.app_context():
        folio = generate_identifier(
            entity_type="sales_invoice",
            entity_id=f"doc-{uuid4().hex[:8]}",
            posting_date=posting_date,
            company="A",
            naming_series_id=series_id,
            sequence_id=sequence_id,
        )
        database.session.commit()
        return folio


@pytest.fixture
def series_periodicas(tmp_path: Path):
    """Base con secuencias anual, mensual y sin reinicio."""
    application = _app(f"sqlite:///{tmp_path / 'secuencias-periodos.sqlite'}")
    with application.app_context():
        database.create_all()
        ids = _sembrar_base()
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_fecha_retroactiva_anual_conserva_el_consecutivo(series_periodicas):
    """Volver a 2025 después de emitir 2026 continúa el contador de 2025."""
    application, ids = series_periodicas
    series_id, sequence_id = ids["yearly"]

    assert _generar(application, series_id, sequence_id, date(2025, 12, 31)) == "SI-2025-00001"
    assert _generar(application, series_id, sequence_id, date(2026, 1, 1)) == "SI-2026-00001"
    assert _generar(application, series_id, sequence_id, date(2025, 12, 30)) == "SI-2025-00002"

    with application.app_context():
        contadores = {
            row.period_key: row.current_value
            for row in database.session.execute(database.select(SequencePeriodCounter).filter_by(sequence_id=sequence_id))
            .scalars()
            .all()
        }
        assert contadores == {"2025": 2, "2026": 1}
        periodos = database.session.execute(
            database.select(GeneratedIdentifierLog.full_identifier, GeneratedIdentifierLog.sequence_period)
            .filter_by(sequence_id=sequence_id)
            .order_by(GeneratedIdentifierLog.full_identifier)
        ).all()
        assert periodos == [
            ("SI-2025-00001", "2025"),
            ("SI-2025-00002", "2025"),
            ("SI-2026-00001", "2026"),
        ]


def test_fecha_retroactiva_mensual_conserva_el_consecutivo(series_periodicas):
    """La política mensual mantiene un contador independiente por mes."""
    application, ids = series_periodicas
    series_id, sequence_id = ids["monthly"]

    assert _generar(application, series_id, sequence_id, date(2026, 1, 15)) == "SM-2026-01-00001"
    assert _generar(application, series_id, sequence_id, date(2026, 2, 10)) == "SM-2026-02-00001"
    assert _generar(application, series_id, sequence_id, date(2026, 1, 20)) == "SM-2026-01-00002"


def test_politica_sin_reinicio_mantiene_el_contador_global(series_periodicas):
    """La política never conserva el contador único entre años."""
    application, ids = series_periodicas
    series_id, sequence_id = ids["never"]

    assert _generar(application, series_id, sequence_id, date(2025, 12, 31)) == "SG-00001"
    assert _generar(application, series_id, sequence_id, date(2026, 1, 1)) == "SG-00002"

    with application.app_context():
        assert (
            database.session.execute(database.select(SequencePeriodCounter).filter_by(sequence_id=sequence_id)).scalars().all()
            == []
        )


@pytest.mark.database
def test_reservas_concurrentes_del_mismo_periodo_en_motor_configurado():
    """Cuatro transacciones del mismo periodo obtienen folios únicos y consecutivos.

    Se ejecuta contra PostgreSQL en CI: allí ``SELECT ... FOR UPDATE`` serializa
    la reserva del contador del periodo.
    """
    application = _app(_configured_test_uri())
    suffix = uuid4().hex[:6].upper()
    company_code = f"A{suffix}"
    with application.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code=company_code,
                name=company_code,
                company_name=f"{company_code} SA",
                tax_id=f"J-{suffix}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        series, sequence = _serie("SC-*YYYY*-", "yearly", f"CO{suffix}", company=company_code)
        database.session.commit()
        series_id, sequence_id = series.id, sequence.id

    barrier = Barrier(4)

    def reservar(indice: int) -> str:
        with application.app_context():
            barrier.wait(timeout=15)
            try:
                folio = generate_identifier(
                    entity_type="sales_invoice",
                    entity_id=f"doc-{suffix}-{indice}",
                    posting_date=date(2026, 5, 20),
                    company=company_code,
                    naming_series_id=series_id,
                    sequence_id=sequence_id,
                )
                database.session.commit()
                return folio
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=4) as workers:
        folios = list(workers.map(reservar, range(4)))

    assert sorted(folios) == [f"SC-2026-{valor:05d}" for valor in range(1, 5)]
    assert len(set(folios)) == 4

    with application.app_context():
        database.session.execute(
            database.delete(GeneratedIdentifierLog).where(GeneratedIdentifierLog.sequence_id == sequence_id)
        )
        database.session.execute(
            database.delete(SequencePeriodCounter).where(SequencePeriodCounter.sequence_id == sequence_id)
        )
        database.session.execute(database.delete(SeriesSequenceMap).where(SeriesSequenceMap.sequence_id == sequence_id))
        database.session.delete(database.session.get(Sequence, sequence_id))
        database.session.delete(database.session.get(NamingSeries, series_id))
        database.session.execute(database.delete(Entity).where(Entity.code == company_code))
        database.session.commit()
        database.session.remove()
        database.engine.dispose()
