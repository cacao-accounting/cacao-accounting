# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2129: la secuencia se elige según la condición del mapeo."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, database
from cacao_accounting.document_identifiers import IdentifierConfigurationError, _pick_sequence_id


@pytest.fixture
def series_con_condiciones():
    """Serie con secuencias para banco A, banco B y fallback."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with app.app_context():
        database.create_all()
        suffix = uuid4().hex[:6]
        series = NamingSeries(
            name=f"COND-{suffix}",
            entity_type="payment_entry",
            company=None,
            prefix_template=f"COND-{suffix}-",
            is_active=True,
            is_default=False,
        )
        secuencia_a = Sequence(name=f"A-{suffix}", current_value=0, increment=1, padding=5, reset_policy="never")
        secuencia_b = Sequence(name=f"B-{suffix}", current_value=0, increment=1, padding=5, reset_policy="never")
        fallback = Sequence(name=f"F-{suffix}", current_value=0, increment=1, padding=5, reset_policy="never")
        database.session.add_all([series, secuencia_a, secuencia_b, fallback])
        database.session.flush()
        database.session.add_all(
            [
                SeriesSequenceMap(
                    naming_series_id=series.id,
                    sequence_id=secuencia_a.id,
                    priority=0,
                    condition=json.dumps({"bank": "A"}),
                ),
                SeriesSequenceMap(
                    naming_series_id=series.id,
                    sequence_id=secuencia_b.id,
                    priority=1,
                    condition=json.dumps({"bank": "B"}),
                ),
                SeriesSequenceMap(
                    naming_series_id=series.id,
                    sequence_id=fallback.id,
                    priority=2,
                    condition=None,
                ),
            ]
        )
        database.session.commit()
        ids = {
            "series": series.id,
            "a": secuencia_a.id,
            "b": secuencia_b.id,
            "fallback": fallback.id,
        }
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_selecciona_la_secuencia_cuya_condicion_coincide(series_con_condiciones):
    """Banco A y banco B usan su propia secuencia, no la de menor prioridad."""
    app, ids = series_con_condiciones
    with app.app_context():
        assert _pick_sequence_id(ids["series"], {"bank": "A"}) == ids["a"]
        assert _pick_sequence_id(ids["series"], {"bank": "B"}) == ids["b"]


def test_usa_el_fallback_sin_condicion(series_con_condiciones):
    """Un contexto no cubierto usa el mapeo sin condición."""
    app, ids = series_con_condiciones
    with app.app_context():
        assert _pick_sequence_id(ids["series"], {"bank": "C"}) == ids["fallback"]
        assert _pick_sequence_id(ids["series"], None) == ids["fallback"]


def test_serie_sin_mapeos_falla(series_con_condiciones):
    """Una serie sin secuencias asociadas no inventa una numeración."""
    app, _ids = series_con_condiciones
    with app.app_context():
        series = NamingSeries(
            name="SIN-MAPA",
            entity_type="sales_invoice",
            company=None,
            prefix_template="SIN-",
            is_active=True,
            is_default=False,
        )
        database.session.add(series)
        database.session.commit()
        with pytest.raises(IdentifierConfigurationError):
            _pick_sequence_id(series.id, {})
