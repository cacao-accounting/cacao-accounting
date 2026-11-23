# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1967: un fallo de persistencia no deja archivos huérfanos."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def test_fallo_de_confirmacion_elimina_el_archivo(app, monkeypatch):
    """Si el commit falla tras mover el archivo, no queda copia física."""
    from cacao_accounting import attachment_service

    monkeypatch.setattr(attachment_service, "_ensure_cloud_mode", lambda: None)
    carpeta = Path(tempfile.mkdtemp())
    monkeypatch.setattr(attachment_service, "_get_upload_folder", lambda: str(carpeta))

    origen = carpeta / "origen.txt"
    origen.write_text("contenido", encoding="utf-8")
    from cacao_accounting.attachment_service import ValidatedUpload

    upload = ValidatedUpload(
        filename="origen.txt",
        temp_path=str(origen),
        size=9,
        mime_type="text/plain",
        sha256="0" * 64,
    )
    monkeypatch.setattr(attachment_service.database.session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    with app.app_context():
        with pytest.raises(Exception):
            attachment_service.store_attachment(
                reference_type="sales_invoice", reference_id="doc-1", upload=upload, commit=True
            )

    restantes = [p for p in os.listdir(carpeta) if p != "origen.txt"]
    assert restantes == []
