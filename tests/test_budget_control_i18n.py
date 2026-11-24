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


def _habilitar_admin(app) -> None:
    """Garantiza el módulo administrativo habilitado."""
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            modulo.enabled = True
        database.session.commit()


def _configurar(app, accion: str, habilitado: str = "1") -> None:
    """Persiste la configuración de control para cacao."""
    with app.app_context():
        for clave, valor in (
            ("budget_control_enabled_cacao", habilitado),
            ("budget_control_action_cacao", accion),
        ):
            registro = database.session.execute(database.select(CacaoConfig).filter_by(key=clave)).scalar_one_or_none()
            if registro is None:
                database.session.add(CacaoConfig(key=clave, value=valor))
            else:
                registro.value = valor
        database.session.commit()


def _limpiar(app) -> None:
    """Elimina las claves de configuración usadas por la prueba."""
    with app.app_context():
        database.session.execute(
            database.delete(CacaoConfig).where(
                CacaoConfig.key.in_(["budget_control_enabled_cacao", "budget_control_action_cacao"])
            )
        )
        database.session.commit()


def test_las_acciones_se_muestran_traducidas(app, entorno_contable, authenticated_client):
    """La tabla no imprime los códigos notify/block/do_nothing en crudo."""
    del entorno_contable
    _habilitar_admin(app)
    try:
        for accion, etiqueta in (("block", "Bloquear"), ("notify", "Notificar"), ("do_nothing", "No hacer nada")):
            _configurar(app, accion)
            response = authenticated_client("admin").get("/settings/budget-control?company=cacao")

            assert response.status_code == 200
            cuerpo = response.get_data(as_text=True)
            assert etiqueta in cuerpo
            assert f'<span class="text-monospace">{accion}</span>' not in cuerpo
            assert f"</i>{accion}</span>" not in cuerpo
    finally:
        _limpiar(app)
