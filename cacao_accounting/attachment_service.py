# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cloud-only file attachment and item image service.

Este módulo es la frontera única de adjuntos: valida el contenido real del
archivo, calcula su SHA-256 de forma incremental, lo persiste y registra la
evidencia append-only en la bitácora central. No implementa deduplicación
física ni rediseña el almacenamiento.
"""

from __future__ import annotations

import hashlib
import os
import uuid
import zipfile
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from flask import current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from cacao_accounting.audit_trail_service import log_attachment_event
from cacao_accounting.database import (
    CompanyParty,
    File,
    FileAttachment,
    Item,
    database,
)
from cacao_accounting.i18n import _
from cacao_accounting.logs import log
from cacao_accounting.runtime_mode import is_desktop_mode

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Límites de seguridad para archivos con estructura ZIP interna (DOCX/XLSX/ODS).
MAX_ZIP_ENTRIES = 500
MAX_ZIP_ENTRY_SIZE = 50 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED = 200 * 1024 * 1024
MAX_ZIP_RATIO = 100

_EXTENSION_KIND = {
    ".pdf": "pdf",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".ods": "ods",
    ".docx": "docx",
    ".doc": "doc",
    ".odt": "odt",
    ".txt": "txt",
}

_KIND_MIME = {
    "pdf": "application/pdf",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "odt": "application/vnd.oasis.opendocument.text",
    "txt": "text/plain",
}

ALLOWED_MIME_TYPES = frozenset(_KIND_MIME.values())

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_DANGEROUS_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"#!",
    b"\xca\xfe\xba\xbe",
    b"\xcf\xfa\xed\xfe",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\x1f\x8b",
    b"BZh",
    b"\xfd7zXZ\x00",
    b"Rar!\x1a\x07",
    b"7z\xbc\xaf\x27\x1c",
)
_HTML_PREFIXES = ("<html", "<!doctype html", "<svg", "<?xml", "<script")
_FORBIDDEN_ZIP_PARTS = ("vbaproject", "externallink", "embeddings/", "connections.xml", "basic/")
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

# Entidades maestras (terceros): no tienen ciclo de vida documental, por lo que
# su evidencia adjunta siempre es editable.
ATTACHMENT_MASTER_MODULES = {"customer": "sales", "supplier": "purchases"}

# Estados en los que la evidencia adjunta queda bloqueada. La evidencia es
# append-only: una vez que el documento sale del borrador (o se contabiliza,
# aprueba, anula o rechaza) no se permite agregar ni eliminar adjuntos.
_ATTACHMENT_LOCKED_STATUSES = frozenset(
    {
        "submitted",
        "approved",
        "posted",
        "applied",
        "closed",
        "completed",
        "cancelled",
        "canceled",
        "void",
        "rejected",
        "reversed",
        "pending approval",
        "pending cancellation",
    }
)


def document_allows_attachment_edit(document: Any) -> bool:
    """Indica si un documento admite alta o baja de evidencia adjunta.

    Se bloquea la edicion cuando el documento tiene ``docstatus`` de enviado o
    anulado (1/2) o cuando su ``status`` corresponde a un estado posterior al
    borrador. Evaluar ``docstatus`` de forma independiente evita que un
    documento contabilizado con ``status`` de borrador pase el filtro.
    """
    if document is None:
        return False
    if getattr(document, "docstatus", None) in (1, 2):
        return False
    status = str(getattr(document, "status", None) or "").strip().lower()
    return status not in _ATTACHMENT_LOCKED_STATUSES


def attachment_reference_allows_edit(reference_type: str, reference_id: str) -> bool:
    """Resuelve si una referencia (documento o maestro) admite editar adjuntos.

    Un tipo desconocido o inexistente devuelve ``True`` para no ocultar la UI
    por error; la autorizacion y el estado se validan igualmente en el backend.
    """
    from cacao_accounting.document_flow.registry import normalize_doctype
    from cacao_accounting.document_flow.repository import get_document

    normalized = normalize_doctype(reference_type)
    if normalized in ATTACHMENT_MASTER_MODULES:
        return True
    try:
        document = get_document(normalized, reference_id)
    except (KeyError, ValueError):
        return True
    if document is None:
        return True
    return document_allows_attachment_edit(document)


class AttachmentError(ValueError):
    """Controlled validation error for attachment operations."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Initialize attachment error with message and HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    """Upload validado y respaldado por un archivo temporal hasta persistirlo."""

    temp_path: str
    filename: str
    mime_type: str
    sha256: str
    size: int


@dataclass(frozen=True)
class StoredAttachment:
    """File metadata created by :func:`store_attachment` before commit."""

    file_id: str
    attachment_id: str
    file_path: str


def _configured_max_file_size() -> int:
    """Devuelve el límite por archivo configurado en el backend."""
    if current_app:
        raw = current_app.config.get("ATTACHMENT_MAX_FILE_SIZE")
        value = 0
        if raw is not None:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = 0
        if value > 0:
            return value
    return MAX_FILE_SIZE


def _safe_filename(raw_name: str, extension: str) -> str:
    """Normaliza el nombre visible sin perder la extensión validada."""
    base = secure_filename(raw_name)
    if not base or not os.path.splitext(base)[1]:
        return f"attachment{extension}"
    stem, current_extension = os.path.splitext(base)
    return f"{stem[:200]}{current_extension.lower()}"


def _stream_upload(upload: Any, path: str, max_bytes: int) -> tuple[int, str]:
    """Copia el upload a disco calculando SHA-256 y respetando el límite."""
    hasher = hashlib.sha256()
    total = 0
    stream = getattr(upload, "stream", None) or upload
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass
    with open(path, "wb") as target:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise AttachmentError(_("El archivo supera el tamaño máximo permitido."))
            hasher.update(chunk)
            target.write(chunk)
    return total, hasher.hexdigest()


def _read_head(path: str, size: int = 4096) -> bytes:
    """Lee solo la cabecera necesaria para inspeccionar firmas."""
    with open(path, "rb") as handle:
        return handle.read(size)


def _has_dangerous_signature(header: bytes) -> bool:
    """Rechaza ejecutables, scripts y archivos comprimidos genéricos."""
    if any(header.startswith(prefix) for prefix in _DANGEROUS_PREFIXES):
        return True
    return header[257:262] == b"ustar"


def _zip_entry_unsafe(name: str) -> bool:
    """Rechaza rutas absolutas o con traversal dentro del ZIP."""
    normalized = name.replace("\\", "/")
    return normalized.startswith("/") or ".." in normalized.split("/")


def _validate_zip_limits(entries: list[zipfile.ZipInfo]) -> None:
    """Protege contra bombas de descompresión y archivos malformados."""
    if len(entries) > MAX_ZIP_ENTRIES:
        raise AttachmentError(_("El archivo contiene demasiados elementos comprimidos."))
    uncompressed = sum(max(entry.file_size, 0) for entry in entries)
    compressed = max(sum(max(entry.compress_size, 1) for entry in entries), 1)
    if uncompressed > MAX_ZIP_UNCOMPRESSED or uncompressed / compressed > MAX_ZIP_RATIO:
        raise AttachmentError(_("El archivo comprimido excede los límites de seguridad."))
    for entry in entries:
        if entry.flag_bits & 0x1:
            raise AttachmentError(_("El archivo está dañado o no es válido."))
        if entry.file_size > MAX_ZIP_ENTRY_SIZE or _zip_entry_unsafe(entry.filename):
            raise AttachmentError(_("El archivo comprimido excede los límites de seguridad."))


def _zip_has_forbidden_parts(names: set[str]) -> bool:
    """Detecta macros, enlaces externos y contenido embebido no permitido."""
    return any(token in name.lower() for name in names for token in _FORBIDDEN_ZIP_PARTS)


def _read_zip_entry(archive: zipfile.ZipFile, name: str, limit: int) -> bytes:
    """Lee una entrada pequeña con cota explícita de tamaño."""
    with archive.open(name) as handle:
        return handle.read(limit + 1)


def _classify_zip(path: str) -> str | None:
    """Clasifica OOXML/ODF por su estructura interna real."""
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            _validate_zip_limits(entries)
            names = {entry.filename for entry in entries}
            if _zip_has_forbidden_parts(names):
                raise AttachmentError(_("El archivo contiene macros, enlaces o contenido embebido no permitido."))
            if "mimetype" in names:
                mime = _read_zip_entry(archive, "mimetype", 256).decode("ascii", "ignore").strip()
                if mime == "application/vnd.oasis.opendocument.spreadsheet":
                    return "ods"
                if mime == "application/vnd.oasis.opendocument.text":
                    return "odt"
                return None
            if "[Content_Types].xml" in names:
                if "word/document.xml" in names:
                    return "docx"
                if "xl/workbook.xml" in names:
                    return "xlsx"
            return None
    except (zipfile.BadZipFile, OSError) as exc:
        raise AttachmentError(_("El archivo está dañado o no es válido.")) from exc


def _contains_stream_name(path: str, needles: tuple[bytes, ...]) -> bool:
    """Busca nombres de stream OLE en UTF-16LE sin cargar todo el archivo."""
    overlap = max(len(needle) for needle in needles) - 1
    carry = b""
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                return False
            data = carry + chunk
            if any(needle in data for needle in needles):
                return True
            carry = data[-overlap:] if overlap else b""


def _classify_ole(path: str) -> str | None:
    """Distingue .doc y .xls legacy por los streams del contenedor OLE."""
    if _contains_stream_name(path, ("WordDocument".encode("utf-16-le"),)):
        return "doc"
    if _contains_stream_name(path, ("Workbook".encode("utf-16-le"), "Book".encode("utf-16-le"))):
        return "xls"
    return None


def _decode_text(path: str) -> str | None:
    """Decodifica texto real, rechazando contenido binario con NUL."""
    with open(path, "rb") as handle:
        data = handle.read()
    if b"\x00" in data:
        return None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _looks_like_markup(text: str) -> bool:
    """Rechaza HTML/SVG/XML aunque se presenten como texto plano."""
    return text.lstrip().lower().startswith(_HTML_PREFIXES)


def _classify_text(path: str) -> str | None:
    """Clasifica texto plano o CSV y bloquea markup ejecutable."""
    text = _decode_text(path)
    if text is None:
        return None
    if _looks_like_markup(text):
        return "markup"
    return "text"


def _detect_kind(path: str, header: bytes) -> str | None:
    """Detecta el tipo real a partir de firmas y estructura del contenido."""
    if header.startswith(b"%PDF-") or b"%PDF-" in header[:1024]:
        return "pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    if header.startswith(_ZIP_SIGNATURES):
        kind = _classify_zip(path)
        if kind is None:
            raise AttachmentError(_("Los archivos comprimidos no se permiten como adjuntos."))
        return kind
    if header.startswith(_OLE_MAGIC):
        return _classify_ole(path)
    return _classify_text(path)


def _validate_file_content(path: str, declared_kind: str) -> str:
    """Valida que el contenido real corresponda a la extensión declarada."""
    header = _read_head(path)
    if _has_dangerous_signature(header):
        raise AttachmentError(_("Tipo de archivo no permitido."))
    actual_kind = _detect_kind(path, header)
    if actual_kind == "markup":
        raise AttachmentError(_("Tipo de archivo no permitido."))
    if actual_kind == "text" and declared_kind in {"csv", "txt"}:
        return _KIND_MIME[declared_kind]
    if actual_kind != declared_kind:
        raise AttachmentError(_("El contenido del archivo no corresponde a su extensión."))
    return _KIND_MIME[declared_kind]


def validate_upload(upload: Any, *, max_bytes: int | None = None) -> ValidatedUpload:
    """Valida un upload real y lo deja en un temporal listo para persistir.

    El SHA-256 se calcula incrementalmente sobre los bytes reales mientras se
    copia el archivo. La validación de tipo usa firmas y estructura interna,
    nunca el ``content_type`` declarado por el navegador.
    """
    if not upload or not getattr(upload, "filename", None):
        raise AttachmentError(_("No se proporcionó ningún archivo."), 400)
    raw_name = str(upload.filename)
    extension = os.path.splitext(raw_name)[1].lower()
    declared_kind = _EXTENSION_KIND.get(extension)
    if declared_kind is None:
        raise AttachmentError(_("Tipo de archivo no permitido."), 400)
    filename = _safe_filename(raw_name, extension)
    limit = max_bytes if max_bytes is not None else _configured_max_file_size()
    temp_path = os.path.join(_get_upload_folder(), f".upload-{uuid.uuid4().hex}.tmp")
    try:
        size, sha256 = _stream_upload(upload, temp_path, limit)
        if size <= 0:
            raise AttachmentError(_("El archivo está vacío."), 400)
        mime_type = _validate_file_content(temp_path, declared_kind)
    except Exception:
        _remove_file(temp_path)
        raise
    return ValidatedUpload(temp_path=temp_path, filename=filename, mime_type=mime_type, sha256=sha256, size=size)


def _remove_file(path: str | None) -> bool:
    """Elimina un archivo físico e informa si el borrado quedó pendiente."""
    if not path:
        return True
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        log.warning("No se pudo eliminar el archivo {}: {}", path, exc)
        return False
    return True


def _remove_files(paths: list[str]) -> list[str]:
    """Intenta borrar una lista de rutas y devuelve las que quedaron pendientes."""
    return [path for path in paths if not _remove_file(path)]


def store_attachment(
    *,
    reference_type: str,
    reference_id: str,
    upload: ValidatedUpload,
    actor_id: str | None = None,
    remarks: str | None = None,
    commit: bool = True,
) -> StoredAttachment:
    """Persist a validated upload and its document link in a single transaction."""
    _ensure_cloud_mode()
    folder = _get_upload_folder()
    file_path = os.path.join(folder, f"{uuid.uuid4().hex[:12]}_{upload.filename}")
    try:
        os.replace(upload.temp_path, file_path)
    except OSError as exc:
        _remove_file(upload.temp_path)
        raise AttachmentError(_("No se pudo almacenar el archivo."), 500) from exc
    try:
        file_record = File(
            file_name=upload.filename,
            file_path=file_path,
            file_size=upload.size,
            mime_type=upload.mime_type,
            sha256=upload.sha256,
            uploaded_by=actor_id,
            remarks=remarks,
        )
        database.session.add(file_record)
        database.session.flush()
        attachment_record = FileAttachment(
            file_id=file_record.id,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        database.session.add(attachment_record)
        database.session.flush()
        _emit_attachment_audit(
            "uploaded",
            reference_type,
            reference_id,
            file_record=file_record,
            after={},
            result="success",
        )
        if commit:
            database.session.commit()
        return StoredAttachment(file_record.id, attachment_record.id, file_path)
    except Exception:
        database.session.rollback()
        cleanup_uncommitted_attachment(StoredAttachment("", "", file_path))
        raise


def cleanup_uncommitted_attachment(attachment: StoredAttachment) -> None:
    """Remove the physical file for an attachment rolled back before commit."""
    _remove_file(attachment.file_path)


def _ensure_cloud_mode() -> None:
    if is_desktop_mode():
        raise AttachmentError(_("La subida de archivos no está disponible en modo escritorio."), 403)


def _get_upload_folder() -> str:
    if current_app:
        folder = current_app.config.get("UPLOAD_FOLDER")
        if not folder:
            folder = os.path.join(current_app.instance_path, "uploads")
    else:
        folder = os.path.join(os.getcwd(), "uploads")
    os.makedirs(folder, exist_ok=True)
    return folder


def _normalize_reference(reference_type: str, reference_id: str) -> tuple[str, str]:
    """Valida y normaliza la referencia documental del adjunto."""
    normalized_reference_type = str(reference_type).strip() if reference_type else ""
    if not normalized_reference_type:
        raise AttachmentError(_("Tipo de referencia requerido."), 400)
    normalized_reference_id = str(reference_id).strip() if reference_id else ""
    if not normalized_reference_id:
        raise AttachmentError(_("ID de referencia requerido."), 400)
    return normalized_reference_type, normalized_reference_id


def _resolve_reference_company(reference_type: str, reference_id: str) -> str | None:
    """Resuelve la compañía del documento o maestro relacionado, si existe."""
    try:
        from cacao_accounting.document_flow.registry import normalize_doctype
        from cacao_accounting.document_flow.repository import get_document

        normalized = normalize_doctype(reference_type)
        if normalized in ATTACHMENT_MASTER_MODULES:
            company = (
                database.session.execute(
                    database.select(CompanyParty.company).where(
                        CompanyParty.party_id == reference_id,
                        CompanyParty.is_active.is_(True),
                    )
                )
                .scalars()
                .first()
            )
            if company:
                return str(company)
        else:
            document = get_document(normalized, reference_id)
            company = getattr(document, "company", None)
            if company:
                return str(company)
    except (KeyError, ValueError):
        pass
    except Exception as exc:  # pragma: no cover - la auditoría no debe romper el flujo
        log.warning("Could not resolve attachment company: {}", exc)
    try:
        if current_user and current_user.is_authenticated:
            return str(getattr(current_user, "company", "") or "") or None
    except (AttributeError, RuntimeError):
        return None
    return None


def _audit_document(reference_type: str, reference_id: str) -> dict[str, Any]:
    """Construye el documento sintético que ancla el evento de auditoría."""
    return {
        "id": str(reference_id),
        "document_type": str(reference_type),
        "name": str(reference_id),
        "company": _resolve_reference_company(reference_type, reference_id),
    }


def _file_audit_payload(
    file_record: File | None,
    reference_type: str,
    reference_id: str,
    result: str,
) -> dict[str, Any]:
    """Arma el payload común de auditoría de un archivo adjunto."""
    return {
        "file_id": getattr(file_record, "id", None),
        "file_name": getattr(file_record, "file_name", None),
        "file_size": getattr(file_record, "file_size", None),
        "mime_type": getattr(file_record, "mime_type", None),
        "sha256": getattr(file_record, "sha256", None),
        "reference_type": reference_type,
        "reference_id": reference_id,
        "result": result,
    }


def _emit_attachment_audit(
    action: str,
    reference_type: str,
    reference_id: str,
    *,
    file_record: File | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    result: str = "success",
    comment: str | None = None,
) -> None:
    """Registra el evento con archivo, referencia y resultado."""
    payload = _file_audit_payload(file_record, reference_type, reference_id, result)
    if before is not None:
        before = {**payload, **before}
    if after is not None:
        after = {**payload, **after}
    log_attachment_event(
        _audit_document(reference_type, reference_id),
        action,
        before=before,
        after=after,
        comment=comment,
    )


def _actor_context(actor_id: str | None) -> Any:
    """Conserva el actor del servicio aun fuera de un request autenticado."""
    if not actor_id:
        return nullcontext()
    try:
        if current_user and current_user.is_authenticated:
            return nullcontext()
    except (AttributeError, RuntimeError):
        pass
    from cacao_accounting.internal_control_service import audit_actor

    return audit_actor(actor_id, actor_id)


def upload_attachment(
    reference_type: str,
    reference_id: str,
    file_storage: Any,
    user_id: str | None = None,
    remarks: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    """Upload and attach a file to a document or master record in Cloud mode.

    Es el único punto de entrada público para adjuntos. Valida el contenido
    real, persiste el SHA-256, registra auditoría y permite que el caller
    controle la transacción con ``commit=False``.
    """
    _ensure_cloud_mode()
    reference_type, reference_id = _normalize_reference(reference_type, reference_id)
    if not attachment_reference_allows_edit(reference_type, reference_id):
        raise AttachmentError(
            _("La evidencia adjunta no puede modificarse en el estado actual del documento."),
            403,
        )

    validated = validate_upload(file_storage)
    with _actor_context(user_id):
        stored = store_attachment(
            reference_type=reference_type,
            reference_id=reference_id,
            upload=validated,
            actor_id=user_id,
            remarks=remarks,
            commit=commit,
        )
        file_record = database.session.get(File, stored.file_id)
    if file_record is None:
        raise AttachmentError(_("Archivo no encontrado."), 404)
    return {
        "file_id": file_record.id,
        "attachment_id": stored.attachment_id,
        "file_name": file_record.file_name,
        "file_size": file_record.file_size,
        "mime_type": file_record.mime_type,
        "sha256": file_record.sha256,
        "created": file_record.created.isoformat() if file_record.created else None,
        "uploaded_by": file_record.uploaded_by,
        "remarks": file_record.remarks,
    }


def list_attachments(reference_type: str, reference_id: str) -> list[dict[str, Any]]:
    """List all attachments linked to a reference in Cloud or Desktop mode (read-only list)."""
    ref_type = str(reference_type).strip()
    ref_id = str(reference_id).strip()

    stmt = (
        database.select(FileAttachment, File)
        .join(File, FileAttachment.file_id == File.id)
        .where(FileAttachment.reference_type == ref_type)
        .where(FileAttachment.reference_id == ref_id)
        .order_by(File.created.desc())
    )

    rows = database.session.execute(stmt).all()
    attachments = []
    for attachment, file_rec in rows:
        attachments.append(
            {
                "attachment_id": attachment.id,
                "file_id": file_rec.id,
                "file_name": file_rec.file_name,
                "file_size": file_rec.file_size or 0,
                "mime_type": file_rec.mime_type or "application/octet-stream",
                "sha256": file_rec.sha256,
                "created": file_rec.created.strftime("%Y-%m-%d %H:%M") if file_rec.created else "-",
                "uploaded_by": file_rec.uploaded_by or "Sistema",
                "remarks": file_rec.remarks or "",
            }
        )
    return attachments


def _sha256_file(path: str) -> str:
    """Calcula el SHA-256 de un archivo en disco por bloques."""
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _verify_file_integrity(file_record: File, path: str) -> None:
    """Verifica el hash persistido; los archivos históricos con NULL se aceptan."""
    if not file_record.sha256:
        return
    if _sha256_file(path) != file_record.sha256:
        raise AttachmentError(_("El archivo no supera la verificación de integridad."), 409)


def get_attachment_file(file_id: str) -> tuple[File, str]:
    """Retrieve File model and verified file path for download."""
    file_record = database.session.get(File, file_id)
    if file_record is None:
        raise AttachmentError(_("Archivo no encontrado."), 404)
    if not file_record.file_path or not os.path.exists(file_record.file_path):
        raise AttachmentError(_("El archivo físico no se encuentra en el servidor."), 404)
    _verify_file_integrity(file_record, file_record.file_path)
    return file_record, file_record.file_path


def log_attachment_downloaded(file_record: File, reference_type: str, reference_id: str) -> None:
    """Registra la descarga autorizada antes de entregar el archivo."""
    _emit_attachment_audit(
        "downloaded",
        reference_type,
        reference_id,
        file_record=file_record,
        after={},
        result="success",
    )
    database.session.commit()


def log_attachment_access_denied(
    file_id: str,
    *,
    reference_type: str | None = None,
    reference_id: str | None = None,
    action: str = "download",
) -> None:
    """Registra un intento no autorizado como evento de seguridad append-only."""
    try:
        file_record = database.session.get(File, file_id)
        resolved_type = str(reference_type or "").strip()
        resolved_id = str(reference_id or "").strip()
        if not resolved_type or not resolved_id:
            link = (
                database.session.execute(database.select(FileAttachment).where(FileAttachment.file_id == file_id))
                .scalars()
                .first()
            )
            if link is not None:
                resolved_type = resolved_type or link.reference_type
                resolved_id = resolved_id or link.reference_id
        if not resolved_id:
            resolved_type = resolved_type or "attachment"
            resolved_id = file_id
        attempted_actions = {
            "download": "download_attempted",
            "delete": "delete_attempted",
            "update": "update_attempted",
        }
        event_action = attempted_actions.get(action, "delete_attempted")
        _emit_attachment_audit(
            event_action,
            resolved_type,
            resolved_id,
            file_record=file_record,
            after={},
            result="denied",
        )
        database.session.commit()
    except Exception as exc:  # pragma: no cover - no debe enmascarar el 403/404
        database.session.rollback()
        log.warning("Could not record attachment access denial: {}", exc)


def _delete_attachment_records(attachments: list[FileAttachment]) -> list[str]:
    """Elimina vínculos y archivos huérfanos dentro de la transacción actual."""
    paths: list[str] = []
    for attachment in attachments:
        file_id = attachment.file_id
        file_record = database.session.get(File, file_id)
        database.session.delete(attachment)
        database.session.flush()
        remaining = (
            database.session.execute(
                database.select(database.func.count(FileAttachment.id)).where(FileAttachment.file_id == file_id)
            ).scalar()
            or 0
        )
        if remaining:
            continue
        if file_record is None:
            continue
        _emit_attachment_audit(
            "deleted",
            attachment.reference_type,
            attachment.reference_id,
            file_record=file_record,
            before={},
            result="success",
        )
        if file_record.file_path:
            paths.append(file_record.file_path)
        database.session.delete(file_record)
    return paths


def _file_cleanup_metadata(attachments: list[FileAttachment]) -> dict[str, dict[str, Any]]:
    """Captura los metadatos del archivo antes de borrar sus filas.

    El evento de limpieza fallida se emite después del commit y no puede
    depender de instancias ORM ya eliminadas.
    """
    metadata: dict[str, dict[str, Any]] = {}
    for attachment in attachments:
        file_record = database.session.get(File, attachment.file_id)
        if file_record is None or not file_record.file_path:
            continue
        metadata[file_record.file_path] = {
            "file_id": file_record.id,
            "file_name": file_record.file_name,
            "file_size": file_record.file_size,
            "mime_type": file_record.mime_type,
            "sha256": file_record.sha256,
        }
    return metadata


def delete_attachment(file_id: str, reference_type: str, reference_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Delete an attachment link and cleanup physical file if no other reference exists.

    Devuelve ``file_removed=False`` y la lista de rutas en ``pending_cleanup``
    cuando el borrado lógico se confirma pero el archivo físico no puede
    eliminarse. El fallo queda registrado en la bitácora como evento append-only
    para que la limpieza pendiente sea visible y reintentable.
    """
    _ensure_cloud_mode()

    ref_type = str(reference_type).strip()
    ref_id = str(reference_id).strip()
    if not attachment_reference_allows_edit(ref_type, ref_id):
        raise AttachmentError(
            _("La evidencia adjunta no puede modificarse en el estado actual del documento."),
            403,
        )

    attachments = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.file_id == file_id)
            .where(FileAttachment.reference_type == ref_type)
            .where(FileAttachment.reference_id == ref_id)
        )
        .scalars()
        .all()
    )

    if not attachments:
        raise AttachmentError(_("Adjunto no encontrado."), 404)

    with _actor_context(user_id):
        try:
            metadata = _file_cleanup_metadata(list(attachments))
            paths = _delete_attachment_records(list(attachments))
            database.session.commit()
        except Exception:
            database.session.rollback()
            raise

    pending = _remove_files(paths)
    for path in pending:
        with _actor_context(user_id):
            try:
                _emit_attachment_audit(
                    "cleanup_failed",
                    ref_type,
                    ref_id,
                    after={**metadata.get(path, {}), "file_path": path},
                    result="failed",
                )
                database.session.commit()
            except Exception as exc:
                database.session.rollback()
                log.warning("Could not record attachment cleanup failure: {}", exc)

    return {"deleted": True, "file_removed": not pending, "pending_cleanup": pending}


