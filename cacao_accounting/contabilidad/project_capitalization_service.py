# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Servicio para la Capitalización Automática de Proyectos."""

from decimal import Decimal
from datetime import date
from cacao_accounting.database import database, GLEntry, Project, Accounts, ComprobanteContable, ComprobanteContableDetalle
from cacao_accounting.contabilidad.journal_service import submit_journal
from cacao_accounting.logs import log


class ProjectCapitalizationService:
    """Servicio encargado de la capitalización automática de movimientos de proyectos."""

    def run_capitalization(self, company: str, period_id: str, user_id: str) -> tuple[int, list[str]]:
        """Busca movimientos elegibles y genera sus comprobantes de capitalización automática (JV/CC)."""
        success_count = 0
        errors = []

        # Find eligible movements of the period:
        # 1. Project code is not null.
        # 2. Account classification is "Gastos".
        # 3. Not cancelled.
        # 4. Either (not is_reversal and debit > 0) OR (is_reversal and credit > 0).
        entries = (
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

        for entry in entries:
            # We must process either non-reversal with debit > 0, or reversal with credit > 0
            if not entry.is_reversal and not (entry.debit > 0):
                continue
            if entry.is_reversal and not (entry.credit > 0):
                continue

            try:
                # Check project settings
                proj = (
                    database.session.execute(database.select(Project).filter_by(entity=company, code=entry.project_code))
                    .scalars()
                    .first()
                )
                if not proj or not proj.capitalizable:
                    continue
                if not proj.capitalization_account_id:
                    continue

                # Check if already capitalized to prevent duplicate run
                orig_journal = database.session.get(ComprobanteContable, entry.voucher_id)
                if orig_journal and orig_journal.capitalized_by_id:
                    continue

                # Get capitalization account details
                cap_account = database.session.get(Accounts, proj.capitalization_account_id)
                if not cap_account:
                    raise ValueError(f"La cuenta de activo de capitalización para el proyecto {proj.code} no existe.")

                # Generate unique document number
                today = date.today()
                from uuid import uuid4

                unique_suffix = str(uuid4())[:8].upper()
                doc_no = f"CAP-{today.year}-{today.month:02d}-{unique_suffix}"

                # Generate the Capitalization Journal Document
                cap_journal = ComprobanteContable(
                    id=f"CAP-{unique_suffix}",
                    entity=company,
                    date=entry.posting_date,
                    status="draft",
                    transaction_currency=entry.account_currency or "NIO",
                    exchange_rate=entry.exchange_rate or Decimal("1.0"),
                    voucher_type="Capitalización Automática de Proyecto",
                    document_no=doc_no,
                    capitalization_origin_id=entry.voucher_id,
                )
                database.session.add(cap_journal)
                database.session.flush()

                orig_doc_no = entry.document_no or "JV-000000"
                memo_text = f"Capitalización automática ({orig_doc_no})"

                # Check if this is a normal or a reversal entry
                if not entry.is_reversal:
                    # Normal entry: Debit Active (+), Credit Expense (-)
                    val = entry.debit
                    deb_acc_code = cap_account.code
                    cred_acc_code = entry.account_code
                else:
                    # Reversal entry: Debit Expense (+), Credit Active (-)
                    val = entry.credit
                    deb_acc_code = entry.account_code
                    cred_acc_code = cap_account.code

                # Create Debit Line (positive value)
                deb_line = ComprobanteContableDetalle(
                    transaction="journal_entry",
                    transaction_id=cap_journal.id,
                    entity=company,
                    account=deb_acc_code,
                    value=val,
                    project=entry.project_code,
                    unit=entry.unit_code,
                    cost_center=entry.cost_center_code,
                    date=entry.posting_date,
                    memo=memo_text,
                    currency_id=entry.account_currency or "NIO",
                    exchange_rate=entry.exchange_rate or Decimal("1.0"),
                )

                # Create Credit Line (negative value)
                cred_line = ComprobanteContableDetalle(
                    transaction="journal_entry",
                    transaction_id=cap_journal.id,
                    entity=company,
                    account=cred_acc_code,
                    value=-val,
                    project=entry.project_code,
                    unit=entry.unit_code,
                    cost_center=entry.cost_center_code,
                    date=entry.posting_date,
                    memo=memo_text,
                    currency_id=entry.account_currency or "NIO",
                    exchange_rate=entry.exchange_rate or Decimal("1.0"),
                )

                database.session.add(deb_line)
                database.session.add(cred_line)
                database.session.flush()

                # Submit to post GL
                submit_journal(cap_journal.id)

                # Link original journal
                if orig_journal:
                    orig_journal.capitalized_by_id = cap_journal.id

                database.session.flush()
                success_count += 1

            except Exception as e:
                database.session.rollback()
                log.exception(f"Error capitalizando entrada {entry.id}")
                errors.append(f"Entrada {entry.document_no or entry.id}: {str(e)}")

        database.session.commit()
        return success_count, errors
