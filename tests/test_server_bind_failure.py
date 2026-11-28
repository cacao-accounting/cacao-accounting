# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1905: un fallo de bind del servidor termina con salida no cero."""

from __future__ import annotations

import pytest

from cacao_accounting import server as server_module


def test_fallo_de_bind_propaga_salida_no_cero(app, monkeypatch):
    """Si Waitress no puede enlazar, server() no retorna normalmente."""
    from cacao_accounting.database import helpers as db_helpers

    monkeypatch.setattr(server_module, "serve", lambda *a, **k: (_ for _ in ()).throw(OSError("ocupado")))
    monkeypatch.setattr(db_helpers, "verifica_coneccion_db", lambda app: True)
    monkeypatch.setattr(db_helpers, "usuarios_creados", lambda: True)

    with pytest.raises(SystemExit) as salida:
        server_module.server()

    assert salida.value.code == 1
