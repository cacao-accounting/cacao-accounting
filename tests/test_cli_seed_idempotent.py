# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2168: `cacaoctl db seed` declara el estado del seed demo con una señal.

La señal de seed completo solo se persiste cuando `dev_data` termina sin
errores; una carga parcial o una entidad CACAO preexistente no declaran éxito
ni reanudan la carga duplicando etapas ya aplicadas.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from cacao_accounting import cli
from cacao_accounting.database import CacaoConfig, Entity, database
from cacao_accounting.datos.dev import DEMO_SEED_KEY, marcar_seed_demo_completo, seed_demo_completo


def _limpiar_estado_demo(app) -> None:
    """Retira la entidad demo y la señal para aislar cada prueba."""
    with app.app_context():
        for registro in database.session.execute(database.select(CacaoConfig).filter_by(key=DEMO_SEED_KEY)).scalars().all():
            database.session.delete(registro)
        entidad = database.session.execute(database.select(Entity).filter_by(code="CACAO")).scalar_one_or_none()
        if entidad is not None:
            database.session.delete(entidad)
        database.session.commit()


@pytest.fixture
def semilla_limpia(app):
    """Aísla el estado demo (entidad CACAO y señal) por prueba."""
    _limpiar_estado_demo(app)
    yield app
    _limpiar_estado_demo(app)


def _sembrar_entidad_demo() -> None:
    """Crea la entidad demo CACAO en la base actual."""
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


def test_db_seed_es_idempotente_con_seed_completo(semilla_limpia, monkeypatch):
    """Un seed ya completado informa que está aplicado y no recarga datos."""
    with semilla_limpia.app_context():
        _sembrar_entidad_demo()
        marcar_seed_demo_completo()

    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: semilla_limpia)

    def fail_if_called():
        raise AssertionError("dev_data no debe ejecutarse si el seed ya está completo")

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", fail_if_called)

    result = CliRunner().invoke(cli.db_seed)

    assert result.exit_code == 0
    assert "ya están aplicados" in result.output


def test_db_seed_rechaza_entidad_demo_sin_semilla_completa(semilla_limpia, monkeypatch):
    """Seed parcial o entidad CACAO preexistente: ni éxito falso ni duplicación."""
    with semilla_limpia.app_context():
        _sembrar_entidad_demo()

    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: semilla_limpia)

    def fail_if_called():
        raise AssertionError("dev_data no debe ejecutarse sobre un estado ambiguo")

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", fail_if_called)

    result = CliRunner().invoke(cli.db_seed)

    assert result.exit_code == 1
    assert "señal de semilla completa" in result.output
    with semilla_limpia.app_context():
        assert not seed_demo_completo()


def test_db_seed_no_marca_completo_cuando_dev_data_falla(semilla_limpia, monkeypatch):
    """Un fallo durante la carga deja la base sin la señal de éxito."""
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: semilla_limpia)

    def dev_data_que_falla():
        raise ValueError("fallo simulado en el seed")

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", dev_data_que_falla)

    result = CliRunner().invoke(cli.db_seed)

    assert result.exit_code == 1
    assert "No fue posible insertar los datos de ejemplo" in result.output
    with semilla_limpia.app_context():
        assert not seed_demo_completo()


def test_db_seed_permite_force_fuera_de_desarrollo(semilla_limpia, monkeypatch):
    """`--force` es la autorización explícita para sembrar fuera de testing."""
    monkeypatch.setattr("cacao_accounting.config.TESTING_MODE", False)
    llamadas = []

    def fake_dev_data():
        llamadas.append(True)
        marcar_seed_demo_completo()

    monkeypatch.setattr("cacao_accounting.datos.dev.dev_data", fake_dev_data)
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: semilla_limpia)

    result = CliRunner().invoke(cli.db_seed, ["--force"])

    assert result.exit_code == 0
    assert llamadas == [True]
    assert "Datos de ejemplo insertados." in result.output
    with semilla_limpia.app_context():
        assert seed_demo_completo()


def test_marcar_seed_demo_completo_es_idempotente(semilla_limpia):
    """Repetir la señal no crea registros duplicados."""
    with semilla_limpia.app_context():
        marcar_seed_demo_completo()
        marcar_seed_demo_completo()

        filas = database.session.execute(database.select(CacaoConfig).filter_by(key=DEMO_SEED_KEY)).scalars().all()
        assert len(filas) == 1
        assert seed_demo_completo()


def test_dev_data_marca_el_seed_completo(semilla_limpia, monkeypatch):
    """`dev_data` persiste la señal al terminar ambas etapas."""
    from cacao_accounting.datos import dev as modulo

    orden = []

    def fake_master_data():
        orden.append("master")

    def fake_transacciones():
        orden.append("transacciones")

    monkeypatch.setattr(modulo, "master_data", fake_master_data)
    monkeypatch.setattr(modulo, "transacciones", fake_transacciones)

    with semilla_limpia.app_context():
        modulo.dev_data()

        assert orden == ["master", "transacciones"]
        assert seed_demo_completo()
