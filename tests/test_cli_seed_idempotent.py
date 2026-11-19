# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2168: `cacaoctl db seed` no falla si los datos demo ya existen."""

from __future__ import annotations

from click.testing import CliRunner

from cacao_accounting import cli
from cacao_accounting.database import Currency, Entity, database


def test_db_seed_es_idempotente_con_entidad_existente(app, monkeypatch):
    """La segunda ejecución informa que el seed ya está aplicado."""
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).first() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="CACAO",
                name="Demo",
                company_name="Demo SA",
                tax_id="J-DEMO-CACAO",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.commit()

    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)

    def fail_if_called():
        raise AssertionError("dev_data no debe ejecutarse si la entidad demo existe")

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", fail_if_called)

    result = CliRunner().invoke(cli.db_seed)

    assert result.exit_code == 0
    assert "ya están aplicados" in result.output
