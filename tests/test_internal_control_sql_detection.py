# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Contrato del detector de SQL crudo sobre tablas protegidas.

El guard de controles internos bloquea escrituras textuales a tablas de
evidencia. El detector leía ``roles_access.delete`` (una columna) como un
``DELETE ... FROM roles_access``, por lo que cualquier ``SELECT`` que
proyectara las columnas ``update`` o ``delete`` de ``RolesAccess`` abortaba
con ``ValueError``. En producción esto rompía la página inicial justo
después del setup inicial, porque las plantillas resuelven permisos.
"""

from __future__ import annotations

import pytest

from cacao_accounting.internal_control_sql import raw_sql_mutates_protected_table

PROTEGIDAS = {"roles_access", "gl_entry", "audit_trail"}


@pytest.mark.parametrize(
    "statement",
    [
        # Columnas llamadas como palabras DML no son instrucciones.
        "SELECT roles_access.delete AS d, roles_access.update AS u FROM roles_access",
        "SELECT roles_access.rol_id, roles_access.update FROM roles_access WHERE rol_id = '1'",
        "SELECT * FROM roles_access",
        "SELECT gl_entry.debit FROM gl_entry",
    ],
)
def test_lecturas_no_se_confunden_con_escrituras(statement):
    """Un SELECT nunca se interpreta como escritura aunque proyecte esas columnas."""
    assert raw_sql_mutates_protected_table(statement, PROTEGIDAS, "postgresql") is False


@pytest.mark.parametrize(
    ("statement", "dialecto"),
    [
        ("DELETE FROM roles_access WHERE id = 1", "postgresql"),
        ("UPDATE roles_access SET access = true", "postgresql"),
        ("UPDATE public.roles_access SET access = true", "postgresql"),
        ("INSERT INTO gl_entry (id) VALUES (1)", "postgresql"),
        ("INSERT gl_entry (id) VALUES (1)", "postgresql"),
        ("TRUNCATE TABLE audit_trail", "postgresql"),
        ("WITH x AS (SELECT 1) DELETE FROM gl_entry WHERE 1=1", "postgresql"),
        ("REPLACE INTO gl_entry (id) VALUES (1)", "mysql"),
        ("DELETE ra FROM roles_access ra WHERE 1=1", "mysql"),
    ],
)
def test_escrituras_siguen_bloqueadas(statement, dialecto):
    """Las instrucciones DML reales siguen detectándose tras el ajuste."""
    assert raw_sql_mutates_protected_table(statement, PROTEGIDAS, dialecto) is True
