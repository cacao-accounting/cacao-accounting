# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Flujo único y auditado de adjuntos.

Cubre validación del contenido real, integridad SHA-256, autorización,
descarga auditada y compatibilidad con archivos históricos.
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.datastructures import FileStorage

from cacao_accounting import create_app
from cacao_accounting.attachment_service import (
    AttachmentError,
    delete_attachment,
    get_attachment_file,
    list_attachments,
    update_attachment_metadata,
    upload_attachment,
    upload_item_image,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AuditTrail,
    CompanyParty,
    Currency,
    Entity,
    File,
    FileAttachment,
    Item,
    Modules,
    Party,
    Roles,
    RolesAccess,
    RolesUser,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _storage(filename: str, data: bytes) -> FileStorage:
    """Construye un upload multipart real en memoria."""
    return FileStorage(stream=BytesIO(data), filename=filename)


def _zip_bytes(entries: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Empaqueta entradas en un ZIP real para las pruebas de estructura."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _xlsx_entries() -> dict[str, bytes]:
    """Estructura mínima reconocible como XLSX."""
    return {
        "[Content_Types].xml": b"<Types/>",
        "xl/workbook.xml": b"<workbook/>",
    }


def _grant_role(user_name: str, module_name: str, *, view: bool = False, edit: bool = False) -> None:
    """Asigna a un usuario un rol con permisos reales sobre un módulo."""
    user = database.session.execute(database.select(User).filter_by(user=user_name)).scalar_one()
    module = database.session.execute(database.select(Modules).filter_by(module=module_name)).scalar_one()
    role = Roles(name=f"{module_name}-{user_name}", note=f"Permisos de {module_name}")
    database.session.add(role)
    database.session.flush()
    database.session.add(RolesAccess(rol_id=role.id, module_id=module.id, view=view, edit=edit))
    database.session.add(RolesUser(user_id=user.id, role_id=role.id, active=True))


def _grant_company(user_name: str, company: str) -> None:
    """Asigna a un usuario acceso explícito a una compañía."""
    user = database.session.execute(database.select(User).filter_by(user=user_name)).scalar_one()
    database.session.add(UserCompanyAccess(user_id=user.id, company_code=company))


@pytest.fixture
def attachment_app(tmp_path: Path):
    """Aplicación Cloud aislada con tercero, usuario y carpeta de adjuntos."""
    application = create_app(
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
            "SECRET_KEY": "test-attachment-secret",
            "MODO_ESCRITORIO": False,
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="company-b",
                    name="Compañía B",
                    company_name="Compañía B SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code="comp-off",
                    name="Compañía Apagada",
                    company_name="Compañía Apagada SA",
                    tax_id="J0003",
                    currency="NIO",
                    enabled=False,
                ),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Party(code="PROV-1", name="Proveedor Uno", is_supplier=True, is_customer=False),
                Party(code="PROV-NONE", name="Proveedor sin activación", is_supplier=True, is_customer=False),
                Party(code="PROV-OFF", name="Proveedor en compañía apagada", is_supplier=True, is_customer=False),
                Party(
                    code="PROV-INACTIVE",
                    name="Proveedor inactivo",
                    is_supplier=True,
                    is_customer=False,
                    is_active=False,
                ),
                UOM(code="UND", name="Unidad", is_active=True),
                User(
                    user="admin",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
                User(
                    user="intruder",
                    name="Intruder",
                    password=b"x",
                    classification="user",
                    active=True,
                    company="cacao",
                ),
                User(
                    user="user-a",
                    name="Usuario A",
                    password=b"x",
                    classification="user",
                    active=True,
                    company="cacao",
                ),
                User(
                    user="user-b",
                    name="Usuario B",
                    password=b"x",
                    classification="user",
                    active=True,
                    company="company-b",
                ),
                User(
                    user="user-no-company",
                    name="Usuario sin compañía",
                    password=b"x",
                    classification="user",
                    active=True,
                    company=None,
                ),
                User(
                    user="user-no-perm",
                    name="Usuario sin permiso",
                    password=b"x",
                    classification="user",
                    active=True,
                    company="company-b",
                ),
            ]
        )
        database.session.flush()
        parties = {party.code: party for party in database.session.execute(database.select(Party)).scalars().all()}
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=parties["PROV-1"].id, is_active=True),
                CompanyParty(company="comp-off", party_id=parties["PROV-OFF"].id, is_active=True),
                CompanyParty(company="cacao", party_id=parties["PROV-INACTIVE"].id, is_active=True),
            ]
        )
        _grant_role("user-a", "purchases", view=True, edit=True)
        _grant_company("user-a", "cacao")
        _grant_role("user-b", "purchases", view=True)
        _grant_role("user-b", "inventory", view=True)
        _grant_company("user-b", "company-b")
        _grant_role("user-no-company", "inventory", view=True, edit=True)
        _grant_company("user-no-perm", "company-b")
        database.session.add(
            Item(
                code="ITEM-1",
                name="Artículo Uno",
                item_type="goods",
                is_stock_item=False,
                default_uom="UND",
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def party_id(attachment_app) -> str:
    """Identificador del tercero usado como referencia documental."""
    with attachment_app.app_context():
        return str(database.session.execute(database.select(Party).filter_by(code="PROV-1")).scalar_one().id)


@pytest.fixture
def users(attachment_app) -> dict[str, str]:
    """Identificadores de los usuarios sembrados."""
    with attachment_app.app_context():
        return {user.user: str(user.id) for user in database.session.execute(database.select(User)).scalars().all()}


def _login(app, user_id: str):
    """Cliente autenticado sin repetir el flujo de contraseña."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _upload(app, party_id: str, filename: str, data: bytes, user_id: str | None = None) -> dict:
    """Ejecuta el flujo único de carga dentro de un contexto de aplicación."""
    with app.app_context():
        return upload_attachment(
            "supplier",
            party_id,
            _storage(filename, data),
            user_id=user_id,
            remarks="evidencia",
        )


def _party_id(app, code: str) -> str:
    """Devuelve el ID de un tercero sembrado por código."""
    with app.app_context():
        return str(database.session.execute(database.select(Party).filter_by(code=code)).scalar_one().id)


def _add_company_party(app, party_id: str, company: str) -> None:
    """Activa un tercero existente en una compañía adicional."""
    with app.app_context():
        database.session.add(CompanyParty(company=company, party_id=party_id, is_active=True))
        database.session.commit()


def test_rechaza_extension_no_permitida(attachment_app, party_id):
    """Una extensión fuera de la lista blanca no llega a almacenarse."""
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment("supplier", party_id, _storage("malware.exe", b"MZ\x90\x00"))
    with attachment_app.app_context():
        assert database.session.execute(database.select(File)).scalars().all() == []


def test_rechaza_contenido_que_no_corresponde_a_la_extension(attachment_app, party_id):
    """Un .pdf con texto plano se rechaza aunque el navegador declare PDF."""
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment("supplier", party_id, _storage("falso.pdf", b"esto no es un pdf"))


def test_rechaza_ejecutable_disfrazado_de_pdf(attachment_app, party_id):
    """La firma PE se rechaza sin importar la extensión declarada."""
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment("supplier", party_id, _storage("falso.pdf", b"MZ\x90\x00" + b"\x00" * 64))


def test_rechaza_html_en_csv(attachment_app, party_id):
    """El markup se bloquea aunque se presente como texto/CSV."""
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment(
            "supplier",
            party_id,
            _storage("reporte.csv", b"<!DOCTYPE html><html><body>x</body></html>"),
        )


def test_acepta_pdf_y_persiste_sha256_real(attachment_app, party_id, users):
    """El PDF válido persiste MIME real, tamaño y hash de los bytes recibidos."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    assert result["mime_type"] == "application/pdf"
    assert result["sha256"] == hashlib.sha256(PDF).hexdigest()
    with attachment_app.app_context():
        file_record = database.session.get(File, result["file_id"])
        assert file_record is not None
        assert file_record.sha256 == hashlib.sha256(PDF).hexdigest()
        assert file_record.file_size == len(PDF)
        assert os.path.exists(file_record.file_path)


def test_sha256_es_inmutable_tras_almacenar(attachment_app, party_id):
    """El hash persistido no se puede reescribir ni borrar."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF)
    with attachment_app.app_context():
        file_record = database.session.get(File, result["file_id"])
        file_record.sha256 = "0" * 64
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()


def test_limite_de_tamano_es_configurable(attachment_app, party_id):
    """El backend puede reducir el límite por archivo."""
    original = attachment_app.config["ATTACHMENT_MAX_FILE_SIZE"]
    attachment_app.config["ATTACHMENT_MAX_FILE_SIZE"] = 8
    try:
        with attachment_app.app_context(), pytest.raises(AttachmentError):
            upload_attachment("supplier", party_id, _storage("factura.pdf", PDF))
    finally:
        attachment_app.config["ATTACHMENT_MAX_FILE_SIZE"] = original


def test_acepta_xlsx_con_estructura_real(attachment_app, party_id):
    """Un OOXML con workbook y content-types se acepta y clasifica como XLSX."""
    data = _zip_bytes(_xlsx_entries())
    result = _upload(attachment_app, party_id, "libro.xlsx", data)
    assert result["mime_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_rechaza_xlsx_con_macros(attachment_app, party_id):
    """Un .docx/.xlsx con vbaProject se rechaza aunque la extensión sea limpia."""
    entries = {**_xlsx_entries(), "xl/vbaProject.bin": b"macro"}
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment("supplier", party_id, _storage("libro.xlsx", _zip_bytes(entries)))


def test_rechaza_zip_bomba_de_descompresion(attachment_app, party_id):
    """Una relación de compresión abusiva se corta antes de descomprimir."""
    entries = {**_xlsx_entries(), "xl/sharedStrings.xml": b"0" * (5 * 1024 * 1024)}
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment("supplier", party_id, _storage("libro.xlsx", _zip_bytes(entries)))


def test_acepta_doc_legacy_solo_con_stream_word(attachment_app, party_id):
    """Un .doc legacy requiere el contenedor OLE y el stream WordDocument."""
    data = OLE_MAGIC + b"\x00" * 64 + "WordDocument".encode("utf-16-le") + b"\x00" * 64
    result = _upload(attachment_app, party_id, "antiguo.doc", data)
    assert result["mime_type"] == "application/msword"


def test_rechaza_doc_legacy_sin_stream(attachment_app, party_id):
    """La firma OLE sola no basta para aceptar un archivo legacy."""
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_attachment("supplier", party_id, _storage("antiguo.doc", OLE_MAGIC + b"\x00" * 128))


def test_archivo_historico_sin_hash_es_compatible(attachment_app, party_id):
    """Un registro previo con sha256 NULL se lista y descarga sin backfill."""
    with attachment_app.app_context():
        path = Path(attachment_app.config["UPLOAD_FOLDER"]) / "historico.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PDF)
        file_record = File(file_name="historico.pdf", file_path=str(path), file_size=len(PDF), mime_type="application/pdf")
        database.session.add(file_record)
        database.session.flush()
        database.session.add(FileAttachment(file_id=file_record.id, reference_type="supplier", reference_id=party_id))
        database.session.commit()
        file_id = file_record.id

        listed = list_attachments("supplier", party_id)
        assert listed[0]["sha256"] is None
        resolved, resolved_path = get_attachment_file(file_id)
        assert resolved.id == file_id
        assert resolved_path == str(path)


def test_descarga_auditada_y_con_cabeceras_seguras(attachment_app, party_id, users):
    """La descarga autorizada registra actor, compañía y cabeceras de defensa."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    client = _login(attachment_app, users["admin"])
    response = client.get(f"/attachments/download/{result['file_id']}")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    with attachment_app.app_context():
        event = database.session.execute(
            database.select(AuditTrail).filter_by(document_id=party_id, action="downloaded")
        ).scalar_one()
        assert event.actor_user_id == users["admin"]
        assert event.company == "cacao"
        payload = json.loads(event.after_json)
        assert payload["sha256"] == result["sha256"]
        assert payload["file_id"] == result["file_id"]
        assert payload["result"] == "success"


def test_descarga_no_autorizada_queda_auditada(attachment_app, party_id, users):
    """Un 403 de descarga deja un evento de seguridad append-only."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    client = _login(attachment_app, users["intruder"])
    response = client.get(f"/attachments/download/{result['file_id']}")
    assert response.status_code == 403

    with attachment_app.app_context():
        event = database.session.execute(
            database.select(AuditTrail).filter_by(document_id=party_id, action="download_attempted")
        ).scalar_one()
        assert event.actor_user_id == users["intruder"]
        assert json.loads(event.after_json)["result"] == "denied"


def test_eliminacion_no_autorizada_queda_auditada(attachment_app, party_id, users):
    """Un intento de eliminación sin permiso queda registrado como intento."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    client = _login(attachment_app, users["intruder"])
    response = client.post(
        f"/api/attachments/{result['file_id']}/delete",
        data={"reference_type": "supplier", "reference_id": party_id},
    )
    assert response.status_code == 403

    with attachment_app.app_context():
        event = database.session.execute(
            database.select(AuditTrail).filter_by(document_id=party_id, action="delete_attempted")
        ).scalar_one()
        assert event.actor_user_id == users["intruder"]
        assert json.loads(event.after_json)["result"] == "denied"
        assert database.session.get(File, result["file_id"]) is not None


def test_actualizacion_de_metadatos_queda_auditada(attachment_app, party_id, users):
    """Editar observaciones conserva el hash y registra before/after."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    original_sha = result["sha256"]
    client = _login(attachment_app, users["admin"])
    response = client.patch(
        f"/api/attachments/{result['file_id']}/metadata",
        json={"remarks": "observación actualizada"},
    )
    assert response.status_code == 200
    assert response.get_json()["remarks"] == "observación actualizada"

    with attachment_app.app_context():
        file_record = database.session.get(File, result["file_id"])
        assert file_record.sha256 == original_sha
        event = database.session.execute(
            database.select(AuditTrail).filter_by(document_id=party_id, action="updated")
        ).scalar_one()
        assert json.loads(event.before_json)["remarks"] == "evidencia"
        assert json.loads(event.after_json)["remarks"] == "observación actualizada"


def test_actualizacion_no_autorizada_queda_auditada_como_intento(attachment_app, party_id, users):
    """Un intento de edición sin permiso se registra como update_attempted."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    client = _login(attachment_app, users["intruder"])
    response = client.patch(
        f"/api/attachments/{result['file_id']}/metadata",
        json={"remarks": "intento"},
    )
    assert response.status_code == 403

    with attachment_app.app_context():
        event = database.session.execute(
            database.select(AuditTrail).filter_by(document_id=party_id, action="update_attempted")
        ).scalar_one()
        assert event.actor_user_id == users["intruder"]
        assert json.loads(event.after_json)["result"] == "denied"
        assert database.session.get(File, result["file_id"]).remarks == "evidencia"


def test_descarga_detecta_alteracion_del_archivo(attachment_app, party_id, users):
    """Si los bytes físicos no coinciden con el hash, la descarga se bloquea."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    with attachment_app.app_context():
        file_record = database.session.get(File, result["file_id"])
        with open(file_record.file_path, "ab") as handle:
            handle.write(b"alterado")
    client = _login(attachment_app, users["admin"])
    response = client.get(f"/attachments/download/{result['file_id']}")
    assert response.status_code == 409


def test_flujo_de_carga_usa_validacion_y_persistencia_unicas(attachment_app, party_id, monkeypatch):
    """La carga activa pasa por validate_upload y store_attachment."""
    import cacao_accounting.attachment_service as service

    calls = {"validate": 0, "store": 0}
    original_validate = service.validate_upload
    original_store = service.store_attachment

    def validate(upload, *, max_bytes=None):
        calls["validate"] += 1
        return original_validate(upload, max_bytes=max_bytes)

    def store(**kwargs):
        calls["store"] += 1
        return original_store(**kwargs)

    monkeypatch.setattr(service, "validate_upload", validate)
    monkeypatch.setattr(service, "store_attachment", store)
    _upload(attachment_app, party_id, "factura.pdf", PDF)
    assert calls == {"validate": 1, "store": 1}


def test_fallo_de_escritura_no_deja_archivos_parciales(attachment_app, party_id):
    """Un stream que falla a mitad de copia no deja temporales ni filas."""

    class _FailingStream:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._sent = False

        def seek(self, *_args) -> int:
            return 0

        def read(self, _size: int = -1) -> bytes:
            if not self._sent:
                self._sent = True
                return self._data
            raise OSError("fallo de red")

    stream = _FailingStream(b"%PDF-1.4\nparcial")
    with attachment_app.app_context(), pytest.raises(OSError):
        upload_attachment("supplier", party_id, FileStorage(stream=stream, filename="factura.pdf"))
    with attachment_app.app_context():
        assert database.session.execute(database.select(File)).scalars().all() == []
        assert database.session.execute(database.select(FileAttachment)).scalars().all() == []
    assert list(Path(attachment_app.config["UPLOAD_FOLDER"]).iterdir()) == []


def test_fallo_de_unlink_queda_visible_y_no_reporta_archivo_borrado(attachment_app, party_id, users, monkeypatch):
    """Si el archivo físico no se elimina, se registra y no se informa como borrado."""
    import cacao_accounting.attachment_service as service

    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    with attachment_app.app_context():
        file_path = database.session.get(File, result["file_id"]).file_path
        monkeypatch.setattr(service, "_remove_file", lambda path: False)
        outcome = delete_attachment(result["file_id"], "supplier", party_id, user_id=users["admin"])

        assert outcome == {"deleted": True, "file_removed": False, "pending_cleanup": [file_path]}
        assert database.session.get(File, result["file_id"]) is None
        event = database.session.execute(
            database.select(AuditTrail).filter_by(document_id=party_id, action="cleanup_failed")
        ).scalar_one()
        payload = json.loads(event.after_json)
        assert payload["file_path"] == file_path
        assert payload["result"] == "failed"
        assert os.path.exists(file_path)


def test_fallo_al_confirmar_reemplazo_conserva_la_imagen_anterior(attachment_app, users, monkeypatch):
    """Un fallo al confirmar el reemplazo no deja archivos ni vínculos nuevos."""
    import cacao_accounting.attachment_service as service

    with attachment_app.app_context():
        first = upload_item_image("ITEM-1", _storage("producto.png", PNG), user_id=users["admin"])
        first_path = first["image_path"]
        original = service._delete_attachment_records

        def fail(attachments):
            if attachments:
                raise RuntimeError("fallo al confirmar")
            return original(attachments)

        monkeypatch.setattr(service, "_delete_attachment_records", fail)
        with pytest.raises(RuntimeError):
            upload_item_image("ITEM-1", _storage("producto2.png", PNG + b"2"), user_id=users["admin"])

        item = database.session.execute(database.select(Item).filter_by(code="ITEM-1")).scalar_one()
        assert item.image_path == first_path
        assert os.path.exists(first_path)
        assert [file.id for file in database.session.execute(database.select(File)).scalars().all()] == [first["file_id"]]
        assert len(database.session.execute(database.select(FileAttachment)).scalars().all()) == 1
        upload_folder = Path(attachment_app.config["UPLOAD_FOLDER"])
        assert {path.name for path in upload_folder.iterdir()} == {Path(first_path).name}


def test_fallo_de_transaccion_no_deja_registros_ni_archivos(attachment_app, party_id, monkeypatch):
    """Un fallo al persistir revierte filas y elimina el archivo físico."""
    import cacao_accounting.attachment_service as service

    def _fail(*args, **kwargs):
        raise RuntimeError("auditoría no disponible")

    monkeypatch.setattr(service, "_emit_attachment_audit", _fail)
    with attachment_app.app_context(), pytest.raises(RuntimeError):
        upload_attachment("supplier", party_id, _storage("factura.pdf", PDF))
    with attachment_app.app_context():
        assert database.session.execute(database.select(File)).scalars().all() == []
        assert database.session.execute(database.select(FileAttachment)).scalars().all() == []
    upload_folder = Path(attachment_app.config["UPLOAD_FOLDER"])
    assert list(upload_folder.iterdir()) == []


def test_modo_escritorio_bloquea_carga(attachment_app, party_id):
    """El flujo sigue siendo Cloud-only y devuelve 403 en escritorio."""
    attachment_app.config["MODO_ESCRITORIO"] = True
    try:
        with attachment_app.app_context(), pytest.raises(AttachmentError) as error:
            upload_attachment("supplier", party_id, _storage("factura.pdf", PDF))
        assert error.value.status_code == 403
    finally:
        attachment_app.config["MODO_ESCRITORIO"] = False


def test_imagen_de_articulo_usa_el_flujo_unico_y_reemplaza(attachment_app, users):
    """La imagen de artículo comparte validación, hash y limpieza del adjunto."""
    with attachment_app.app_context():
        first = upload_item_image("ITEM-1", _storage("producto.png", PNG), user_id=users["admin"])
        first_path = first["image_path"]
        assert os.path.exists(first_path)
        assert database.session.get(File, first["file_id"]).sha256 == hashlib.sha256(PNG).hexdigest()

        second = upload_item_image("ITEM-1", _storage("producto2.png", PNG + b"2"), user_id=users["admin"])
        assert second["image_path"] != first_path
        assert not os.path.exists(first_path)
        assert database.session.get(File, first["file_id"]) is None
        item = database.session.execute(database.select(Item).filter_by(code="ITEM-1")).scalar_one()
        assert item.image_path == second["image_path"]


def test_imagen_alterada_no_se_sirve(attachment_app, users):
    """La ruta GET de imagen rechaza un archivo cuyo hash ya no coincide."""
    with attachment_app.app_context():
        upload_item_image("ITEM-1", _storage("producto.png", PNG), user_id=users["admin"])
        attachment = database.session.execute(
            database.select(FileAttachment).filter_by(reference_type="item_image", reference_id="ITEM-1")
        ).scalar_one()
        file_record = database.session.get(File, attachment.file_id)
        with open(file_record.file_path, "ab") as handle:
            handle.write(b"alterado")

    client = _login(attachment_app, users["admin"])
    response = client.get("/api/inventory/items/ITEM-1/image")
    assert response.status_code == 409


def test_gif_no_se_acepta_como_imagen_de_articulo(attachment_app, users):
    """GIF queda fuera de la lista blanca aprobada de imágenes."""
    with attachment_app.app_context(), pytest.raises(AttachmentError):
        upload_item_image("ITEM-1", _storage("producto.gif", b"GIF89a" + b"\x00" * 32), user_id=users["admin"])


def test_metadatos_sin_cambios_no_duplican_auditoria(attachment_app, party_id):
    """Una actualización idempotente no inventa un evento de cambio."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF)
    with attachment_app.app_context():
        update_attachment_metadata(result["file_id"], remarks="evidencia")
        events = (
            database.session.execute(database.select(AuditTrail).filter_by(document_id=party_id, action="updated"))
            .scalars()
            .all()
        )
        assert events == []


def test_adjunto_de_tercero_visible_desde_otra_compania_activa(attachment_app, party_id, users):
    """#1284: la visibilidad es compartida entre compañías donde el tercero está activo."""
    _add_company_party(attachment_app, party_id, "company-b")
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["user-a"])
    client = _login(attachment_app, users["user-b"])

    assert client.get(f"/api/attachments/supplier/{party_id}").status_code == 200
    assert client.get(f"/attachments/download/{result['file_id']}").status_code == 200


def test_adjunto_de_tercero_exige_permiso_de_modulo(attachment_app, party_id, users):
    """#1284: tener acceso a la compañía no sustituye el permiso del módulo."""
    _add_company_party(attachment_app, party_id, "company-b")
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    client = _login(attachment_app, users["user-no-perm"])

    assert client.get(f"/api/attachments/supplier/{party_id}").status_code == 403
    assert client.get(f"/attachments/download/{result['file_id']}").status_code == 403


def test_adjunto_de_tercero_fuera_de_compania_denegado(attachment_app, party_id, users):
    """#1284: un tercero activo solo en A no expone adjuntos a un usuario de B."""
    result = _upload(attachment_app, party_id, "factura.pdf", PDF, users["admin"])
    client = _login(attachment_app, users["user-b"])

    assert client.get(f"/api/attachments/supplier/{party_id}").status_code == 403
    assert client.get(f"/attachments/download/{result['file_id']}").status_code == 403


def test_adjunto_de_tercero_inactivo_denegado(attachment_app, users):
    """#1284: un tercero inactivo no expone adjuntos ni a un administrador."""
    party_id = _party_id(attachment_app, "PROV-INACTIVE")
    client = _login(attachment_app, users["admin"])

    assert client.get(f"/api/attachments/supplier/{party_id}").status_code == 403


def test_adjunto_de_tercero_sin_compania_denegado(attachment_app, users):
    """#1284: un tercero sin activación en ninguna compañía no expone adjuntos."""
    party_id = _party_id(attachment_app, "PROV-NONE")
    client = _login(attachment_app, users["admin"])

    assert client.get(f"/api/attachments/supplier/{party_id}").status_code == 403


def test_adjunto_de_tercero_en_compania_apagada_denegado(attachment_app, users):
    """#1284: una activación en una entidad deshabilitada no habilita el acceso."""
    party_id = _party_id(attachment_app, "PROV-OFF")
    client = _login(attachment_app, users["admin"])

    assert client.get(f"/api/attachments/supplier/{party_id}").status_code == 403


def test_carga_en_tercero_inactivo_denegada(attachment_app, users):
    """#1284: la carga aplica la misma política que la lectura para un tercero inactivo."""
    party_id = _party_id(attachment_app, "PROV-INACTIVE")
    client = _login(attachment_app, users["admin"])

    response = client.post(
        f"/api/attachments/supplier/{party_id}/upload",
        data={"file": (BytesIO(PDF), "factura.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 403
    with attachment_app.app_context():
        assert database.session.execute(database.select(File)).scalars().all() == []


def test_carga_en_tercero_sin_compania_denegada(attachment_app, users):
    """#1284: la carga aplica la misma política que la lectura sin activación."""
    party_id = _party_id(attachment_app, "PROV-NONE")
    client = _login(attachment_app, users["admin"])

    response = client.post(
        f"/api/attachments/supplier/{party_id}/upload",
        data={"file": (BytesIO(PDF), "factura.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 403
    with attachment_app.app_context():
        assert database.session.execute(database.select(File)).scalars().all() == []
