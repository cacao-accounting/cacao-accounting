# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Escritura atómica de valores de configuración clave/valor.

`CacaoConfig.key` es único; la escritura usa el upsert nativo de cada motor
para que dos procesos no dupliquen la clave ni dejen valores divergentes
(#1697). No confirma la transacción: el flujo llamador conserva el control.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cacao_accounting.database import CacaoConfig, database


def set_config_value(key: str, value: str) -> None:
    """Inserta o actualiza una clave de configuración de forma atómica."""
    table = CacaoConfig.__table__
    dialect = database.session.get_bind().dialect.name
    match dialect:
        case "sqlite":
            statement: Any = sqlite_insert(table).values(id=_new_id(), key=key, value=value)
            statement = statement.on_conflict_do_update(index_elements=[table.c.key], set_={"value": value})
        case "postgresql":
            statement = postgresql_insert(table).values(id=_new_id(), key=key, value=value)
            statement = statement.on_conflict_do_update(index_elements=[table.c.key], set_={"value": value})
        case "mysql" | "mariadb":
            statement = mysql_insert(table).values(id=_new_id(), key=key, value=value)
            statement = statement.on_duplicate_key_update(value=value)
        case _:
            _set_config_value_portable(key, value)
            return
    database.session.execute(statement)


def _new_id() -> str:
    """Genera un ULID para una fila nueva de configuración."""
    from cacao_accounting.database import obtiene_texto_unico

    return obtiene_texto_unico()


def _set_config_value_portable(key: str, value: str) -> None:
    """Fallback select/insert/update para motores sin upsert soportado."""
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    if record is None:
        database.session.add(CacaoConfig(key=key, value=value))
        return
    record.value = value
