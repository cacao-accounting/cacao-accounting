# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1900: importar terceros invalida la caché del Smart Select."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.imports.services import import_service


def test_procesar_documento_invalida_datos_maestros(app, monkeypatch):
    """Tras persistir y confirmar, se invalida smart-select-master-data."""
    invalidados: list[str] = []
    monkeypatch.setattr(import_service, "invalidate_cache", invalidados.append)
    monkeypatch.setattr(import_service.database.session, "commit", lambda: None)

    servicio = import_service.ImportService.__new__(import_service.ImportService)
    monkeypatch.setattr(servicio, "_validate_document_period", lambda *a, **k: None)
    adapter = SimpleNamespace(
        build_document=lambda rows, context: SimpleNamespace(),
        persist_document=lambda doc: None,
    )

    with app.app_context():
        servicio._process_document(adapter, "ref", [{}], {}, SimpleNamespace(), "batch")

    assert "smart-select-master-data" in invalidados
