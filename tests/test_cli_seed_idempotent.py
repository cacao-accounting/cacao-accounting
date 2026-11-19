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


def test_db_seed_se_rechaza_fuera_de_desarrollo_sin_force(app, monkeypatch):
    """Un entorno no testing no puede sembrar credenciales demo por accidente (#2167)."""
    monkeypatch.setattr("cacao_accounting.config.TESTING_MODE", False)

    def fail_if_called():
        raise AssertionError("dev_data no debe ejecutarse fuera de desarrollo sin --force")

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", fail_if_called)
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: (_ for _ in ()).throw(AssertionError("no debe abrir la app")))

    result = CliRunner().invoke(cli.db_seed)

    assert result.exit_code == 1
    assert "solo está disponible en entornos de desarrollo o con --force" in result.output


def test_db_seed_permite_force_fuera_de_desarrollo(app, monkeypatch):
    """`--force` es la autorización explícita para sembrar fuera de testing."""
    monkeypatch.setattr("cacao_accounting.config.TESTING_MODE", False)
    llamadas = []

    def fake_dev_data():
        llamadas.append(True)

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", fake_dev_data)
    monkeypatch.setattr(cli, "_demo_seed_presente", lambda: False)
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)

    result = CliRunner().invoke(cli.db_seed, ["--force"])

    assert result.exit_code == 0
    assert llamadas == [True]
    assert "Datos de ejemplo insertados." in result.output
