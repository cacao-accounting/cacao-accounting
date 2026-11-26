# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1661: la importación rechaza tipos de registro sin adaptador."""

from __future__ import annotations

import io
from typing import Any
from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, RolesAccess, User, database
from cacao_accounting.imports.models import ImportBatch
from cacao_accounting.runtime_mode import is_desktop_mode


def _estado_imports():
    """Captura presencia y valores exactos del módulo imports."""
    registro = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
    if registro is None:
        return None
    return (registro.enabled, registro.default)


def _permisos_del_modulo(modulo_id: str) -> list[dict[str, Any]]:
    """Captura los permisos que referencian al módulo antes de eliminarlo."""
    columnas = [columna.name for columna in RolesAccess.__table__.columns]
    filas = database.session.execute(database.select(RolesAccess).filter_by(module_id=modulo_id)).scalars().all()
    return [{columna: getattr(fila, columna) for columna in columnas} for fila in filas]


def _restaurar_permisos_del_modulo(filas: list[dict[str, Any]]) -> None:
    """Reinserta los permisos capturados apuntando al módulo restaurado."""
    modulo = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
    if modulo is None or not filas:
        return
    existentes = {
        (fila.rol_id, fila.module_id)
        for fila in database.session.execute(database.select(RolesAccess).filter_by(module_id=modulo.id)).scalars()
    }
    pendientes: list[RolesAccess] = []
    for fila in filas:
        valores = dict(fila)
        valores["module_id"] = modulo.id
        if (valores["rol_id"], valores["module_id"]) not in existentes:
            pendientes.append(RolesAccess(**valores))
    database.session.add_all(pendientes)


def _restaurar_imports(estado, permisos: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Restaura ausencia, NULL, False o True sin confundir los casos.

    ``permisos=None`` captura los permisos vigentes al eliminar el módulo;
    una lista explícita, incluso vacía, indica que ya fueron capturados.
    """
    registro = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
    capturados: list[dict[str, Any]] = []
    if permisos is not None:
        capturados = permisos
    elif estado is None and registro is not None:
        capturados = _permisos_del_modulo(registro.id)
    if estado is None:
        if registro is not None:
            if capturados:
                database.session.execute(database.delete(RolesAccess).where(RolesAccess.module_id == registro.id))
            database.session.delete(registro)
        return capturados
    enabled, default = estado
    if registro is None:
        database.session.add(Modules(module="imports", default=default, enabled=enabled))
        return capturados
    registro.enabled = enabled
    registro.default = default
    return capturados


@pytest.fixture(autouse=True)
def _modulo_imports(app):
    with app.app_context():
        estado_anterior = _estado_imports()
        registro_anterior = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
        permisos_iniciales = _permisos_del_modulo(registro_anterior.id) if registro_anterior is not None else []
        _restaurar_imports((True, False), permisos_iniciales)
        database.session.commit()
    try:
        yield
    finally:
        with app.app_context():
            database.session.rollback()
            _restaurar_imports(estado_anterior)
            _restaurar_permisos_del_modulo(permisos_iniciales)
            database.session.commit()


@pytest.mark.parametrize(
    "sembrado",
    [
        None,
        (None, False),
        (False, False),
        (True, True),
    ],
    ids=["ausente", "null", "false", "true"],
)
def test_restauracion_conserva_estado_exacto(app, sembrado):
    """Capturar y restaurar distingue fila ausente de módulo con enabled NULL."""
    with app.app_context():
        _restaurar_imports(sembrado)
        database.session.commit()

        capturado = _estado_imports()
        _restaurar_imports((True, False))
        database.session.commit()
        _restaurar_imports(capturado)
        database.session.commit()

        registro = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
        if sembrado is None:
            assert registro is None
        else:
            assert registro is not None
            assert registro.enabled == sembrado[0]
            assert registro.default == sembrado[1]


def _lote(record_type: str, estado: int) -> str:
    sufijo = uuid4().hex[:6]
    usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    lote = ImportBatch(
        company_id="cacao",
        record_type=record_type,
        source_format="csv",
        source_filename=f"{sufijo}.csv" if estado else None,
        import_status=estado,
        cancel_requested=False,
        created_by=usuario.id,
    )
    database.session.add(lote)
    database.session.commit()
    return lote.id


@pytest.mark.skipif(is_desktop_mode(), reason="Imports deshabilitado en modo desktop.")
def test_nuevo_rechaza_tipo_sin_adaptador(app, authenticated_client, entorno_contable):
    """El POST no crea lotes con tipos que el servicio no puede resolver."""
    del entorno_contable
    client = authenticated_client("admin")
    with app.app_context():
        antes = database.session.execute(database.select(database.func.count(ImportBatch.id))).scalar_one()

    record_type = f"not_a_real_adapter_{uuid4().hex[:6]}"
    response = client.post(
        "/imports/new",
        data={"company_id": "cacao", "record_type": record_type},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert response.history[0].status_code == 302
    html = response.get_data(as_text=True)
    assert record_type in html
    assert any(
        message in html
        for message in (
            f"Tipo de registro no soportado: {record_type}",
            f"Unsupported record type: {record_type}",
        )
    )
    with app.app_context():
        despues = database.session.execute(database.select(database.func.count(ImportBatch.id))).scalar_one()
    assert despues == antes


@pytest.mark.skipif(is_desktop_mode(), reason="Imports deshabilitado en modo desktop.")
def test_upload_rechaza_lote_con_tipo_sin_adaptador(app, authenticated_client, entorno_contable):
    """Un lote inválido preexistente no acepta archivos ni cambia de estado."""
    del entorno_contable
    with app.app_context():
        lote_id = _lote("not_a_real_adapter", 0)

    try:
        response = authenticated_client("admin").post(
            f"/imports/{lote_id}/upload",
            data={"file": (io.BytesIO(b"cuenta,debito\n1101,100\n"), "datos.csv")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        with app.app_context():
            lote = database.session.get(ImportBatch, lote_id)
            assert lote.import_status == 0
            assert lote.source_path is None
    finally:
        with app.app_context():
            database.session.execute(database.delete(ImportBatch).where(ImportBatch.id == lote_id))
            database.session.commit()


@pytest.mark.skipif(is_desktop_mode(), reason="Imports deshabilitado en modo desktop.")
def test_detalle_no_falla_con_tipo_sin_adaptador(app, authenticated_client, entorno_contable):
    """El detalle de un lote legado no intenta previsualizar sin adaptador."""
    del entorno_contable
    with app.app_context():
        lote_id = _lote("not_a_real_adapter", 1)

    try:
        response = authenticated_client("admin").get(f"/imports/{lote_id}")

        assert response.status_code == 200
    finally:
        with app.app_context():
            database.session.execute(database.delete(ImportBatch).where(ImportBatch.id == lote_id))
            database.session.commit()
