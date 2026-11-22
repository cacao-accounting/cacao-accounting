# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1853: una sola configuración efectiva de mypy.

`.mypy.ini` tiene prioridad sobre `pyproject.toml`; mantener ambos hacía que
los flags del proyecto se ignoraran en CI. La configuración vive solo en
`pyproject.toml`.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_no_existe_config_competidora_de_mypy():
    """No debe quedar `.mypy.ini` que sombree pyproject."""
    assert not (RAIZ / ".mypy.ini").exists()


def test_pyproject_conserva_los_flags_del_proyecto():
    """La configuración efectiva mantiene los flags que antes vivían en .mypy.ini."""
    configuracion = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    mypy = configuracion["tool"]["mypy"]

    assert mypy["ignore_missing_imports"] is True
    assert mypy["show_error_codes"] is True
    assert mypy["python_version"] == "3.12"
    assert mypy["follow_imports"] == "silent"
