# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1900: importar terceros invalida la caché y el selector ve el registro nuevo."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

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


def _importar_tercero(app, monkeypatch, nombre: str, sufijo: str) -> str:
    """Ejecuta el worker de importación y devuelve el id del lote creado."""
    with app.app_context():
        lote = _lote("cacao")
        lote_id = lote.id

        def persistir(_documento) -> None:
            cliente = Party(code=f"IMP-{sufijo}", name=nombre, is_customer=True, is_active=True)
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
    return lote_id


def _limpiar_tercero(app, nombre: str, lote_id: str) -> None:
    """Elimina el tercero importado y su lote de prueba."""
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(name=nombre)).scalar_one_or_none()
        if cliente is not None:
            database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id == cliente.id))
            database.session.delete(cliente)
        lote = database.session.get(ImportBatch, lote_id)
        if lote is not None:
            database.session.delete(lote)
        database.session.commit()


def _buscar_con_cache(app, user_id: str, nombre: str):
    """Ejecuta la búsqueda cacheada dentro de una sesión autenticada."""
    from flask_login import login_user

    from cacao_accounting.api import _cached_master_data_search
    from cacao_accounting.database import User

    with app.test_request_context("/"):
        login_user(database.session.get(User, user_id))
        return _cached_master_data_search("customer", nombre, (), 5, ("cacao",))


@pytest.mark.cache
def test_el_selector_cacheado_se_refresca_tras_importar(app, entorno_contable, reference_users, monkeypatch):
    """Un resultado precargado en Redis deja de ocultar al tercero importado."""
    del entorno_contable
    if app.config.get("CACHE_TYPE") != "RedisCache" or not app.config.get("CACHE_REDIS_URL"):
        pytest.skip("La prueba de caché requiere Redis configurado en modo Cloud.")

    sufijo = uuid4().hex[:8]
    nombre = f"Cliente cacheado {sufijo}"
    user_id = str(reference_users["admin"].id)

    antes = _buscar_con_cache(app, user_id, nombre)
    assert antes["results"] == []

    lote_id = _importar_tercero(app, monkeypatch, nombre, sufijo)
    try:
        despues = _buscar_con_cache(app, user_id, nombre)

        nombres = [opcion["display_name"] for opcion in despues["results"]]
        assert len(nombres) == 1
        assert nombre in nombres[0]
    finally:
        _limpiar_tercero(app, nombre, lote_id)


def test_el_selector_sin_redis_lee_el_registro_nuevo(app, entorno_contable, reference_users, monkeypatch):
    """Sin Redis la ruta cacheada es pass-through y no requiere invalidación."""
    del entorno_contable
    if app.config.get("CACHE_TYPE") == "RedisCache" and app.config.get("CACHE_REDIS_URL"):
        pytest.skip("Aplica al modo sin caché compartida.")

    sufijo = uuid4().hex[:8]
    nombre = f"Cliente sin cache {sufijo}"
    user_id = str(reference_users["admin"].id)

    assert _buscar_con_cache(app, user_id, nombre)["results"] == []
    lote_id = _importar_tercero(app, monkeypatch, nombre, sufijo)
    try:
        despues = _buscar_con_cache(app, user_id, nombre)
        assert any(nombre in opcion["display_name"] for opcion in despues["results"])
    finally:
        _limpiar_tercero(app, nombre, lote_id)
