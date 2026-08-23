# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para gestión de comprobantes recurrentes."""

from datetime import date
import json
from typing import Any, Dict, List, Sequence
from sqlalchemy import or_, select
from cacao_accounting.audit_trail_service import log_create, log_submit
from cacao_accounting.database import (
    Accounts,
    Book,
    database,
    RecurringJournalTemplate,
    RecurringJournalItem,
    RecurringJournalApplication,
    ComprobanteContable,
    ComprobanteContableDetalle,
)
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


class RecurringJournalError(Exception):
    """Error base para comprobantes recurrentes."""

    _safe_for_display = True


PLANTILLA_NO_ENCONTRADA = "Plantilla no encontrada."


def create_recurring_template(data: Dict[str, Any], items: List[Dict[str, Any]], user_id: str) -> RecurringJournalTemplate:
    """Crea una nueva plantilla de comprobante recurrente."""
    validate_template_balance(items)
    company = data["company"]
    books = _authorized_template_books(company, data.get("books"), user_id, "crear")
    ledger_id = _canonical_book_reference(company, data.get("ledger_id"))
    if ledger_id and ledger_id not in (books or []):
        raise RecurringJournalError("El libro principal debe pertenecer a los libros autorizados seleccionados.")

    template = RecurringJournalTemplate(
        code=data["code"],
        company=company,
        ledger_id=ledger_id or (books[0] if books else None),
        naming_series_id=data.get("naming_series_id"),
        book_codes=_serialize_book_codes(books),
        name=data["name"],
        description=data.get("description"),
        start_date=data["start_date"],
        end_date=data["end_date"],
        frequency=data.get("frequency", "monthly"),
        currency=data.get("currency"),
        status="draft",
        docstatus=0,
        created_by=user_id,
    )
    database.session.add(template)
    database.session.flush()

    for item in items:
        line = RecurringJournalItem(
            template_id=template.id,
            account_code=_normalize_account_code(company, item["account_code"]),
            debit=item.get("debit", 0),
            credit=item.get("credit", 0),
            description=item.get("description"),
            cost_center=item.get("cost_center"),
            unit=item.get("unit"),
            project=item.get("project"),
            party_type=item.get("party_type"),
            party_id=item.get("party_id"),
            status="active",
            created_by=user_id,
        )
        database.session.add(line)

    log_create(template)
    database.session.commit()
    return template


def validate_template_balance(items: List[Dict[str, Any]]):
    """Valida que la plantilla esté balanceada."""
    from decimal import Decimal

    total_debit = sum(Decimal(str(i.get("debit", 0))) for i in items)
    total_credit = sum(Decimal(str(i.get("credit", 0))) for i in items)

    if total_debit != total_credit:
        raise RecurringJournalError("La plantilla debe estar balanceada (Débito != Crédito).")

    if len(items) < 2:
        raise RecurringJournalError("La plantilla debe tener al menos dos líneas.")


def approve_recurring_template(template_id: str, user_id: str):
    """Aprueba una plantilla recurrente."""
    template = database.session.get(RecurringJournalTemplate, template_id, with_for_update=True)
    if not template:
        raise RecurringJournalError(PLANTILLA_NO_ENCONTRADA)

    _validate_template_access(template, user_id, "autorizar")

    if template.status != "draft":
        raise RecurringJournalError("Solo se pueden aprobar plantillas en borrador.")

    template.status = "approved"
    template.docstatus = 1
    template.approved_by = user_id
    template.approved_at = database.func.now()
    log_submit(template)
    database.session.commit()


def cancel_recurring_template(template_id: str, reason: str, user_id: str):
    """Cancela una plantilla recurrente."""
    template = database.session.get(RecurringJournalTemplate, template_id)
    if not template:
        raise RecurringJournalError(PLANTILLA_NO_ENCONTRADA)

    _validate_template_access(template, user_id, "anular")

    template.status = "cancelled"
    template.docstatus = 2
    template.cancelled_by = user_id
    template.cancelled_at = database.func.now()
    template.cancel_reason = reason
    database.session.commit()


