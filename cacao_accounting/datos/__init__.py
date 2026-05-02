# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo para alimentar la base de datos con información por defecto."""

from cacao_accounting.datos.base import base_data
from cacao_accounting.datos.dev import dev_data

__all__ = (
    "dev_data",
    "base_data",
)
