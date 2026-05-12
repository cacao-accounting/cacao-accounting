# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para gestión de comprobantes recurrentes."""

from datetime import date
from typing import Any, Dict, List, Sequence
from sqlalchemy import select
from cacao_accounting.database import (
    database,
    RecurringJournalTemplate,
    RecurringJournalItem,
    RecurringJournalApplication,
    ComprobanteContable,
    ComprobanteContableDetalle,
)


class RecurringJournalError(Exception):
    """Error base para comprobantes recurrentes."""


def create_recurring_template(data: Dict[str, Any], items: List[Dict[str, Any]], user_id: str) -> RecurringJournalTemplate:
    """Crea una nueva plantilla de comprobante recurrente."""
    validate_template_balance(items)

    template = RecurringJournalTemplate(
        code=data["code"],
        company=data["company"],
        ledger_id=data.get("ledger_id"),
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

    for idx, item in enumerate(items):
        line = RecurringJournalItem(
            template_id=template.id,
            account_code=item["account_code"],
            debit=item.get("debit", 0),
            credit=item.get("credit", 0),
            description=item.get("description"),
            cost_center=item.get("cost_center"),
            unit=item.get("unit"),
            project=item.get("project"),
            party_type=item.get("party_type"),
            party_id=item.get("party_id"),
            reference_type=item.get("reference_type"),
            reference_name=item.get("reference_name"),
            reference1=item.get("reference1"),
            reference2=item.get("reference2"),
            is_advance=bool(item.get("is_advance")),
            status="active",
            created_by=user_id,
        )
        database.session.add(line)

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
    template = database.session.get(RecurringJournalTemplate, template_id)
    if not template:
        raise RecurringJournalError("Plantilla no encontrada.")

    if template.status != "draft":
        raise RecurringJournalError("Solo se pueden aprobar plantillas en borrador.")

    template.status = "approved"
    template.docstatus = 1
    template.approved_by = user_id
    template.approved_at = database.func.now()
    database.session.commit()


def cancel_recurring_template(template_id: str, reason: str, user_id: str):
    """Cancela una plantilla recurrente."""
    template = database.session.get(RecurringJournalTemplate, template_id)
    if not template:
        raise RecurringJournalError("Plantilla no encontrada.")

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
        RecurringJournalTemplate.ledger_id == ledger_id,
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
) -> RecurringJournalApplication:
    """Aplica una plantilla recurrente a un periodo específico."""
    template = database.session.get(RecurringJournalTemplate, template_id)
    if not template:
        raise RecurringJournalError("Plantilla no encontrada.")

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

    if existing and existing.status == "applied":
        raise RecurringJournalError(f"La plantilla ya fue aplicada al periodo {period_name}.")

    # Generar ComprobanteContable
    journal = ComprobanteContable(
        entity=template.company,
        book=template.ledger_id,
        date=application_date,
        memo=f"Generado automáticamente desde plantilla recurrente: {template.name}",
        status="draft",
        user_id=user_id,
        is_recurrent=True,
        recurrent_template_id=template.id,
    )
    database.session.add(journal)
    database.session.flush()

    # Generar líneas
    items = database.session.query(RecurringJournalItem).filter_by(template_id=template.id).all()
    for item in items:
        line = ComprobanteContableDetalle(
            entity=template.company,
            account=item.account_code,
            value=item.debit if item.debit > 0 else -item.credit,
            memo=item.description,
            cost_center=item.cost_center,
            unit=item.unit,
            project=item.project,
            third_type=item.party_type,
            third_code=item.party_id,
            internal_reference=item.reference_type,
            internal_reference_id=item.reference_name,
            reference1=item.reference1,
            reference2=item.reference2,
            is_advance=item.is_advance,
            transaction_id=journal.id,
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
        status="applied",
        journal_id=journal.id,
        applied_by=user_id,
    )
    database.session.add(application)

    template.last_applied_date = application_date
    # Lógica para marcar como completado si es la última aplicación según end_date
    # (Simplificado: si la fecha de aplicación >= end_date)
    if application_date >= template.end_date:
        template.is_completed = True
        template.status = "completed"
        template.docstatus = 3

    database.session.commit()
    return application