def get_applicable_templates(company: str, ledger_id: str, period_date: date) -> Sequence[RecurringJournalTemplate]:
    """Obtiene las plantillas aplicables para un periodo."""
    # Filtros: compañía, ledger, rango de fechas, estado aprobado, no completado
    stmt = select(RecurringJournalTemplate).where(
        RecurringJournalTemplate.company == company,
        or_(
            RecurringJournalTemplate.ledger_id == ledger_id,
            RecurringJournalTemplate.book_codes.contains(f'"{ledger_id}"'),
        ),
        RecurringJournalTemplate.start_date <= period_date,
        RecurringJournalTemplate.end_date >= period_date,
        RecurringJournalTemplate.status == "approved",
        RecurringJournalTemplate.is_completed.is_(False),
    )
    return database.session.execute(stmt).scalars().all()


def apply_recurring_template(
    template_id: str,
    fiscal_year: str,
    period_name: str,
    application_date: date,
    user_id: str,
    company: str | None = None,
) -> RecurringJournalApplication:
    """Aplica una plantilla recurrente a un periodo específico."""
    template = database.session.get(RecurringJournalTemplate, template_id, with_for_update=True)
    if not template:
        raise RecurringJournalError(PLANTILLA_NO_ENCONTRADA)
    _validate_template_access(template, user_id, "autorizar")
    if company is not None and template.company != company:
        raise RecurringJournalError("La plantilla recurrente no pertenece a la compañía del cierre.")
    if template.status != "approved":
        raise RecurringJournalError("Solo se pueden aplicar plantillas aprobadas.")
    if not template.start_date <= application_date <= template.end_date:
        raise RecurringJournalError("La fecha de aplicación está fuera de la vigencia de la plantilla.")

    # Verificar si ya fue aplicada
    existing = (
        database.session.query(RecurringJournalApplication)
        .filter_by(
            company=template.company,
            ledger_id=template.ledger_id,
            template_id=template.id,
            fiscal_year=fiscal_year,
            accounting_period=period_name,
        )
        .first()
    )

    if existing and existing.status in {"pending", "applied"}:
        raise RecurringJournalError(f"La plantilla ya fue aplicada al periodo {period_name}.")

    items = database.session.query(RecurringJournalItem).filter_by(template_id=template.id).all()
    if not items:
        raise RecurringJournalError("La plantilla aprobada no tiene líneas contables.")

    # Generar ComprobanteContable
    journal = ComprobanteContable(
        entity=template.company,
        book=template.ledger_id,
        book_codes=template.book_codes,
        naming_series_id=template.naming_series_id,
        date=application_date,
        memo=f"Generado automáticamente desde plantilla recurrente: {template.name}",
        status="draft",
        user_id=user_id,
        is_recurrent=True,
        recurrent_template_id=template.id,
    )
    database.session.add(journal)
    database.session.flush()

    from cacao_accounting.contabilidad.journal_service import _assign_identifier_if_needed

    _assign_identifier_if_needed(journal, template.naming_series_id)
    log_create(journal)

    # Generar líneas
    for idx, item in enumerate(items, start=1):
        line = ComprobanteContableDetalle(
            entity=template.company,
            account=item.account_code,
            value=item.debit if item.debit > 0 else -item.credit,
            memo=item.description,
            order=idx,
            cost_center=item.cost_center,
            unit=item.unit,
            project=item.project,
            third_type=item.party_type,
            third_code=item.party_id,
            transaction="journal_entry",
            transaction_id=journal.id,
            voucher_type="journal_entry",
        )
        database.session.add(line)

    # Registrar aplicación
    application = RecurringJournalApplication(
        company=template.company,
        ledger_id=template.ledger_id,
        template_id=template.id,
        fiscal_year=fiscal_year,
        accounting_period=period_name,
        application_date=application_date,
        status="pending",
        journal_id=journal.id,
        applied_by=user_id,
    )
    database.session.add(application)
    database.session.flush()
    journal.recurrent_application_id = application.id

    # La aplicación queda pendiente hasta que el comprobante pase al GL.
    database.session.commit()
    return application


def _normalize_account_code(company: str, account_value: Any) -> str:
    """Normaliza una cuenta recibida por id o por código hacia código contable."""
    account_text = str(account_value or "").strip()
    if not account_text:
        raise RecurringJournalError("Cada línea debe tener una cuenta contable.")

    account = database.session.get(Accounts, account_text)
    if account is not None:
        if account.entity != company:
            raise RecurringJournalError("La cuenta contable no pertenece a la compañía de la plantilla.")
        return str(account.code)

    account = (
        database.session.execute(database.select(Accounts).filter_by(entity=company, code=account_text)).scalars().first()
    )
    if account is None:
        raise RecurringJournalError("La cuenta contable indicada no existe para la compañía.")
    return str(account.code)


