"""Cloud-only document comments and lightweight task collaboration."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, NoReturn

from flask import abort, url_for
from werkzeug.routing import BuildError

from cacao_accounting.audit_trail_service import log_comment, log_task_event
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import DocumentTask, User, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.decorators import exige_acceso_compania
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, normalize_doctype
from cacao_accounting.document_flow.repository import get_document
from cacao_accounting.runtime_mode import is_desktop_mode

TASK_STATUSES = {"open", "in_progress", "completed", "cancelled"}
TASK_PRIORITIES = {"low", "normal", "high"}
COMMENT_MAX_LENGTH = 2000


class CollaborationError(ValueError):
    """Controlled validation error for collaboration actions."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Initialize the error with a message and HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


def add_document_comment(document_type: str, document_id: str, comment: str, user_id: str) -> Any:
    """Add an audit-trail comment to a document."""
    _ensure_cloud_mode()
    cleaned_comment = _validate_comment(comment)
    document = _document_for_collaboration(document_type, document_id, user_id)
    entry = log_comment(document, cleaned_comment)
    database.session.commit()
    return entry


def create_task(
    *,
    document: Any,
    title: str,
    description: str | None,
    assigned_to: str,
    assigned_by: str,
    priority: str = "normal",
    due_date: date | None = None,
) -> DocumentTask:
    """Create a task assigned to an active user for a document."""
    _ensure_cloud_mode()
    normalized_priority = _validate_priority(priority)
    clean_title = _validate_title(title)
    assigned_user = _active_user_or_error(assigned_to)
    _ = assigned_user

    task = DocumentTask(
        document_type=_document_type(document),
        document_id=str(document.id),
        document_no=getattr(document, "document_no", None) or getattr(document, "serie", None),
        company=_document_company(document),
        title=clean_title,
        description=(description or "").strip() or None,
        assigned_by=assigned_by,
        assigned_to=assigned_to,
        priority=normalized_priority,
        due_date=due_date,
        status="open",
    )
    database.session.add(task)
    database.session.flush()
    log_task_event(document, "task_created", f"Tarea asignada: {task.title}")
    database.session.commit()
    return task


def create_document_task(
    document_type: str,
    document_id: str,
    payload: dict[str, Any],
    user_id: str,
) -> DocumentTask:
    """Validate document access and create a task from an API payload."""
    document = _document_for_collaboration(document_type, document_id, user_id)
    return create_task(
        document=document,
        title=str(payload.get("title") or ""),
        description=str(payload.get("description") or "") or None,
        assigned_to=str(payload.get("assigned_to") or ""),
        assigned_by=user_id,
        priority=str(payload.get("priority") or "normal"),
        due_date=_parse_date(payload.get("due_date")),
    )


def update_task_status(task_id: str, status: str, user_id: str) -> DocumentTask:
    """Update a task status and audit the related document."""
    _ensure_cloud_mode()
    normalized_status = _validate_status(status)
    task = database.session.get(DocumentTask, task_id)
    if task is None:
        raise CollaborationError("Tarea no encontrada.", 404)
    document = _document_for_collaboration(task.document_type, task.document_id, user_id)

    previous_status = task.status
    task.status = normalized_status
    task.completed_at = datetime.now(UTC) if normalized_status == "completed" else None
    action = _audit_action_for_status(normalized_status, previous_status)
    log_task_event(document, action, f"Tarea '{task.title}' cambió de {previous_status} a {normalized_status}.")
    database.session.commit()
    return task


def list_document_tasks(document_type: str, document_id: str) -> list[DocumentTask]:
    """List tasks attached to one document."""
    return list(
        database.session.execute(
            database.select(DocumentTask)
            .where(DocumentTask.document_type == normalize_doctype(document_type))
            .where(DocumentTask.document_id == document_id)
            .order_by(DocumentTask.created_at.desc(), DocumentTask.id.desc())
        )
        .scalars()
        .all()
    )


def list_user_tasks(
    user_id: str,
    status: str | None = None,
    priority: str | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    company: str | None = None,
) -> list[DocumentTask]:
    """List tasks assigned to a user with optional filters."""
    query = database.select(DocumentTask).where(DocumentTask.assigned_to == user_id)
    if status:
        query = query.where(DocumentTask.status == _validate_status(status))
    if priority:
        query = query.where(DocumentTask.priority == _validate_priority(priority))
    if due_date_from:
        query = query.where(DocumentTask.due_date >= due_date_from)
    if due_date_to:
        query = query.where(DocumentTask.due_date <= due_date_to)
    if company:
        query = query.where(DocumentTask.company == company)
    return list(database.session.execute(query.order_by(DocumentTask.created_at.desc())).scalars().all())


