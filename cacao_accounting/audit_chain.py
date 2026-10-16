# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cadena de hashes SHA-256 sobre ``audit_trail`` para detección de manipulación.

Cada fila nueva de ``audit_trail`` calcula ``payload_hash = sha256(payload)``
sobre su contenido y registra ``prev_hash`` igual al ``payload_hash`` de la
fila precedente. La verificación recalcula el hash de cada fila y valida el
enlace con la fila previa, por lo que editar una fila histórica, insertar
evidencia falsa o eliminar del medio la cadena queda detectado en
``verify_audit_trail_chain()``.

Limitaciones aceptadas por diseño mínimo:

- Escritores concurrentes en PostgreSQL se serializan con un advisory lock
  transaccional, incluso cuando la cadena todavía está vacía.
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
# v1 (filas heredadas): el payload no ata la identidad de la propia fila, por
# lo que una fila movida a otra posición queda indistinguible. v2 la incluye.
V1_FIELDS = (
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
CHAIN_HASH_VERSION = 2
_CHAIN_TAIL_INFO_KEY = "cacao_audit_chain_pending_tail"
_V2_FIELDS = ("id",) + V1_FIELDS

# Alias histórico compatibles con lecturas del módulo originales.
_CHAIN_FIELDS = V1_FIELDS


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


def _hash_fields(version: int | None) -> tuple[str, ...]:
    """Select the canonical field set for the chain hash version."""
    return _V2_FIELDS if version == CHAIN_HASH_VERSION else V1_FIELDS


def _row_hash_version(source: Any, explicit: int | None) -> int | None:
    """Resolve the hash version for a row: explicit > stored > legacy (v1).

    Las filas nuevas fijan ``hash_version=2`` al momento de estampar; las
    filas heredadas sin columna quedan verificadas con el formato v1, de
    modo que la estrategia es compatible con datos existentes.
    """
    if explicit is not None:
        return explicit
    if isinstance(source, Mapping):
        value = source.get("hash_version")
    else:
        value = getattr(source, "hash_version", None)
    return value


def compute_payload_hash(source: Any, *, version: int | None = None) -> str:
    """Devuelve el hash SHA-256 del contenido canónico de una fila de auditoría.

    ``version=2`` (filas nuevas) incluye la identidad de fila en el payload; la
    versión se resuelve de la fila misma para verificar datos existentes sin
    re-escribirlos.
    """
    resolved = _row_hash_version(source, version)
    fields = _hash_fields(resolved)
    if isinstance(source, Mapping):
        raw = {name: source.get(name) for name in fields}
    else:
        raw = {name: getattr(source, name, None) for name in fields}
    payload = _canonical_timestamp(raw["timestamp"]) if raw["timestamp"] is not None else None
    canonical = dict(raw, timestamp=payload)
    rendered = json.dumps(canonical, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _last_chain_hash(connection: Any) -> str | None:
    """Return the terminal hash by link topology, independent of row ids."""
    successor = AuditTrail.__table__.alias("audit_chain_successor")
    has_successor = database.select(successor.c.id).where(successor.c.prev_hash == AuditTrail.payload_hash).exists()
    heads = (
        connection.execute(
            database.select(AuditTrail.payload_hash).where(AuditTrail.payload_hash.is_not(None), ~has_successor).limit(2)
        )
        .scalars()
        .all()
    )
    if len(heads) > 1:
        raise RuntimeError("La cadena de auditoría tiene más de una cabeza terminal.")
    return heads[0] if heads else None


def _serialize_chain_head(connection: Any) -> None:
    """Serializa escritores concurrentes del encabezado de la cadena.

    Un advisory lock transaccional serializa incluso el primer escritor,
    cuando la cadena está vacía. El bloqueo de fila sobre la cabeza permanece
    como defensa adicional. Este mecanismo es específico de PostgreSQL;
    SQLite serializa escritores localmente.
    """
    dialect = getattr(getattr(connection, "dialect", None), "name", "")
    if dialect != "postgresql":
        return
    connection.exec_driver_sql("SELECT pg_advisory_xact_lock(481239, 926)")
    successor = AuditTrail.__table__.alias("audit_chain_successor")
    has_successor = database.select(successor.c.id).where(successor.c.prev_hash == AuditTrail.payload_hash).exists()
    connection.execute(
        database.select(AuditTrail.id).where(AuditTrail.payload_hash.is_not(None), ~has_successor).limit(1).with_for_update()
    ).all()


def _chain_head_after_lock(connection: Any) -> str | None:
    """Devuelve el ``payload_hash`` de la cabeza esperando el bloqueo previo."""
    _serialize_chain_head(connection)
    return _last_chain_hash(connection)


def _pending_chain_tail(connection: Any) -> str | None:
    """Return the tail already reserved by writes in the current flush."""
    transaction = connection.get_transaction()
    cached = connection.info.get(_CHAIN_TAIL_INFO_KEY)
    if transaction is not None and cached is not None and cached[0] is transaction:
        return cached[1]
    tail = _chain_head_after_lock(connection)
    connection.info[_CHAIN_TAIL_INFO_KEY] = (connection.get_transaction(), tail)
    return tail


def stamp_audit_values(connection: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Adjunta la cadena de hashes a un INSERT Core contra ``audit_trail``.

    Recibe el diccionario de columnas que el servicio de control interno
    prepara antes de ejecutar el INSERT y lo completa ``in place`` con
    ``prev_hash`` y ``payload_hash``.
    """
    values.setdefault("id", obtiene_texto_unico())
    if values.get("timestamp") is None:
        values["timestamp"] = datetime.now(timezone.utc)
    values["hash_version"] = CHAIN_HASH_VERSION
    values["prev_hash"] = _pending_chain_tail(connection)
    values["payload_hash"] = compute_payload_hash(values)
    connection.info[_CHAIN_TAIL_INFO_KEY] = (connection.get_transaction(), values["payload_hash"])
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
    entry.hash_version = CHAIN_HASH_VERSION
    entry.prev_hash = _pending_chain_tail(connection)
    entry.payload_hash = compute_payload_hash(entry)
    connection.info[_CHAIN_TAIL_INFO_KEY] = (connection.get_transaction(), entry.payload_hash)


def chain_pending_rows(session: Any) -> None:
    """Encadena las filas auditadas pendientes de la sesión en un flush.

    Debe invocarse desde ``before_flush``: ordena las filas por ``id`` (ULID
    monótonico), toma el hash final visible en la base de datos al inicio del
    flush y enlaza cada fila nueva con la anterior de su propio lote.
    El cálculo es idempotente: si el flush se deshace (rollback) y las filas
    se reintentan, la cadena se recalcula con la cola vigente.
    """
    connection = session.connection()
    connection.info.pop(_CHAIN_TAIL_INFO_KEY, None)
    pending = [target for target in session.new if isinstance(target, AuditTrail)]
    if not pending:
        return
    tail = _chain_head_after_lock(connection)
    connection.info[_CHAIN_TAIL_INFO_KEY] = (connection.get_transaction(), tail)
    for row in pending:
        if row.id is None:
            row.id = obtiene_texto_unico()
        if row.timestamp is None:
            row.timestamp = datetime.now(timezone.utc)
    tail = connection.info[_CHAIN_TAIL_INFO_KEY][1]
    for row in sorted(pending, key=lambda target: str(target.id)):
        row.prev_hash = tail
        row.hash_version = CHAIN_HASH_VERSION
        row.payload_hash = compute_payload_hash(row)
        tail = row.payload_hash
    connection.info[_CHAIN_TAIL_INFO_KEY] = (connection.get_transaction(), tail)


def _payload_hash_issues(rows: list[Any]) -> list[dict[str, str]]:
    """Return rows whose canonical payload no longer matches its stored hash."""
    return [
        {"row": str(row.id), "finding": "payload_tampered"}
        for row in rows
        if compute_payload_hash(row, version=row.hash_version) != row.payload_hash
    ]


def _walk_chain(root: Any, children: dict[str | None, list[Any]]) -> tuple[set[str], list[Any]]:
    """Walk one chain branch, returning visited ids and unexpected branches."""
    visited: set[str] = set()
    branches: list[Any] = []
    current = root
    while current is not None and str(current.id) not in visited:
        visited.add(str(current.id))
        successors = children.get(current.payload_hash, [])
        if len(successors) != 1:
            branches.extend(row for row in successors if str(row.id) not in visited)
            break
        current = successors[0]
    return visited, branches


def _chain_link_issues(rows: list[Any]) -> list[dict[str, str]]:
    """Return branch, extra-root, and orphan findings for a linked chain."""
    children: dict[str | None, list[Any]] = {}
    for row in rows:
        children.setdefault(row.prev_hash, []).append(row)
    roots = sorted(children.get(None, []), key=lambda row: str(row.id))
    issues = [{"row": str(row.id), "finding": "chain_break"} for row in roots[1:]]
    visited: set[str] = set()
    if roots:
        visited, branches = _walk_chain(roots[0], children)
        issues.extend({"row": str(row.id), "finding": "chain_break"} for row in branches)
    reported = {issue["row"] for issue in issues}
    issues.extend(
        {"row": str(row.id), "finding": "chain_break"}
        for row in rows
        if str(row.id) not in visited and str(row.id) not in reported
    )
    return issues


def verify_audit_trail_chain() -> list[dict[str, str]]:
    """Verifica la integridad del ``audit_trail`` y devuelve los hallazgos.

    Requiere app context. Devuelve ``[]`` si la cadena es íntegra. Excluye las
    filas previas al despliegue del mecanismo (``payload_hash`` nulo) porque
    forman la cola heredada sobre la que inicia la cadena. Las filas v1 se
    recalculan con su formato heredado (sin identidad de fila); las v2 atan la
    identidad de la fila a su contenido, así que mover una fila a otra posición
    o duplicar su payload queda detectado.
    """
    rows = database.session.scalars(database.select(AuditTrail).order_by(AuditTrail.id.asc())).all()
    hashed_rows = [row for row in rows if row.payload_hash is not None]
    issues = _payload_hash_issues(hashed_rows) + _chain_link_issues(hashed_rows)
    issues.sort(key=lambda issue: (issue["row"], issue["finding"]))
    return issues