def _serialize_book_codes(books: Any) -> str | None:
    """Serializa la selección de libros para aplicar la plantilla."""
    if not books:
        return None
    if isinstance(books, str):
        return json.dumps([books])
    if isinstance(books, list):
        normalized = [str(book) for book in books if str(book)]
        return json.dumps(normalized) if normalized else None
    return None


def _authorized_template_books(company: str, requested: Any, user_id: str, action: str) -> list[str] | None:
    """Canonicaliza libros de una plantilla contra el ACL contable."""
    from cacao_accounting.database import User

    if database.session.get(User, user_id) is None:
        raise RecurringJournalError("El usuario indicado no existe o no puede autorizar libros contables.")
    permissions = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=user_id)
    granular_action = {
        "autorizar": "can_approve",
        "anular": "can_cancel",
        "consultar": "can_read",
        "listar": "can_read",
    }.get(action, "can_write")
    authorized = permissions.obtener_libros_autorizados(granular_action, company=company, return_codes=True)
    active = database.session.execute(
        database.select(Book)
        .where(Book.entity == company)
        .where(Book.status == "activo")
        .where(Book.code.in_(authorized))
        .order_by(Book.is_primary.desc(), Book.code)
    ).scalars()
    active_codes = [book.code for book in active]
    if not active_codes:
        raise RecurringJournalError("El usuario no tiene libros contables autorizados para la compañía.")
    active_books = database.session.execute(
        database.select(Book).where(Book.entity == company).where(Book.status == "activo")
    ).scalars()
    references = {str(value): book.code for book in active_books for value in (book.id, book.code)}
    selected = [references.get(str(value), str(value)) for value in (_normalize_requested_books(requested) or active_codes)]
    invalid = set(selected) - set(active_codes)
    if invalid:
        raise RecurringJournalError(f"El usuario no tiene acceso al libro contable {sorted(invalid)[0]}.")
    return [code for code in active_codes if code in selected]


def _normalize_requested_books(value: Any) -> list[str] | None:
    """Normaliza códigos de libros recibidos desde formularios o servicios."""
    if value is None:
        return None
    if isinstance(value, str):
        return [value] if value else None
    if isinstance(value, (list, tuple, set)):
        values = [str(item) for item in value if str(item)]
        return values or None
    raise RecurringJournalError("La selección de libros no tiene un formato válido.")


def _validate_template_access(template: RecurringJournalTemplate, user_id: str, action: str) -> None:
    """Revalida compañía y todos los libros antes de una transición."""
    validate_recurring_template_access(template, user_id, action)


def validate_recurring_template_access(
    template: RecurringJournalTemplate,
    user_id: str,
    action: str = "consultar",
) -> None:
    """Valida todos los libros persistidos, incluido el principal legacy."""
    selected = _deserialize_book_codes(template.book_codes) or []
    if template.ledger_id and template.ledger_id not in selected:
        selected.append(str(template.ledger_id))
    if not selected:
        raise RecurringJournalError("La plantilla no tiene una selección canónica de libros contables.")
    _authorized_template_books(template.company, selected, user_id, action)


def accessible_recurring_template_ids(user_id: str) -> list[str]:
    """Retorna plantillas cuyos libros completos son legibles por el usuario."""
    templates = database.session.execute(database.select(RecurringJournalTemplate)).scalars()
    accessible: list[str] = []
    for template in templates:
        try:
            validate_recurring_template_access(template, user_id, "listar")
        except RecurringJournalError:
            continue
        accessible.append(str(template.id))
    return accessible


def _canonical_book_reference(company: str, value: Any) -> str | None:
    """Convierte id o código de libro a su código canónico."""
    if not value:
        return None
    book = database.session.execute(
        database.select(Book).where(Book.entity == company).where((Book.id == str(value)) | (Book.code == str(value)))
    ).scalar_one_or_none()
    return book.code if book else str(value)


def _deserialize_book_codes(value: str | None) -> list[str] | None:
    """Lee la selección persistida de libros."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RecurringJournalError("La selección persistida de libros no es válida.") from exc
    return _normalize_requested_books(parsed)
