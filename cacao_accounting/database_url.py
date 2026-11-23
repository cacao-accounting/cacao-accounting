# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Construcción segura de la URL de base de datos desde componentes."""

from __future__ import annotations

from urllib.parse import quote


def database_url_from_parts(*, user: str, password: str, host: str, port: str, name: str) -> str:
    """Compone una URL PostgreSQL codificando cada componente.

    Interpolar la contraseña cruda en una URI rompe la conexión cuando
    contiene caracteres reservados (``@``, ``:``, ``/``, ``%``, etc.).
    """
    return (
        "postgresql+psycopg://"
        f"{quote(str(user), safe='')}:{quote(str(password), safe='')}"
        f"@{host}:{port}/{quote(str(name), safe='')}"
    )
