# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio para la Capitalización Automática de Proyectos."""

import json
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy import func

from cacao_accounting.database import (
    database,
    GLEntry,
    Project,
    Accounts,
    ComprobanteContable,
    ComprobanteContableDetalle,
    Book,
)
from cacao_accounting.contabilidad.journal_service import submit_journal
from cacao_accounting.ledger_queries import primary_ledger_id
from cacao_accounting.logs import log


@dataclass(frozen=True)
class CapitalizationLine:
    """Línea fuente normalizada para un comprobante de capitalización."""

    entry: GLEntry
    debit_account_code: str
    credit_account_code: str
    value: Decimal


def _is_eligible_capitalization_entry(entry: GLEntry) -> bool:
    """Determina si una entrada GL es elegible para capitalizacion."""
    if entry.is_reversal:
        return entry.credit > 0
    return entry.debit > 0


def _find_capitalizable_project(company: str, project_code: str) -> Project | None:
    """Busca un proyecto capitalizable activo para el codigo dado."""
    proj = database.session.execute(database.select(Project).filter_by(entity=company, code=project_code)).scalars().first()
    if not proj or not proj.capitalizable or not proj.capitalization_account_id:
        return None
    return proj


def _is_already_capitalized(entry: GLEntry) -> bool:
    """Verifica si la entrada ya fue capitalizada."""
    orig_journal = database.session.get(ComprobanteContable, entry.voucher_id)
    return bool(orig_journal and orig_journal.capitalized_by_id)


def _resolve_capitalization_accounts(entry: GLEntry, proj: Project) -> tuple[str, str, Decimal]:
    """Resuelve las cuentas de debito y credito y el monto para la capitalizacion."""
    cap_account = database.session.get(Accounts, proj.capitalization_account_id)
    if not cap_account:
        raise ValueError(f"La cuenta de activo de capitalizacion para el proyecto {proj.code} no existe.")

    if not entry.is_reversal:
        value = entry.debit_in_account_currency if entry.debit_in_account_currency is not None else entry.debit
        return cap_account.code, entry.account_code, value
    value = entry.credit_in_account_currency if entry.credit_in_account_currency is not None else entry.credit
    return entry.account_code, cap_account.code, value


def _create_capitalization_journal(
    company: str,
    lines: list[CapitalizationLine],
    user_id: str,
) -> ComprobanteContable:
    """Crea un comprobante que capitaliza todas las líneas de un documento fuente."""
    if not lines:
        raise ValueError("No hay líneas elegibles para capitalizar.")
    entry = lines[0].entry
    unique_suffix = str(uuid4())[:8].upper()
    today = date.today()
    doc_no = f"CAP-{today.year}-{today.month:02d}-{unique_suffix}"

    transaction_currency = entry.account_currency or entry.company_currency
    if not transaction_currency:
        raise ValueError("No se pudo determinar la moneda del movimiento a capitalizar.")

    cap_journal = ComprobanteContable(
        id=f"CAP-{unique_suffix}",
        entity=company,
        user_id=user_id,
        date=entry.posting_date,
        status="draft",
        transaction_currency=transaction_currency,
        # Resolve the rate independently for each active book at posting time.
        exchange_rate=None,
        voucher_type="Capitalización Automática de Proyecto",
        document_no=doc_no,
        capitalization_origin_id=entry.voucher_id,
        book_codes=json.dumps(
            [
                book.code
                for book in database.session.execute(
                    database.select(Book).where(Book.entity == company, Book.status == "activo").order_by(Book.code)
                ).scalars()
            ]
        ),
    )
    database.session.add(cap_journal)
    database.session.flush()

    for capitalization_line in lines:
        source = capitalization_line.entry
        source_currency = source.account_currency or source.company_currency
        if source_currency != transaction_currency:
            raise ValueError("Un comprobante fuente contiene líneas capitalizables en monedas incompatibles.")
        orig_doc_no = source.document_no or "JV-000000"
        common_kwargs: dict[str, Any] = {
            "transaction": "journal_entry",
            "transaction_id": cap_journal.id,
            "entity": company,
            "project": source.project_code,
            "unit": source.unit_code,
            "cost_center": source.cost_center_code,
            "date": source.posting_date,
            "memo": f"Capitalizacion automatica ({orig_doc_no})",
            "currency_id": transaction_currency,
            "exchange_rate": None,
        }
        database.session.add(
            ComprobanteContableDetalle(
                account=capitalization_line.debit_account_code,
                value=capitalization_line.value,
                **common_kwargs,
            )
        )
        database.session.add(
            ComprobanteContableDetalle(
                account=capitalization_line.credit_account_code,
                value=-capitalization_line.value,
                **common_kwargs,
            )
        )
    database.session.flush()

    return cap_journal