def update_attachment_metadata(
    file_id: str,
    *,
    remarks: str | None = None,
    file_name: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Actualiza metadatos editables y registra el cambio en auditoría."""
    _ensure_cloud_mode()
    file_record = database.session.get(File, file_id)
    if file_record is None:
        raise AttachmentError(_("Archivo no encontrado."), 404)

    before = {"file_name": file_record.file_name, "remarks": file_record.remarks}
    changed = False
    if remarks is not None and remarks != file_record.remarks:
        file_record.remarks = remarks
        changed = True
    if file_name is not None:
        extension = os.path.splitext(file_record.file_name)[1].lower()
        safe_name = _safe_filename(str(file_name), extension)
        if safe_name != file_record.file_name:
            file_record.file_name = safe_name
            changed = True
    if not changed:
        return {
            "file_id": file_record.id,
            "file_name": file_record.file_name,
            "remarks": file_record.remarks,
        }

    after = {"file_name": file_record.file_name, "remarks": file_record.remarks}
    link = database.session.execute(database.select(FileAttachment).where(FileAttachment.file_id == file_id)).scalars().first()
    reference_type = link.reference_type if link else "attachment"
    reference_id = link.reference_id if link else file_id
    with _actor_context(user_id):
        try:
            _emit_attachment_audit(
                "updated",
                reference_type,
                reference_id,
                file_record=file_record,
                before=before,
                after=after,
                result="success",
            )
            database.session.commit()
        except Exception:
            database.session.rollback()
            raise
    return {
        "file_id": file_record.id,
        "file_name": file_record.file_name,
        "remarks": file_record.remarks,
    }


def upload_item_image(item_id: str, file_storage: Any, user_id: str | None = None) -> dict[str, Any]:
    """Upload product image for an inventory item (Cloud mode only)."""
    _ensure_cloud_mode()

    if not item_id or not str(item_id).strip():
        raise AttachmentError(_("ID de artículo requerido."), 400)

    item = database.session.execute(
        database.select(Item).where((Item.code == str(item_id).strip()) | (Item.id == str(item_id).strip()))
    ).scalar_one_or_none()

    if item is None:
        raise AttachmentError(_("Artículo no encontrado."), 404)

    if not file_storage or not getattr(file_storage, "filename", None):
        raise AttachmentError(_("No se seleccionó una imagen."), 400)

    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise AttachmentError(_("Formato de imagen no permitido. Use PNG, JPG o WEBP."), 400)

    stream = getattr(file_storage, "stream", None) or file_storage
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass
    header = stream.read(4096)
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass
    if not _has_valid_image_signature(header, ext):
        raise AttachmentError(_("El contenido no corresponde a una imagen válida."), 400)

    old_attachments = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.reference_type == "item_image")
            .where(FileAttachment.reference_id == item.code)
        )
        .scalars()
        .all()
    )

    result = upload_attachment(
        reference_type="item_image",
        reference_id=item.code,
        file_storage=file_storage,
        user_id=user_id,
        remarks=f"Imagen del producto {item.code}",
        commit=False,
    )
    file_record, path = get_attachment_file(result["file_id"])
    item.image_path = path
    try:
        old_paths = _delete_attachment_records(list(old_attachments))
        database.session.commit()
    except Exception:
        database.session.rollback()
        cleanup_uncommitted_attachment(StoredAttachment("", "", path))
        raise

    for old_path in old_paths:
        _remove_file(old_path)

    return {
        "item_id": item.code,
        "image_path": path,
        "file_id": file_record.id,
    }


def _has_valid_image_signature(header: bytes, extension: str) -> bool:
    """Check the file signature instead of trusting multipart metadata alone."""
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def delete_item_image(item_id: str, user_id: str | None = None, ignore_missing: bool = False) -> bool:
    """Remove product image from an inventory item."""
    _ensure_cloud_mode()

    item = database.session.execute(
        database.select(Item).where((Item.code == str(item_id).strip()) | (Item.id == str(item_id).strip()))
    ).scalar_one_or_none()

    if item is None:
        if ignore_missing:
            return False
        raise AttachmentError(_("Artículo no encontrado."), 404)

    attachments = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.reference_type == "item_image")
            .where(FileAttachment.reference_id == item.code)
        )
        .scalars()
        .all()
    )

    with _actor_context(user_id):
        try:
            paths = _delete_attachment_records(list(attachments))
            item.image_path = None
            database.session.commit()
        except Exception:
            database.session.rollback()
            raise

    for path in paths:
        _remove_file(path)
    return True


def get_item_image_file(item_id: str) -> tuple[File | None, str | None]:
    """Retrieve File model and verified file path for an item's product image."""
    item = database.session.execute(
        database.select(Item).where((Item.code == str(item_id).strip()) | (Item.id == str(item_id).strip()))
    ).scalar_one_or_none()

    if item is None or not item.image_path or not os.path.exists(item.image_path):
        return None, None

    attachment = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.reference_type == "item_image")
            .where(FileAttachment.reference_id == item.code)
        )
        .scalars()
        .first()
    )

    file_rec = database.session.get(File, attachment.file_id) if attachment else None
    if file_rec is not None:
        _verify_file_integrity(file_rec, item.image_path)
    return file_rec, item.image_path