def active_users() -> list[User]:
    """Return active users available for task assignment."""
    return list(database.session.execute(database.select(User).filter_by(active=True).order_by(User.user)).scalars().all())


def open_task_count(user_id: str) -> int:
    """Return the count of not-completed tasks assigned to a user."""
    return int(
        database.session.execute(
            database.select(database.func.count(DocumentTask.id))
            .where(DocumentTask.assigned_to == user_id)
            .where(DocumentTask.status.in_(("open", "in_progress")))
        ).scalar()
        or 0
    )


def document_url(task: DocumentTask) -> str | None:
    """Build the detail URL for a task document when a route is registered."""
    spec = DOCUMENT_TYPES.get(task.document_type)
    if not spec or not spec.detail_endpoint:
        return None
    try:
        return url_for(spec.detail_endpoint, **{spec.detail_arg: task.document_id})
    except BuildError:
        return None


def _ensure_cloud_mode() -> None:
    if is_desktop_mode():
        raise CollaborationError("La colaboración no está disponible en modo escritorio.", 403)


def _validate_comment(comment: str) -> str:
    cleaned = (comment or "").strip()
    if not cleaned:
        raise CollaborationError("El comentario no puede estar vacío.", 400)
    if len(cleaned) > COMMENT_MAX_LENGTH:
        raise CollaborationError("El comentario no puede exceder 2000 caracteres.", 400)
    return cleaned


def _validate_title(title: str) -> str:
    cleaned = (title or "").strip()
    if not cleaned:
        raise CollaborationError("El título de la tarea es obligatorio.", 400)
    if len(cleaned) > 255:
        raise CollaborationError("El título de la tarea no puede exceder 255 caracteres.", 400)
    return cleaned


def _validate_status(status: str) -> str:
    normalized = (status or "").strip()
    if normalized not in TASK_STATUSES:
        raise CollaborationError("Estado de tarea inválido.", 400)
    return normalized


def _validate_priority(priority: str) -> str:
    normalized = (priority or "normal").strip()
    if normalized not in TASK_PRIORITIES:
        raise CollaborationError("Prioridad de tarea inválida.", 400)
    return normalized


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise CollaborationError("Fecha de vencimiento inválida.", 400) from exc


def _active_user_or_error(user_id: str) -> User:
    user = database.session.get(User, user_id)
    if user is None:
        raise CollaborationError("Usuario asignado no encontrado.", 404)
    if not user.active:
        raise CollaborationError("No se puede asignar tareas a usuarios inactivos.", 400)
    return user


def _document_for_collaboration(document_type: str, document_id: str, user_id: str) -> Any:
    doctype = normalize_doctype(document_type)
    if doctype not in DOCUMENT_TYPES:
        raise CollaborationError("Tipo documental no encontrado.", 404)
    document = get_document(doctype, document_id)
    if document is None:
        raise CollaborationError("Documento no encontrado.", 404)
    _require_document_permission(doctype, user_id)
    spec = DOCUMENT_TYPES[doctype]
    module_name = spec.permission_module or spec.module
    exige_acceso_compania(module_name, _document_company(document), "consultar")
    return document


def _require_document_permission(document_type: str, user_id: str) -> None:
    spec = DOCUMENT_TYPES[document_type]
    module_name = spec.permission_module or spec.module
    module_id = obtener_id_modulo_por_nombre(module_name)
    permission = Permisos(modulo=module_id, usuario=user_id)
    if not permission.autorizado:
        raise CollaborationError("No tiene permiso para colaborar en este documento.", 403)


def _document_type(document: Any) -> str:
    value = getattr(document, "document_type", None) or getattr(document, "voucher_type", None)
    if value:
        return normalize_doctype(str(value))
    for key, spec in DOCUMENT_TYPES.items():
        if isinstance(document, spec.header_model):
            return key
    return document.__class__.__name__


def _document_company(document: Any) -> str | None:
    company = getattr(document, "company", None) or getattr(document, "entity", None)
    return str(company) if company else None


def _audit_action_for_status(new_status: str, previous_status: str) -> str:
    if new_status == "completed":
        return "task_completed"
    if new_status == "cancelled":
        return "task_cancelled"
    if new_status != previous_status:
        return "task_status_changed"
    return "task_status_changed"


def abort_for_collaboration_error(error: CollaborationError) -> NoReturn:
    """Abort a Flask request using the status carried by the collaboration error."""
    abort(error.status_code)
