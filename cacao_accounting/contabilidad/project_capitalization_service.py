# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio para la Capitalización Automática de Proyectos."""

from decimal import Decimal
from datetime import date
from typing import Any
from uuid import uuid4

from cacao_accounting.database import database, GLEntry, Project, Accounts, ComprobanteContable, ComprobanteContableDetalle
from cacao_accounting.contabilidad.journal_service import submit_journal
from cacao_accounting.logs import log


def _is_eligible_capitalization_entry(entry: GLEntry) -> bool:
    """Determina si una entrada GL es elegible para capitalizacion."""
    if entry.is_reversal:
        return entry.credit > 0
    return entry.debit > 0


def _find_capitalizable_project(company: str, project_code: str) -> Project | None:
    """Busca un proyecto capitalizable activo para el codigo dado."""
    proj = (
        database.session.execute(database.select(Project).filter_by(entity=company, code=project_code))
        .scalars()
        .first()
    )
    if not proj or not proj.capitalizable or not proj.capitalization_account_id:
        return None
    return proj


def _is_already_capitalized(entry: GLEntry) -> bool:
    """Verifica si la entrada ya fue capitalizada."""
    orig_journal = database.session.get(ComprobanteContable, entry.voucher_id)
    return bool(orig_journal and orig_journal.capitalized_by_id)


def _resolve_capitalization_accounts(
    entry: GLEntry, proj: Project
) -> tuple[str, str, Decimal]:
    """Resuelve las cuentas de debito y credito y el monto para la capitalizacion."""
    cap_account = database.session.get(Accounts, proj.capitalization_account_id)
    if not cap_account:
        raise ValueError(f"La cuenta de activo de capitalizacion para el proyecto {proj.code} no existe.")

    if not entry.is_reversal:
        return cap_account.code, entry.account_code, entry.debit
    return entry.account_code, cap_account.code, entry.credit


def _create_capitalization_journal(
    company: str,
    entry: GLEntry,
    deb_acc_code: str,
    cred_acc_code: str,
    val: Decimal,
) -> ComprobanteContable:
    """Crea el comprobante de capitalizacion con sus lineas."""
    unique_suffix = str(uuid4())[:8].upper()
    today = date.today()
    doc_no = f"CAP-{today.year}-{today.month:02d}-{unique_suffix}"

    cap_journal = ComprobanteContable(
        id=f"CAP-{unique_suffix}",
        entity=company,
        date=entry.posting_date,
        status="draft",
        transaction_currency=entry.account_currency or "NIO",
        exchange_rate=entry.exchange_rate or Decimal("1.0"),
        voucher_type="Capitalizacion Automatica de Proyecto",
        document_no=doc_no,
        capitalization_origin_id=entry.voucher_id,
    )
    database.session.add(cap_journal)
    database.session.flush()

    orig_doc_no = entry.document_no or "JV-000000"
    memo_text = f"Capitalizacion automatica ({orig_doc_no})"
    common_kwargs: dict[str, Any] = {
        "transaction": "journal_entry",
        "transaction_id": cap_journal.id,
        "entity": company,
        "project": entry.project_code,
        "unit": entry.unit_code,
        "cost_center": entry.cost_center_code,
        "date": entry.posting_date,
        "memo": memo_text,
        "currency_id": entry.account_currency or "NIO",
        "exchange_rate": entry.exchange_rate or Decimal("1.0"),
    }

    database.session.add(ComprobanteContableDetalle(account=deb_acc_code, value=val, **common_kwargs))
    database.session.add(ComprobanteContableDetalle(account=cred_acc_code, value=-val, **common_kwargs))
    database.session.flush()

    return cap_journal


class ProjectCapitalizationService:
    """Servicio encargado de la capitalizacion automatica de movimientos de proyectos."""

    def run_capitalization(self, company: str, period_id: str, user_id: str) -> tuple[int, list[str]]:
        """Busca movimientos elegibles y genera sus comprobantes de capitalizacion automatica (JV/CC)."""
        success_count = 0
        errors: list[str] = []

        entries = self._query_eligible_entries(company, period_id)

        for entry in entries:
            if not _is_eligible_capitalization_entry(entry):
                continue
            try:
                self._process_single_entry(company, entry)
                success_count += 1
            except Exception as e:
                database.session.rollback()
                log.exception(f"Error capitalizando entrada {entry.id}")
                errors.append(f"Entrada {entry.document_no or entry.id}: {str(e)}")

        database.session.commit()
        return success_count, errors

    @staticmethod
    def _query_eligible_entries(company: str, period_id: str) -> list[GLEntry]:
        """Consulta las entradas GL elegibles para capitalizacion."""
        return (
            database.session.query(GLEntry)
            .join(Accounts, GLEntry.account_id == Accounts.id)
            .filter(
                GLEntry.company == company,
                GLEntry.accounting_period_id == period_id,
                GLEntry.is_cancelled.is_(False),
                GLEntry.project_code.isnot(None),
                Accounts.classification.in_(["Gastos", "expense", "gastos", "EXPENSE"]),
            )
            .all()
        )

    @staticmethod
    def _process_single_entry(company: str, entry: GLEntry) -> None:
        """Procesa una unica entrada GL para capitalizacion."""
        proj = _find_capitalizable_project(company, entry.project_code)
        if not proj:
            return
        if _is_already_capitalized(entry):
            return

        deb_acc_code, cred_acc_code, val = _resolve_capitalization_accounts(entry, proj)
        cap_journal = _create_capitalization_journal(company, entry, deb_acc_code, cred_acc_code, val)

        submit_journal(cap_journal.id)

        orig_journal = database.session.get(ComprobanteContable, entry.voucher_id)
        if orig_journal:
            orig_journal.capitalized_by_id = cap_journal.id

        database.session.flush()
