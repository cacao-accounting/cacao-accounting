# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de extractos bancarios."""

from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any

from cacao_accounting.database import BankAccount, BankTransaction, database
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.imports.readers.base import NumericCellValue
from cacao_accounting.imports.utils.dates import parse_import_date
from cacao_accounting.numbers import coerce_decimal
from sqlalchemy.exc import IntegrityError


from cacao_accounting.i18n import _


def _text(value: Any, default: str = "") -> str:
    """Normaliza celdas vacías de XLSX/ODS sin convertirlas en "None"."""
    if value is None:
        return default
    text = str(value)
    return text if text.strip() else default


def _is_bank_identity_conflict(error: IntegrityError) -> bool:
    """Indica si el error corresponde a la identidad única del movimiento."""
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == "uq_bank_transaction_identity":
        return True
    message = str(original).lower()
    return "uq_bank_transaction_identity" in message or "bank_transaction.identity_key" in message


class BankStatementAdapter(BaseImportAdapter):
    """Adaptador para Extractos Bancarios."""

    # Una referencia bancaria es informativa; movimientos distintos pueden compartirla.
    group_by_reference = False

    columns = [
        "bank_account_id",
        "posting_date",
        "reference_number",
        "description",
        "deposit",
        "withdrawal",
    ]
    column_aliases = {"reference": "reference_number"}
    required_columns = ["bank_account_id", "posting_date"]

    @staticmethod
    def _valid_grouped_integer(integer_part: str, thousands_sep: str) -> bool:
        """Valida que la parte entera use agrupación de miles de tres dígitos.

        Con ambos separadores presentes, el que no es decimal solo puede ser
        separador de miles. ``1,234,567`` y ``1.234.567`` son inequívocos;
        ``12,34`` no lo es y corrompería el importe si se elimina el separador.
        """
        body = integer_part[1:] if integer_part[:1] in "+-" else integer_part
        groups = body.split(thousands_sep)
        if len(groups) < 2:
            return False
        return (
            groups[0].isdigit()
            and 1 <= len(groups[0]) <= 3
            and all(len(group) == 3 and group.isdigit() for group in groups[1:])
        )

    @staticmethod
    def _numeric_cell_amount(value: NumericCellValue) -> Decimal | None:
        """Convierte una celda numérica sin interpretar separadores de texto."""
        amount = coerce_decimal(str(value), "monto", max_fractional_digits=4)
        return amount if amount != 0 else None

    @staticmethod
    def _optional_amount(value: Any) -> Decimal | None:
        """Convierte una columna vacía o cero en un lado bancario ausente.

        Los importes con separadores ambiguos se rechazan en lugar de
        interpretarse: un importe con milés por convención europea que se
        lea como decimales corrompe el extracto por un factor de 1000.
        ``1.000,00`` y ``1,234.56`` son inequívocos; ``1.000``, ``1,000`` y
        ``12,34.56`` no lo son y abortan la fila con un error de negocio.
        """
        if value is None:
            return None
        if isinstance(value, NumericCellValue):
            return BankStatementAdapter._numeric_cell_amount(value)
        normalized = str(value).strip().replace(" ", "")
        if normalized == "":
            return None
        if "," in normalized and "." in normalized:
            decimal_sep = "," if normalized.rfind(",") > normalized.rfind(".") else "."
            thousands_sep = "." if decimal_sep == "," else ","
            integer_part, decimal_part = normalized.rsplit(decimal_sep, 1)
            if not decimal_part.isdigit() or not BankStatementAdapter._valid_grouped_integer(integer_part, thousands_sep):
                raise InvalidOperation(_("Separador de miles ambiguo"))
            normalized = integer_part.replace(thousands_sep, "") + "." + decimal_part
        elif "," in normalized:
            decimal_part = normalized.rsplit(",", 1)[1]
            if len(decimal_part) > 2:
                raise InvalidOperation(_("Separador de miles ambiguo"))
            normalized = normalized.replace(",", ".")
        elif normalized.count(".") > 1:
            raise InvalidOperation(_("Separador de miles ambiguo"))
        elif "." in normalized:
            decimal_part = normalized.rsplit(".", 1)[1]
            if len(decimal_part) == 3:
                raise InvalidOperation(_("Separador de miles ambiguo"))
        amount = coerce_decimal(normalized, "monto", max_fractional_digits=4)
        return amount if amount != 0 else None

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Validate a single bank statement row."""
        errors = super().validate_row(row_data)
        bank_account = database.session.get(BankAccount, _text(row_data.get("bank_account_id")))
        if bank_account is None:
            errors.append(f"Cuenta bancaria no encontrada: {row_data.get('bank_account_id')}")
        raw_date = row_data.get("posting_date")
        try:
            if not parse_import_date(raw_date, field="fecha bancaria"):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"Fecha bancaria inválida: {raw_date}")

        amounts: dict[str, Decimal | None] = {}
        for field in ("deposit", "withdrawal"):
            try:
                amounts[field] = self._optional_amount(row_data.get(field))
            except (InvalidOperation, TypeError, ValueError) as exc:
                amounts[field] = None
                errors.append(f"Monto bancario inválido en columna '{field}': {row_data.get(field)} ({exc})")
            else:
                amt = amounts[field]
                if amt is not None and amt < 0:
                    errors.append(f"El monto bancario en columna '{field}' no puede ser negativo.")
        if (
            amounts["deposit"] is None
            and amounts["withdrawal"] is None
            and not any(f"columna '{field}'" in error for error in errors for field in ("deposit", "withdrawal"))
        ):
            errors.append("La fila bancaria debe contener un depósito o un retiro mayor que cero.")
        if amounts["deposit"] is not None and amounts["withdrawal"] is not None:
            errors.append("Una fila bancaria no puede contener depósito y retiro simultáneamente.")
        return errors

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Valida compañía de la cuenta y período de cada transacción."""
        from cacao_accounting.imports.utils.validation import is_period_open

        company_id = (context or {}).get("company_id") or ""
        errors: list[str] = []
        for row in document_data:
            bank_account = database.session.get(BankAccount, _text(row.get("bank_account_id")))
            if bank_account and bank_account.company != company_id:
                errors.append(
                    f"La cuenta bancaria {bank_account.id} pertenece a la compañía "
                    f"{bank_account.company}, no a {company_id}."
                )
            try:
                posting_date = parse_import_date(row.get("posting_date"), field="fecha bancaria")
            except (TypeError, ValueError):
                continue
            if not is_period_open(company_id, posting_date):
                errors.append(f"El periodo contable para la fecha {posting_date} está cerrado o no existe.")
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build bank transactions from the imported data."""
        transactions = []
        fingerprint = str(context.get("import_fingerprint") or "")
        for position, row in enumerate(document_data, start=1):
            posting_date = row.get("posting_date")
            try:
                posting_date = parse_import_date(posting_date, field="fecha bancaria")
            except ValueError as exc:
                raise ValueError(_("Fecha bancaria inválida: %(date)s") % {"date": posting_date}) from exc
            deposit = self._optional_amount(row.get("deposit"))
            withdrawal = self._optional_amount(row.get("withdrawal"))
            if (deposit is not None and deposit < 0) or (withdrawal is not None and withdrawal < 0):
                raise ValueError(_("El monto bancario no puede ser negativo."))
            row_number = getattr(row, "row_number", position)
            transactions.append(
                {
                    "bank_account_id": _text(row.get("bank_account_id")),
                    "company_id": context.get("company_id"),
                    "posting_date": posting_date,
                    "reference_number": _text(row.get("reference_number") or row.get("reference")),
                    "description": _text(row.get("description")),
                    "deposit": deposit,
                    "withdrawal": withdrawal,
                    "import_discriminator": f"{fingerprint}:{row_number}" if fingerprint else "",
                }
            )
            if deposit is not None and withdrawal is not None:
                raise ValueError(_("Una fila bancaria no puede contener depósito y retiro simultáneamente."))
        return transactions

    def persist_document(self, document: Any) -> None:
        """Persist bank transactions to the database."""
        persisted_ids: list[str] = []
        seen_in_batch: set[str] = set()
        # La comprobación de duplicados y la inserción deben ejecutarse bajo el
        # mismo lock por cuenta. Dos importaciones concurrentes del mismo
        # extracto esperan su turno; la segunda ya ve la fila confirmada por la
        # primera en lugar de insertar un duplicado (#2172). El orden estable
        # evita interbloqueos cuando el lote toca varias cuentas.
        for bank_account_id in sorted(
            {str(tx_data.get("bank_account_id") or "") for tx_data in document if tx_data.get("bank_account_id")}
        ):
            database.session.execute(
                database.select(BankAccount)
                .where(BankAccount.id == bank_account_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).scalar_one_or_none()
        for tx_data in document:
            self._validate_row_account(tx_data)
            reference_number = str(tx_data.get("reference_number") or "")
            if reference_number and self._has_existing_reference(tx_data, reference_number, seen_in_batch):
                raise ValueError(_("La transacción bancaria ya existe en la base de datos."))
            tx = self._build_transaction(tx_data, reference_number)
            if not self._insert_transaction(tx, reference_number):
                continue
            seen_in_batch.add(str(tx.id))
            persisted_ids.append(str(tx.id))
        self._auto_reconcile(persisted_ids)

    @staticmethod
    def _validate_row_account(tx_data: dict[str, Any]) -> None:
        """Valida que la cuenta bancaria exista y pertenezca a la compañía."""
        bank_account = database.session.get(BankAccount, tx_data["bank_account_id"])
        if bank_account is None:
            raise ValueError(_("Cuenta bancaria no encontrada: %(account)s") % {"account": tx_data["bank_account_id"]})
        company_id = tx_data.get("company_id")
        if company_id and bank_account.company != company_id:
            raise ValueError(
                _("La cuenta bancaria %(bank_account_id)s pertenece a la compañía %(bank_company)s, " "no a %(company_id)s.")
                % {
                    "bank_account_id": bank_account.id,
                    "bank_company": bank_account.company,
                    "company_id": company_id,
                }
            )

    @staticmethod
    def _has_existing_reference(tx_data: dict[str, Any], reference_number: str, seen_in_batch: set[str]) -> bool:
        """Indica si ya existe un movimiento con la misma identidad económica.

        Solo aplica con referencia bancaria (#1262): sin referencia, fecha e
        importe no identifican de forma segura un movimiento.
        """
        return (
            database.session.execute(
                database.select(BankTransaction)
                .filter_by(
                    bank_account_id=tx_data["bank_account_id"],
                    posting_date=tx_data["posting_date"],
                    reference_number=reference_number,
                    deposit=tx_data.get("deposit"),
                    withdrawal=tx_data.get("withdrawal"),
                )
                .filter(~BankTransaction.id.in_(list(seen_in_batch)))
            )
            .scalars()
            .first()
        ) is not None

    @staticmethod
    def _build_transaction(tx_data: dict[str, Any], reference_number: str) -> Any:
        """Construye la transacción; sin referencia conserva su procedencia."""
        return BankTransaction(
            bank_account_id=tx_data["bank_account_id"],
            posting_date=tx_data["posting_date"],
            reference_number=reference_number,
            description=tx_data.get("description", ""),
            deposit=tx_data.get("deposit"),
            withdrawal=tx_data.get("withdrawal"),
            import_reference=(None if reference_number else (tx_data.get("import_discriminator") or None)),
        )

    @staticmethod
    def _insert_transaction(tx: Any, reference_number: str) -> bool:
        """Inserta la transacción; devuelve ``False`` si fue un reimport idempotente."""
        try:
            with database.session.begin_nested():
                database.session.add(tx)
                database.session.flush()
        except IntegrityError as exc:
            if not _is_bank_identity_conflict(exc):
                raise
            if not reference_number:
                # Reimportar exactamente el mismo archivo (misma huella y fila)
                # es idempotente: la fila ya existe, no es un duplicado (#1262).
                return False
            raise ValueError(_("La transacción bancaria ya existe en la base de datos.")) from exc
        return True

    def _auto_reconcile(self, persisted_ids: list[str]) -> None:
        """Intenta la conciliación automática opcional de las filas importadas.

        Solo actúa cuando existen reglas activas con ``auto_reconcile``
        habilitado; un fallo de conciliación individual no revierte la
        importación y deja la transacción pendiente para revisión manual.
        """
        if not persisted_ids:
            return
        from cacao_accounting.bancos.reconciliation_service import BankReconciliationError
        from cacao_accounting.bancos.statement_service import (
            BankStatementError,
            auto_reconcile_bank_transaction,
        )

        for transaction_id in persisted_ids:
            try:
                # Savepoint: un fallo controlado de conciliación automática no
                # revierte la importación de la fila del extracto; el propio
                # context manager deshace solo el intento fallido.
                with database.session.begin_nested():
                    auto_reconcile_bank_transaction(transaction_id)
            except (BankStatementError, BankReconciliationError):
                pass
