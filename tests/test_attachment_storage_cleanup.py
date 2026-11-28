# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""#1967: compensaci?n y reconciliaci?n de limpieza de adjuntos."""

from __future__ import annotations

import json
import os
from pathlib import Path
from io import BytesIO

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.datastructures import FileStorage

from cacao_accounting import create_app
from cacao_accounting.attachment_service import (
    ValidatedUpload,
    delete_attachment,
    reconcile_pending_attachment_cleanups,
    store_attachment,
    upload_attachment,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, CompanyParty, Currency, Entity, File, Modules, Party, User, database


def _app(tmp_path: Path):
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "MODO_ESCRITORIO": False,
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    with app.app_context():
        database.create_all()
        party = Party(code="PROV-1", name="Proveedor", is_supplier=True, is_customer=False)
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J1",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="purchases", default=False, enabled=True),
                party,
                User(
                    id="admin-user",
                    user="admin",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
        database.session.commit()
    return app


def test_fallo_de_confirmacion_elimina_el_archivo(tmp_path, monkeypatch):
    """Si el commit falla tras mover el archivo, no queda copia f?sica."""
    app = _app(tmp_path)
    from cacao_accounting import attachment_service

    monkeypatch.setattr(attachment_service, "_ensure_cloud_mode", lambda: None)
    carpeta = Path(app.config["UPLOAD_FOLDER"])
    carpeta.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(attachment_service, "_get_upload_folder", lambda: str(carpeta))
    origen = carpeta / "origen.txt"
    origen.write_text("contenido", encoding="utf-8")
    upload = ValidatedUpload(filename="origen.txt", temp_path=str(origen), size=9, mime_type="text/plain", sha256="0" * 64)
    monkeypatch.setattr(attachment_service.database.session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    with app.app_context():
        with pytest.raises(RuntimeError):
            store_attachment(reference_type="supplier", reference_id="PROV-1", upload=upload, commit=True)

    assert [p for p in os.listdir(carpeta) if p != "origen.txt"] == []


def test_reconciliacion_avanza_mas_alla_de_eventos_resueltos(tmp_path, monkeypatch):
    """#1967: una cola de eventos resueltos no bloquea fallos posteriores."""
    app = _app(tmp_path)
    import cacao_accounting.attachment_service as service

    def _upload(name: str):
        return upload_attachment(
            "supplier",
            "PROV-1",
            FileStorage(stream=BytesIO(b"%PDF-1.4\n%%EOF"), filename=name),
            user_id="admin-user",
        )

    with app.app_context():
        monkeypatch.setattr(service, "_remove_file", lambda path: False)
        for index in range(3):
            upload = _upload(f"old-{index}.pdf")
            delete_attachment(upload["file_id"], "supplier", "PROV-1", user_id="admin-user")

    monkeypatch.setattr(service, "_remove_file", lambda path: (os.remove(path), True)[1])
    with app.app_context():
        resolved = reconcile_pending_attachment_cleanups(actor_id="admin-user", limit=10)
        assert resolved["resolved"] == 3
        assert resolved["pending"] == 0

    with app.app_context():
        monkeypatch.setattr(service, "_remove_file", lambda path: False)
        pending = _upload("pending.pdf")
        delete_attachment(pending["file_id"], "supplier", "PROV-1", user_id="admin-user")

    monkeypatch.setattr(service, "_remove_file", lambda path: (os.remove(path), True)[1])
    with app.app_context():
        retry = reconcile_pending_attachment_cleanups(actor_id="admin-user", limit=1)
        assert retry["resolved"] == 1
        assert retry["pending"] == 0
        assert retry["resolved_ids"] == [pending["file_id"]]


def test_unlink_fallido_reporta_pendiente_y_reconciliacion_resuelve(tmp_path, monkeypatch):
    """Unlink fallido queda auditado; reconciliación lo resuelve sin exponer ruta."""
    app = _app(tmp_path)
    import cacao_accounting.attachment_service as service

    with app.app_context():
        upload = upload_attachment(
            "supplier",
            "PROV-1",
            FileStorage(stream=BytesIO(b"%PDF-1.4\n%%EOF"), filename="f.pdf"),
            user_id="admin-user",
        )
        file_path = database.session.get(File, upload["file_id"]).file_path
        monkeypatch.setattr(service, "_remove_file", lambda path: False)
        outcome = delete_attachment(upload["file_id"], "supplier", "PROV-1", user_id="admin-user")

        assert outcome["deleted"] is True
        assert outcome["logical_deleted"] is True
        assert outcome["file_removed"] is False
        assert outcome["pending_cleanup"] == [file_path]
        assert database.session.get(File, upload["file_id"]) is None

        failed = database.session.execute(
            database.select(AuditTrail).filter_by(document_id="PROV-1", action="cleanup_failed")
        ).scalar_one()
        assert json.loads(failed.after_json)["file_path"] == file_path

    monkeypatch.setattr(service, "_remove_file", lambda p: (os.remove(p), True)[1])
    with app.app_context():
        result = reconcile_pending_attachment_cleanups(actor_id="admin-user")
        assert result["resolved"] == 1
        assert result["pending"] == 0
        assert result["resolved_ids"]
        assert "file_path" not in str(result)
        resolved = database.session.execute(
            database.select(AuditTrail).filter_by(document_id="PROV-1", action="cleanup_resolved")
        ).scalar_one()
        payload = json.loads(resolved.after_json)
        assert payload["result"] == "resolved"
        assert "file_path" not in payload
        assert not os.path.exists(file_path)
