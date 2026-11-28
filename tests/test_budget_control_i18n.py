# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1963: las acciones del control presupuestario se muestran traducidas."""

from __future__ import annotations

import os

import pytest

from cacao_accounting.database import CacaoConfig, Modules, database

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="El control presupuestario no aplica en modo escritorio.",
)


def _habilitar_admin(app) -> tuple[bool, bool | None]:
    """Habilita admin y devuelve si fue creado y su estado previo."""
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        creado = modulo is None
        anterior = None if creado else modulo.enabled
        if modulo is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            modulo.enabled = True
        database.session.commit()
        return creado, anterior


def _configurar(app, accion: str, habilitado: str = "1") -> dict[str, tuple[bool, str | None]]:
    """Persiste la configuración y devuelve el estado previo de cada clave."""
    previos: dict[str, tuple[bool, str | None]] = {}
    with app.app_context():
        for clave, valor in (
            ("budget_control_enabled_cacao", habilitado),
            ("budget_control_action_cacao", accion),
        ):
            registro = database.session.execute(database.select(CacaoConfig).filter_by(key=clave)).scalar_one_or_none()
            if clave not in previos:
                previos[clave] = (registro is None, None if registro is None else registro.value)
            if registro is None:
                database.session.add(CacaoConfig(key=clave, value=valor))
            else:
                registro.value = valor
        database.session.commit()
    return previos


def _restaurar(app, admin_previo: tuple[bool, bool | None], config_previas: dict[str, tuple[bool, str | None]]) -> None:
    """Restaura exactamente el módulo admin y las claves modificadas."""
    creado, anterior = admin_previo
    with app.app_context():
        for clave, (no_existia, valor) in config_previas.items():
            registro = database.session.execute(database.select(CacaoConfig).filter_by(key=clave)).scalar_one_or_none()
            if registro is not None:
                if no_existia:
                    database.session.delete(registro)
                else:
                    registro.value = valor
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = anterior
        database.session.commit()


def test_las_acciones_se_muestran_traducidas(app, entorno_contable, authenticated_client):
    """La tabla no imprime los códigos notify/block/do_nothing en crudo."""
    del entorno_contable
    admin_previo = _habilitar_admin(app)
    config_previas: dict[str, tuple[bool, str | None]] = {}
    try:
        for accion, etiqueta in (("block", "Bloquear"), ("notify", "Notificar"), ("do_nothing", "No hacer nada")):
            for clave, estado in _configurar(app, accion).items():
                config_previas.setdefault(clave, estado)
            response = authenticated_client("admin").get("/settings/budget-control?company=cacao")

            assert response.status_code == 200
            cuerpo = response.get_data(as_text=True)
            assert etiqueta in cuerpo
            assert f'<span class="text-monospace">{accion}</span>' not in cuerpo
            assert f"</i>{accion}</span>" not in cuerpo
    finally:
        _restaurar(app, admin_previo, config_previas)
