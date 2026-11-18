# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Identidad fiscal global de terceros.

La identificación fiscal se normaliza (mayúsculas, sin espacios, guiones ni
puntos) y es única globalmente; `CompanyParty` solo activa el tercero en una
compañía (#1051).
"""

from __future__ import annotations

import re

from cacao_accounting.database import Party, database


def normalize_tax_id(value: object) -> str | None:
    """Devuelve la clave fiscal normalizada o ``None`` si está vacía."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[\s\-\.]", "", text).upper()
    return normalized or None


def find_party_by_tax_id(tax_id: object, *, exclude_party_id: str | None = None) -> Party | None:
    """Busca un tercero por identidad fiscal normalizada."""
    key = normalize_tax_id(tax_id)
    if not key:
        return None
    query = database.select(Party).where(Party.tax_id_key == key)
    if exclude_party_id:
        query = query.where(Party.id != exclude_party_id)
    return database.session.execute(query).scalars().first()