class ProjectCapitalizationService:
    """Servicio encargado de la capitalizacion automatica de movimientos de proyectos."""

    def run_capitalization(self, company: str, period_id: str, user_id: str) -> tuple[int, list[str]]:
        """Busca movimientos elegibles y genera sus comprobantes de capitalizacion automatica (JV/CC)."""
        success_count = 0
        errors: list[str] = []

        groups = self._capitalization_groups(company, period_id)

        for voucher_id, lines in groups.items():
            try:
                if self._process_group(company, voucher_id, lines, user_id):
                    success_count += 1
            except Exception as e:
                database.session.rollback()
                log.exception(f"Error capitalizando comprobante {voucher_id}")
                errors.append(f"Comprobante {voucher_id}: {str(e)}")

        database.session.commit()
        return success_count, errors

    @classmethod
    def _capitalization_groups(cls, company: str, period_id: str) -> dict[str, list[CapitalizationLine]]:
        """Agrupa todas las líneas elegibles por comprobante fuente."""
        groups: dict[str, list[CapitalizationLine]] = {}
        for entry in cls._query_eligible_entries(company, period_id):
            if not _is_eligible_capitalization_entry(entry) or _is_already_capitalized(entry):
                continue
            project = _find_capitalizable_project(company, entry.project_code)
            if not project:
                continue
            debit_code, credit_code, value = _resolve_capitalization_accounts(entry, project)
            groups.setdefault(entry.voucher_id, []).append(
                CapitalizationLine(
                    entry=entry,
                    debit_account_code=debit_code,
                    credit_account_code=credit_code,
                    value=value,
                )
            )
        return groups

    @staticmethod
    def _query_eligible_entries(company: str, period_id: str) -> list[GLEntry]:
        """Consulta las entradas GL elegibles para capitalizacion."""
        query = (
            database.session.query(GLEntry)
            .join(Accounts, GLEntry.account_id == Accounts.id)
            .filter(
                GLEntry.company == company,
                GLEntry.accounting_period_id == period_id,
                GLEntry.is_cancelled.is_(False),
                GLEntry.is_reversal.is_(False),
                GLEntry.project_code.isnot(None),
                func.lower(Accounts.classification).in_(["gasto", "gastos", "expense"]),
            )
        )
        ledger_id = primary_ledger_id(company)
        if ledger_id:
            query = query.filter(GLEntry.ledger_id == ledger_id)
        return query.all()

    @staticmethod
    def _process_group(
        company: str,
        voucher_id: str,
        lines: list[CapitalizationLine],
        user_id: str,
    ) -> bool:
        """Capitaliza atómicamente todas las líneas elegibles de un comprobante."""
        orig_journal = database.session.get(ComprobanteContable, voucher_id, with_for_update=True)
        if not orig_journal or orig_journal.capitalized_by_id:
            return False

        cap_journal = _create_capitalization_journal(company, lines, user_id)
        orig_journal.capitalized_by_id = cap_journal.id
        database.session.add(orig_journal)

        submit_journal(cap_journal.id)
        return True
