# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1900: importar terceros invalida la caché y el selector ve el registro nuevo."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.database import CompanyParty, Party, database
from cacao_accounting.imports.models import ImportBatch
from cacao_accounting.imports.services import import_service
from cacao_accounting.search_select import search_select


def _lote(compania: str) -> ImportBatch:
    """Crea un lote en proceso válido para el worker."""
    lote = ImportBatch(
        company_id=compania,
        record_type="customer",
        source_format="csv",
        source_filename="clientes.csv",
        import_status=4,
        cancel_requested=False,
    )
    database.session.add(lote)
    database.session.commit()
    return lote


def test_procesar_documento_invalida_y_expone_el_tercero(app, entorno_contable, monkeypatch):
    """Tras persistir y confirmar, la caché se limpia y el selector ve el cliente."""
    sufijo = uuid4().hex[:8]
    nombre = f"Cliente importado {sufijo}"
    invalidados: list[str] = []
    original = import_service.invalidate_cache

    def registrar(clave: str) -> None:
        invalidados.append(clave)
        original(clave)

    monkeypatch.setattr(import_service, "invalidate_cache", registrar)
    with app.app_context():
        lote = _lote("cacao")
        lote_id = lote.id

        def persistir(_documento) -> None:
            cliente = Party(
                code=f"IMP-{sufijo}",
                name=nombre,
                is_customer=True,
                is_active=True,
            )
            database.session.add(cliente)
            database.session.flush()
            database.session.add(CompanyParty(company="cacao", party_id=cliente.id, is_active=True))
            database.session.commit()

        adapter = SimpleNamespace(
            build_document=lambda rows, context: SimpleNamespace(),
            persist_document=persistir,
        )
        servicio = import_service.ImportService.__new__(import_service.ImportService)
        monkeypatch.setattr(servicio, "_validate_document_period", lambda *a, **k: None)

        servicio._process_document(adapter, "ref", [{}], {}, lote, lote_id)

        assert "smart-select-master-data" in invalidados
        resultado = search_select("customer", nombre, {"company": ["cacao"]}, limit=5)
        nombres = [opcion["display_name"] for opcion in resultado["results"]]
        assert len(nombres) == 1
        assert nombre in nombres[0]

        cliente = database.session.execute(database.select(Party).filter_by(name=nombre)).scalar_one()
        database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id == cliente.id))
        database.session.delete(cliente)
        database.session.delete(database.session.get(ImportBatch, lote_id))
        database.session.commit()
