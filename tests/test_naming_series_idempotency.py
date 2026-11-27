# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2129: bootstrap idempotente de series globales y de compañía."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import NamingSeries, database
from cacao_accounting.document_identifiers import (
    ensure_default_naming_series_for_company,
    ensure_global_naming_series,
)


def _series(entity_type: str, code: str, company: str | None, *, is_default: bool = False) -> NamingSeries:
    """Crea una serie mínima para el escenario."""
    return NamingSeries(
        name=f"Global-{code}" if company is None else f"{company}-{code}",
        entity_type=entity_type,
        company=company,
        prefix_template=f"{code}-",
        is_active=True,
        is_default=is_default,
    )


def test_global_no_default_se_reutiliza_y_se_marca_default(entorno_contable_aislado):
    """Una global existente no genera otra serie Global-*."""
    app = entorno_contable_aislado.app
    with app.app_context():
        suffix = uuid4().hex[:6]
        entity_type = f"test_global_{suffix}"
        code = entity_type[:3].upper()
        series = _series(entity_type, code, None)
        database.session.add(series)
        database.session.commit()
        series_id = series.id

        ensure_global_naming_series([entity_type])

        rows = (
            database.session.execute(database.select(NamingSeries).filter_by(entity_type=entity_type, company=None))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].id == series_id
        assert rows[0].is_default is True


def test_serie_de_compania_no_default_se_marca_default(entorno_contable_aislado):
    """Una serie local existente se normaliza como default sin crear otra."""
    app = entorno_contable_aislado.app
    with app.app_context():
        suffix = uuid4().hex[:6]
        entity_type = f"test_company_{suffix}"
        code = entity_type[:3].upper()
        series = _series(entity_type, code, "cacao")
        database.session.add(series)
        database.session.commit()
        series_id = series.id

        ensure_default_naming_series_for_company("cacao", [entity_type])

        rows = (
            database.session.execute(database.select(NamingSeries).filter_by(entity_type=entity_type, company="cacao"))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].id == series_id
        assert rows[0].is_default is True


def test_defaults_globales_duplicados_se_normalizan(entorno_contable_aislado):
    """Los duplicados heredados conservan el menor id y quedan idempotentes."""
    app = entorno_contable_aislado.app
    with app.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La simulación de duplicados heredados requiere SQLite.")
        database.session.connection().exec_driver_sql("DROP INDEX IF EXISTS uq_naming_series_default_global")
        suffix = uuid4().hex[:6]
        entity_type = f"test_dup_{suffix}"
        code = entity_type[:3].upper()
        # Los ULID de dos altas en el mismo milisegundo no están ordenados por
        # creación; el contrato normaliza por identificador, así que se fijan
        # ids conocidos para no depender del orden aleatorio del generador.
        first_id = f"01TESTNS{suffix.upper()}0000000000001"
        second_id = f"01TESTNS{suffix.upper()}0000000000002"
        first = _series(entity_type, code, None, is_default=True)
        first.id = first_id
        second = _series(entity_type, code, None, is_default=True)
        second.id = second_id
        database.session.add_all([first, second])
        database.session.commit()

        ensure_global_naming_series([entity_type])
        ensure_global_naming_series([entity_type])

        rows = (
            database.session.execute(database.select(NamingSeries).filter_by(entity_type=entity_type, company=None))
            .scalars()
            .all()
        )
        defaults = [row for row in rows if row.is_default]
        assert len(rows) == 2
        assert len(defaults) == 1
        assert defaults[0].id == first_id
