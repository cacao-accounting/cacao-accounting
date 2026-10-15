# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Integridad del ``audit_trail`` mediante cadena de hashes SHA-256."""

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.audit_chain import compute_payload_hash, verify_audit_trail_chain
from cacao_accounting.audit_trail_service import log_create
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, database


@pytest.fixture()
def app_ctx():
    """App de escritorio sin enforcement, con la cadena activa en ambos modos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": True,
            "INTERNAL_CONTROLS_ENFORCE": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.commit()
        yield application
        database.session.rollback()
        database.session.remove()
        database.engine.dispose()


@pytest.fixture()
def cloud_ctx():
    """App Cloud con enforcement de controles y las rutas Core de evidencia."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import User

        database.session.add(User(id="actor", user="actor", password=b"x", active=True))
        database.session.commit()
        yield application
        database.session.rollback()
        database.session.remove()
        database.engine.dispose()


def _rows():
    return database.session.scalars(database.select(AuditTrail).order_by(AuditTrail.id.asc())).all()


def test_orm_rows_are_hash_chained(app_ctx):
    """Cada fila referencia el payload_hash de la fila precedente."""
    log_create({"id": "doc1", "document_type": "test", "company_id": "co"})
    log_create({"id": "doc2", "document_type": "test", "company_id": "co"})
    database.session.flush()
    rows = _rows()
    assert len(rows) == 2
    assert rows[0].prev_hash is None
    assert rows[1].prev_hash == rows[0].payload_hash
    for row in rows:
        assert len(row.payload_hash) == 64
        assert compute_payload_hash(row) == row.payload_hash
    assert verify_audit_trail_chain() == []


def test_cloud_core_rows_continue_the_chain(cloud_ctx):
    """La ruta Core del control interno encadena con las filas ORM previas."""
    log_create({"id": "orm-doc", "document_type": "test", "company_id": "co"})
    database.session.flush()
    from cacao_accounting.database import Roles

    database.session.add(Roles(name="audited", note="Original"))
    database.session.commit()
    rows = _rows()
    assert rows[-1].document_type == "roles"
    assert rows[-1].prev_hash == rows[-2].payload_hash
    assert verify_audit_trail_chain() == []


def test_row_update_is_detected(app_ctx):
    """Editar una fila histórica rompe su hash payload."""
    log_create({"id": "doc", "document_type": "test", "company_id": "co"})
    database.session.flush()
    database.session.connection().exec_driver_sql("UPDATE audit_trail SET comment = 'tampered'")
    database.session.expire_all()
    findings = verify_audit_trail_chain()
    assert len(findings) == 1
    assert findings[0]["finding"] == "payload_tampered"


def test_middle_row_deletion_is_detected(app_ctx):
    """Eliminar una fila del medio rompe el enlace con la fila siguiente."""
    log_create({"id": "doc1", "document_type": "test", "company_id": "co"})
    log_create({"id": "doc2", "document_type": "test", "company_id": "co"})
    database.session.commit()
    first = database.session.scalars(database.select(AuditTrail).order_by(AuditTrail.id.asc())).first()
    database.session.delete(first)
    database.session.commit()
    findings = verify_audit_trail_chain()
    assert findings and findings[0]["finding"] == "chain_break"


def test_raw_update_via_text_statement_is_detected(app_ctx):
    """El UPDATE textual de un tamper queda detectado."""
    log_create({"id": "doc", "document_type": "test", "company_id": "co"})
    database.session.flush()
    database.session.connection().execute(text("UPDATE audit_trail SET actor_name = 'fake'"))
    database.session.expire_all()
    findings = verify_audit_trail_chain()
    assert findings and findings[0]["finding"] == "payload_tampered"


def test_legacy_rows_without_hash_are_tolerated(app_ctx):
    """Las filas previas al despliegue inician la cadena sin falsos positivos."""
    database.session.execute(database.insert(AuditTrail).values(document_type="legacy", document_id="old", action="created"))
    database.session.commit()
    log_create({"id": "doc", "document_type": "test", "company_id": "co"})
    database.session.flush()
    chained = [row for row in _rows() if row.payload_hash is not None]
    assert len(chained) == 1
    assert verify_audit_trail_chain() == []


def test_new_rows_are_versioned_with_row_identity(app_ctx):
    """El hash v2 incluye la identidad de la fila y la versión queda estampada."""
    from cacao_accounting.audit_chain import CHAIN_HASH_VERSION

    log_create({"id": "doc1", "document_type": "test", "company_id": "co"})
    database.session.commit()
    rows = _rows()
    assert all(row.hash_version == CHAIN_HASH_VERSION for row in rows)
    # La identidad de fila es parte del payload: la misma evidencia con otro id
    # produce un hash distinto, atando la fila a su posición.
    a = rows[0]
    clone = AuditTrail(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAV-C",
        document_type=a.document_type,
        document_id=a.document_id,
        action=a.action,
        timestamp=a.timestamp,
        hash_version=CHAIN_HASH_VERSION,
    )
    assert compute_payload_hash(a) != compute_payload_hash(clone)


def test_legacy_v1_rows_are_verified_with_legacy_format(app_ctx):
    """Filas v1 (hash_version NULL) se verifican sin re-escribir datos."""
    legacy = AuditTrail(document_type="legacy", document_id="old", action="created")
    database.session.add(legacy)
    database.session.flush()
    legacy.prev_hash = None
    legacy.hash_version = None
    legacy.payload_hash = compute_payload_hash(legacy, version=1)
    database.session.commit()
    assert verify_audit_trail_chain() == []


def test_swapped_row_identity_is_detected_in_v2(app_ctx):
    """Mover una fila v2 a otra posición (otro id) rompe su hash payload."""
    log_create({"id": "doc1", "document_type": "test", "company_id": "co"})
    database.session.commit()
    row = _rows()[0]
    database.session.connection().execute(
        text("UPDATE audit_trail SET id = '01ARZ3NDEKTSV4RRFFQ69G5FAV-X' WHERE id = :id"), {"id": row.id}
    )
    database.session.expire_all()
    findings = verify_audit_trail_chain()
    assert findings and findings[0]["finding"] == "payload_tampered"
