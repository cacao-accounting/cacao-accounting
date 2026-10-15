# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cadena de hashes SHA-256 sobre ``audit_trail`` para detección de manipulación.

Cada fila nueva de ``audit_trail`` calcula ``payload_hash = sha256(payload)``
sobre su contenido y registra ``prev_hash`` igual al ``payload_hash`` de la
fila precedente (orden por ``id``, ULID monótonico). La verificación recalcula
el hash de cada fila y valida el enlace con la fila previa, por lo que editar
una fila histórica, insertar evidencia falsa o eliminar del medio la cadena
queda detectado en ``verify_audit_trail_chain()``.

Limitaciones aceptadas por diseño mínimo:

- Escritores concurrentes en PostgreSQL pueden leer el mismo ``prev_hash``
  antes de aterrizar su COMMIT (respuesta de falta (fork) aparente). En SQLite,
  escritor único, no ocurre.
- Los DBA con escritura directa sobre la columna pueden rearmar la cadena;
  lo que protege es que los GRANT/REVOKE de despliegue revocan UPDATE/DELETE
  y que la columna no se recalcula desde la aplicación.
- No cubre ``audit_log``/``approval_action``, solo el ``audit_trail`` central.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from cacao_accounting.database import AuditTrail, database, obtiene_texto_unico

_HASH_LENGTH = 64
_CHAIN_FIELDS = (
    "document_type",
    "document_id",
    "document_no",
    "company",
    "action",
    "actor_user_id",
    "actor_name",
    "before_json",
    "after_json",
    "changes_json",
    "comment",
    "source_module",
    "ip_address",
    "user_agent",
    "timestamp",
)


def _canonical_timestamp(value: Any) -> Any:
    """Devuelve una representación UTC estable del instante almacenado.

    SQLite entrega ``naive`` y PostgreSQL entrega ``aware``; se normaliza al
    instante UTC sin zona para que generación y verificación comparen igual.
    """
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat()
    return value


def compute_payload_hash(source: Any) -> str:
    """Devuelve el hash SHA-256 del contenido canónico de una fila de auditoría."""
    if isinstance(source, Mapping):
        raw = {name: source.get(name) for name in _CHAIN_FIELDS}
    else:
        raw = {name: getattr(source, name, None) for name in _CHAIN_FIELDS}
    payload = _canonical_timestamp(raw["timestamp"]) if raw["timestamp"] is not None else None
    canonical = dict(raw, timestamp=payload)
    rendered = json.dumps(canonical, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _last_chain_hash(connection: Any) -> str | None:
    """Devuelve el ``payload_hash`` de la fila auditada más reciente."""
    return connection.execute(database.select(AuditTrail.payload_hash).order_by(AuditTrail.id.desc()).limit(1)).scalar()


def stamp_audit_values(connection: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Adjunta la cadena de hashes a un INSERT Core contra ``audit_trail``.

    Recibe el diccionario de columnas que el servicio de control interno
    prepara antes de ejecutar el INSERT y lo completa ``in place`` con
    ``prev_hash`` y ``payload_hash``.
    """
    values.setdefault("id", obtiene_texto_unico())
    if values.get("timestamp") is None:
        values["timestamp"] = datetime.now(timezone.utc)
    values["prev_hash"] = _last_chain_hash(connection)
    values["payload_hash"] = compute_payload_hash(values)
    return values


def stamp_audit_entry(connection: Any, entry: Any) -> None:
    """Adjunta la cadena de hashes a una fila ORM pendiente (camino de respaldo).

    Las filas nuevas se encadenan en ``chain_pending_rows`` al inicio del
    flush; en SQLAlchemy 2.0 los INSERT del mismo mapper se agrupan en un solo
    ``executemany``, de modo que durante ``before_insert`` aún no se ven las
    filas hermanas. Este camino cubre inserciones que escapen a ese flujo.
    """
    if entry.payload_hash is not None:
        return
    if entry.id is None:
        entry.id = obtiene_texto_unico()
    if entry.timestamp is None:
        entry.timestamp = datetime.now(timezone.utc)
    entry.prev_hash = _last_chain_hash(connection)
    entry.payload_hash = compute_payload_hash(entry)


def chain_pending_rows(session: Any) -> None:
    """Encadena las filas auditadas pendientes de la sesión en un flush.

    Debe invocarse desde ``before_flush``: ordena las filas por ``id`` (ULID
    monótonico), toma el hash final visible en la base de datos al inicio del
    flush y enlaza cada fila nueva con la anterior de su propio lote.
    El cálculo es idempotente: si el flush se deshace (rollback) y las filas
    se reintentan, la cadena se recalcula con la cola vigente.
    """
    pending = [target for target in session.new if isinstance(target, AuditTrail)]
    if not pending:
        return
    for row in pending:
        if row.id is None:
            row.id = obtiene_texto_unico()
        if row.timestamp is None:
            row.timestamp = datetime.now(timezone.utc)
    tail = _last_chain_hash(session.connection())
    for row in sorted(pending, key=lambda target: str(target.id)):
        row.prev_hash = tail
        row.payload_hash = compute_payload_hash(row)
        tail = row.payload_hash


def verify_audit_trail_chain() -> list[dict[str, str]]:
    """Verifica la integridad del ``audit_trail`` y devuelve los hallazgos.

    Requiere app context. Devuelve ``[]`` si la cadena es íntegra. Excluye las
    filas previas al despliegue del mecanismo (``payload_hash`` nulo) porque
    forman la cola heredada sobre la que inicia la cadena.
    """
    rows = database.session.scalars(database.select(AuditTrail).order_by(AuditTrail.id.asc())).all()
    issues: list[dict[str, str]] = []
    expected_prev: str | None = None
    for row in rows:
        if row.payload_hash is None:
            continue
        if compute_payload_hash(row) != row.payload_hash:
            issues.append({"row": str(row.id), "finding": "payload_tampered"})
        if expected_prev is None:
            if row.prev_hash is not None:
                issues.append({"row": str(row.id), "finding": "chain_break"})
        elif row.prev_hash != expected_prev:
            issues.append({"row": str(row.id), "finding": "chain_break"})
        expected_prev = row.payload_hash
    return issues
