# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2079: el hash de auditoría conserva los formatos heredado (v1) y actual (v2).

La versión v1 no ata la identidad de la fila; v2 incluye el ``id``. La
verificación debe resolver la versión desde la fila para no reescribir
evidencia histórica.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from cacao_accounting.audit_chain import CHAIN_HASH_VERSION, compute_payload_hash


def _fila(**overrides) -> SimpleNamespace:
    """Construye una fila de auditoría con todos los campos del payload."""
    valores = {
        "id": "AUD-1",
        "document_type": "sales_invoice",
        "document_id": "INV-1",
        "document_no": "FAC-1",
        "company": "cacao",
        "action": "submit",
        "actor_user_id": "user-1",
        "actor_name": "Usuario",
        "before_json": None,
        "after_json": "{}",
        "changes_json": None,
        "comment": "Aprobada",
        "source_module": "sales",
        "ip_address": "127.0.0.1",
        "user_agent": "pytest",
        "timestamp": datetime(2026, 5, 12, 15, 30, 0),
    }
    valores.update(overrides)
    return SimpleNamespace(**valores)


def test_hash_v1_ignora_identidad_y_v2_la_incluye():
    """Cambiar el id no altera el hash v1, pero sí el hash v2."""
    primera = _fila(id="AUD-A")
    segunda = _fila(id="AUD-B")

    assert compute_payload_hash(primera, version=1) == compute_payload_hash(segunda, version=1)
    assert compute_payload_hash(primera, version=2) != compute_payload_hash(segunda, version=2)


def test_hash_respeta_la_version_persistida_en_la_fila():
    """La versión guardada en la fila decide el formato del hash."""
    actual = _fila(hash_version=CHAIN_HASH_VERSION)
    heredada = _fila(hash_version=1)
    sin_columna = _fila()

    assert compute_payload_hash(actual) == compute_payload_hash(actual, version=2)
    assert compute_payload_hash(heredada) == compute_payload_hash(heredada, version=1)
    assert compute_payload_hash(sin_columna) == compute_payload_hash(sin_columna, version=1)


def test_hash_detecta_alteracion_del_contenido():
    """Un cambio en el contenido cambia el hash en ambas versiones."""
    original = _fila()
    alterada = _fila(comment="Comentario alterado")

    assert compute_payload_hash(original, version=1) != compute_payload_hash(alterada, version=1)
    assert compute_payload_hash(original, version=2) != compute_payload_hash(alterada, version=2)


def test_hash_acepta_mapeos_con_la_misma_version():
    """El mismo payload en mapeo o atributo produce el mismo hash."""
    fila = _fila()
    como_mapeo = {campo: getattr(fila, campo) for campo in vars(fila)}

    assert compute_payload_hash(como_mapeo) == compute_payload_hash(fila)
