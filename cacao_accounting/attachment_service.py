"""Cloud-only file attachment and item image service."""

from __future__ import annotations

import os
import uuid
from typing import Any

from flask import current_app
from werkzeug.utils import secure_filename

from cacao_accounting.database import File, FileAttachment, Item, database
from cacao_accounting.runtime_mode import is_desktop_mode

MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


class AttachmentError(ValueError):
    """Controlled validation error for attachment operations."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Initialize attachment error with message and HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


def _ensure_cloud_mode() -> None:
    if is_desktop_mode():
        raise AttachmentError("La subida de archivos no está disponible en modo escritorio.", 403)


def _get_upload_folder() -> str:
    if current_app:
        folder = current_app.config.get("UPLOAD_FOLDER")
        if not folder:
            folder = os.path.join(current_app.instance_path, "uploads")
    else:
        folder = os.path.join(os.getcwd(), "uploads")
    os.makedirs(folder, exist_ok=True)
    return folder


def upload_attachment(
    reference_type: str,
    reference_id: str,
    file_storage: Any,
    user_id: str | None = None,
    remarks: str | None = None,
) -> dict[str, Any]:
    """Upload and attach a file to a document or master record in Cloud mode."""
    _ensure_cloud_mode()

    if not reference_type or not str(reference_type).strip():
        raise AttachmentError("Tipo de referencia requerido.", 400)
    if not reference_id or not str(reference_id).strip():
        raise AttachmentError("ID de referencia requerido.", 400)

    if not file_storage or not getattr(file_storage, "filename", None):
        raise AttachmentError("No se proporcionó ningún archivo.", 400)

    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        original_filename = "attachment"

    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_size <= 0:
        raise AttachmentError("El archivo está vacío.", 400)
    if file_size > MAX_FILE_SIZE:
        raise AttachmentError("El archivo excede el tamaño máximo permitido (16 MB).", 400)

    upload_folder = _get_upload_folder()
    unique_prefix = uuid.uuid4().hex[:12]
    saved_filename = f"{unique_prefix}_{original_filename}"
    file_path = os.path.join(upload_folder, saved_filename)

    file_storage.save(file_path)

    try:
        mime_type = getattr(file_storage, "content_type", None) or "application/octet-stream"

        file_record = File(
            file_name=original_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=user_id,
            remarks=remarks,
        )
        database.session.add(file_record)
        database.session.flush()

        attachment_record = FileAttachment(
            file_id=file_record.id,
            reference_type=str(reference_type).strip(),
            reference_id=str(reference_id).strip(),
        )
        database.session.add(attachment_record)
        database.session.commit()
    except Exception:
        database.session.rollback()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
        raise

    return {
        "file_id": file_record.id,
        "attachment_id": attachment_record.id,
        "file_name": file_record.file_name,
        "file_size": file_record.file_size,
        "mime_type": file_record.mime_type,
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
                "created": file_rec.created.strftime("%Y-%m-%d %H:%M") if file_rec.created else "-",
                "uploaded_by": file_rec.uploaded_by or "Sistema",
                "remarks": file_rec.remarks or "",
            }
        )
    return attachments


def get_attachment_file(file_id: str) -> tuple[File, str]:
    """Retrieve File model and verified file path for download."""
    file_record = database.session.get(File, file_id)
    if file_record is None:
        raise AttachmentError("Archivo no encontrado.", 404)
    if not file_record.file_path or not os.path.exists(file_record.file_path):
        raise AttachmentError("El archivo físico no se encuentra en el servidor.", 404)
    return file_record, file_record.file_path


def delete_attachment(file_id: str, reference_type: str, reference_id: str, user_id: str | None = None) -> bool:
    """Delete an attachment link and cleanup physical file if no other reference exists."""
    _ensure_cloud_mode()

    ref_type = str(reference_type).strip()
    ref_id = str(reference_id).strip()

    attachment = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.file_id == file_id)
            .where(FileAttachment.reference_type == ref_type)
            .where(FileAttachment.reference_id == ref_id)
        )
        .scalars()
        .first()
    )

    if attachment is None:
        raise AttachmentError("Adjunto no encontrado.", 404)

    database.session.delete(attachment)
    database.session.flush()

    other_links = (
        database.session.execute(
            database.select(database.func.count(FileAttachment.id)).where(FileAttachment.file_id == file_id)
        ).scalar()
        or 0
    )

    if other_links == 0:
        file_rec = database.session.get(File, file_id)
        if file_rec:
            if file_rec.file_path and os.path.exists(file_rec.file_path):
                try:
                    os.remove(file_rec.file_path)
                except OSError:
                    pass
            database.session.delete(file_rec)

    database.session.commit()
    return True


def upload_item_image(item_id: str, file_storage: Any, user_id: str | None = None) -> dict[str, Any]:
    """Upload product image for an inventory item (Cloud mode only)."""
    _ensure_cloud_mode()

    if not item_id or not str(item_id).strip():
        raise AttachmentError("ID de artículo requerido.", 400)

    item = database.session.execute(
        database.select(Item).where((Item.code == str(item_id).strip()) | (Item.id == str(item_id).strip()))
    ).scalar_one_or_none()

    if item is None:
        raise AttachmentError("Artículo no encontrado.", 404)

    if not file_storage or not getattr(file_storage, "filename", None):
        raise AttachmentError("No se seleccionó una imagen.", 400)

    ext = os.path.splitext(file_storage.filename)[1].lower()
    content_type = getattr(file_storage, "content_type", "") or ""

    if ext not in ALLOWED_IMAGE_EXTENSIONS or not content_type.startswith("image/"):
        raise AttachmentError("Formato de imagen no permitido. Use PNG, JPG, WEBP o GIF.", 400)

    file_storage.seek(0)
    header = file_storage.read(4096)
    file_storage.seek(0)
    if not _has_valid_image_signature(header, ext):
        raise AttachmentError("El contenido no corresponde a una imagen válida.", 400)

    old_attachments = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.reference_type == "item_image")
            .where(FileAttachment.reference_id == item.code)
        )
        .scalars()
        .all()
    )

    upload_result = upload_attachment(
        reference_type="item_image",
        reference_id=item.code,
        file_storage=file_storage,
        user_id=user_id,
        remarks=f"Imagen del producto {item.code}",
    )

    file_rec, path = get_attachment_file(upload_result["file_id"])
    item.image_path = path
    database.session.commit()

    for old_attachment in old_attachments:
        delete_attachment(old_attachment.file_id, "item_image", item.code, user_id=user_id)

    return {
        "item_id": item.code,
        "image_path": path,
        "file_id": file_rec.id,
    }


def _has_valid_image_signature(header: bytes, extension: str) -> bool:
    """Check the file signature instead of trusting multipart metadata alone."""
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
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
        raise AttachmentError("Artículo no encontrado.", 404)

    attachments = (
        database.session.execute(
            database.select(FileAttachment)
            .where(FileAttachment.reference_type == "item_image")
            .where(FileAttachment.reference_id == item.code)
        )
        .scalars()
        .all()
    )

    for att in attachments:
        try:
            delete_attachment(att.file_id, "item_image", item.code, user_id=user_id)
        except AttachmentError:
            pass

    item.image_path = None
    database.session.commit()
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
    return file_rec, item.image_path
