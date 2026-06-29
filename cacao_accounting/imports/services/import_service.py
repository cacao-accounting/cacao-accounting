# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio centralizado de importación."""

import threading
from datetime import datetime
from typing import Dict, Type, List, Any
from flask import current_app
from cacao_accounting.database import database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.readers.csv_reader import CSVReader
from cacao_accounting.imports.readers.xls_reader import XLSReader
from cacao_accounting.imports.readers.xlsx_reader import XLSXReader
from cacao_accounting.imports.readers.ods_reader import ODSReader
from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.imports.adapters.customer import CustomerAdapter
from cacao_accounting.imports.adapters.vendor import VendorAdapter
from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter
from cacao_accounting.imports.adapters.transaction_documents import (
    DeliveryNoteAdapter,
    PurchaseInvoiceAdapter,
    PurchaseOrderAdapter,
    PurchaseQuotationAdapter,
    PurchaseReceiptAdapter,
    PurchaseRequestAdapter,
    SalesInvoiceAdapter,
    SalesOrderAdapter,
    SalesQuotationAdapter,
    SalesRequestAdapter,
    SupplierQuotationAdapter,
)
from cacao_accounting.imports.utils.validation import is_period_open

IMPORT_SYNC_MAX_ROWS = 100


class ImportService:
    """Servicio principal para gestionar importaciones."""

    READERS = {"csv": CSVReader, "xls": XLSReader, "xlsx": XLSXReader, "ods": ODSReader}

    ADAPTERS: Dict[str, Type] = {
        "journal_entry": JournalEntryAdapter,
        "customer": CustomerAdapter,
        "vendor": VendorAdapter,
        "chart_of_accounts": ChartOfAccountsAdapter,
        "purchase_request": PurchaseRequestAdapter,
        "purchase_quotation": PurchaseQuotationAdapter,
        "supplier_quotation": SupplierQuotationAdapter,
        "purchase_order": PurchaseOrderAdapter,
        "purchase_receipt": PurchaseReceiptAdapter,
        "purchase_invoice": PurchaseInvoiceAdapter,
        "sales_request": SalesRequestAdapter,
        "sales_quotation": SalesQuotationAdapter,
        "sales_order": SalesOrderAdapter,
        "delivery_note": DeliveryNoteAdapter,
        "sales_invoice": SalesInvoiceAdapter,
    }

    FORBIDDEN_COLUMNS = [
        "company_id",
        "empresa",
        "compañía",
        "record_type",
        "tipo_registro",
        "sequence_id",
        "serie",
        "secuencia",
        "accounting_book_id",
        "libro_contable",
    ]

    def _get_reader(self, format: str):
        reader_class = self.READERS.get(format.lower())
        if not reader_class:
            raise ValueError(f"Formato no soportado: {format}")
        return reader_class()

    def _get_adapter(self, record_type: str):
        adapter_class = self.ADAPTERS.get(record_type)
        if not adapter_class:
            raise ValueError(f"Tipo de registro no soportado: {record_type}")
        return adapter_class()

    def _normalize_rows(self, columns: List[str], rows: List[List[Any]]) -> List[Dict[str, Any]]:
        """Convierte filas de lista a diccionarios usando los nombres de columna."""
        return [dict(zip(columns, row)) for row in rows]

    def validate(self, batch_id: str):
        """Valida estructuralmente y por reglas de negocio un lote de importación."""
        batch = database.session.get(ImportBatch, batch_id)
        if not batch:
            return

        batch.import_status = 4
        database.session.commit()

        try:
            if not self._validate_accounting_book_rule(batch):
                return

            reader = self._get_reader(batch.source_format)
            adapter = self._get_adapter(batch.record_type)
            table = reader.read(batch.source_path)
            normalized_rows = self._normalize_rows(table.columns, table.rows)

            ImportBatchError.query.filter_by(batch_id=batch_id).delete()

            structural_errors = self._collect_structural_errors(batch_id, table, adapter)
            if structural_errors:
                self._commit_structural_errors(batch, batch_id, structural_errors)
                return

            docs = self._group_by_reference(table.columns, normalized_rows)
            batch.total_rows = len(normalized_rows)

            business_errors_count = self._collect_business_errors(adapter, batch_id, batch.company_id, docs)
            batch.import_status = 2 if business_errors_count > 0 else 3
            database.session.commit()

        except Exception as e:
            self._handle_validation_error(batch, batch_id, e)

    def _validate_accounting_book_rule(self, batch: ImportBatch) -> bool:
        """Valida regla de libro contable solo para journal_entry."""
        if batch.record_type != "journal_entry" and batch.accounting_book_id:
            database.session.add(
                ImportBatchError(
                    batch_id=batch.id,
                    field_name="accounting_book_id",
                    error_type="BUSINESS_RULE",
                    message="El libro contable solo se permite para comprobantes contables.",
                )
            )
            batch.import_status = 7
            database.session.commit()
            return False
        return True

    def _collect_structural_errors(
        self, batch_id: str, table: Any, adapter: Any
    ) -> List[ImportBatchError]:
        """Recolecta errores estructurales de columnas."""
        errors = []
        for col in table.columns:
            if col.lower() in self.FORBIDDEN_COLUMNS:
                errors.append(
                    ImportBatchError(
                        batch_id=batch_id,
                        field_name=col,
                        error_type="PROHIBITED_COLUMN",
                        message=f"Columna prohibida detectada: {col}",
                    )
                )

        for req_col in adapter.required_columns:
            if req_col not in table.columns:
                errors.append(
                    ImportBatchError(
                        batch_id=batch_id,
                        field_name=req_col,
                        error_type="MISSING_COLUMN",
                        message=f"Columna requerida faltante: {req_col}",
                    )
                )
        return errors

    def _commit_structural_errors(self, batch: ImportBatch, batch_id: str, errors: List[ImportBatchError]) -> None:
        """Persiste errores estructurales y marca batch como fallido."""
        for err in errors:
            database.session.add(err)
        batch.import_status = 7
        database.session.commit()

    def _collect_business_errors(
        self, adapter: Any, batch_id: str, company_id: str, docs: Dict[str, List]
    ) -> int:
        """Recolecta errores de negocio de filas y documentos."""
        errors_count = 0
        for ref, rows in docs.items():
            for i, row in enumerate(rows):
                for err_msg in adapter.validate_row(row):
                    errors_count += 1
                    database.session.add(
                        ImportBatchError(
                            batch_id=batch_id,
                            row_number=i + 1,
                            document_ref=ref,
                            error_type="ROW_VALIDATION",
                            message=err_msg,
                        )
                    )

            for err_msg in adapter.validate_document(rows, {"company_id": company_id}):
                errors_count += 1
                database.session.add(
                    ImportBatchError(batch_id=batch_id, document_ref=ref, error_type="BUSINESS_RULE", message=err_msg)
                )
        return errors_count

    def _handle_validation_error(self, batch: ImportBatch, batch_id: str, e: Exception) -> None:
        """Maneja errores inesperados durante validación."""
        database.session.add(ImportBatchError(batch_id=batch_id, error_type="SYSTEM_ERROR", message=str(e)))
        batch.import_status = 7
        database.session.commit()

    def preview(self, batch_id: str) -> Dict[str, Any]:
        """Obtiene información para la vista previa del lote."""
        batch = database.session.get(ImportBatch, batch_id)
        if not batch:
            return {}

        reader = self._get_reader(batch.source_format)
        table = reader.read(batch.source_path)
        normalized_rows = self._normalize_rows(table.columns, table.rows)
        docs = self._group_by_reference(table.columns, normalized_rows)

        errors = ImportBatchError.query.filter_by(batch_id=batch_id).all()

        sample_rows_list = table.rows[:10]

        return {
            "batch": batch,
            "columns": table.columns,
            "sample_rows": sample_rows_list,
            "total_documents": len(docs),
            "errors": errors,
        }

    def execute(self, batch_id: str):
        """Ejecuta la importación del lote de forma síncrona o asíncrona."""
        batch = database.session.query(ImportBatch).with_for_update().get(batch_id)
        if not batch:
            return

        if batch.import_status != 3:
            return

        reader = self._get_reader(batch.source_format)
        table = reader.read(batch.source_path)

        batch.import_status = 4
        database.session.commit()

        if len(table.rows) > IMPORT_SYNC_MAX_ROWS:
            thread = threading.Thread(
                target=self._execute_task,
                args=(current_app._get_current_object(), batch_id),
                daemon=True,
            )
            thread.start()
        else:
            self._execute_task(current_app._get_current_object(), batch_id)

    def cancel(self, batch_id: str):
        """Solicita la cancelación de un lote de importación."""
        batch = database.session.get(ImportBatch, batch_id)
        if batch:
            batch.cancel_requested = True
            database.session.commit()

    def _process_document(
        self,
        adapter: Any,
        ref: str,
        rows: list,
        context: dict,
        batch: Any,
        batch_id: str,
    ) -> tuple[int, int]:
        """Procesa un documento individual dentro de la importación."""
        doc_obj = adapter.build_document(rows, context)
        self._validate_document_period(doc_obj, batch)
        adapter.persist_document(doc_obj)
        database.session.commit()
        return 1, 0

    def _validate_document_period(self, doc_obj: Any, batch: Any) -> None:
        """Valida que el periodo contable esté abierto para el documento."""
        doc_date = self._extract_document_date(doc_obj)
        if not doc_date:
            return
        if not is_period_open(batch.company_id, doc_date):
            raise ValueError(f"El periodo contable para la fecha {doc_date} está cerrado.")

    def _extract_document_date(self, doc_obj: Any) -> Any:
        """Extrae la fecha de publicación del documento."""
        if isinstance(doc_obj, dict):
            return doc_obj.get("posting_date")
        if hasattr(doc_obj, "posting_date"):
            return doc_obj.posting_date
        return None

    def _parse_document_date(self, doc_date: Any) -> Any:
        """Convierte fecha en string ISO a objeto date."""
        if isinstance(doc_date, str):
            try:
                return datetime.strptime(doc_date, "%Y-%m-%d").date()
            except ValueError:
                return None
        return doc_date

    def _execute_task(self, app, batch_id: str):
        """Tarea de fondo para procesar la importación."""
        with app.app_context():
            batch = database.session.get(ImportBatch, batch_id)
            if not batch:
                return

            batch.import_status = 4
            batch.started_at = datetime.now()
            database.session.commit()

            try:
                reader = self._get_reader(batch.source_format)
                adapter = self._get_adapter(batch.record_type)
                table = reader.read(batch.source_path)
                normalized_rows = self._normalize_rows(table.columns, table.rows)
                docs = self._group_by_reference(table.columns, normalized_rows)

                context = {
                    "company_id": batch.company_id,
                    "sequence_id": batch.sequence_id,
                    "accounting_book_id": batch.accounting_book_id,
                    "record_type": batch.record_type,
                    "created_by": batch.created_by,
                }

                success_count, error_count = self._process_all_documents(
                    batch, batch_id, adapter, docs, context
                )
                self._finalize_execution(batch, batch_id, success_count, error_count)

            except Exception as e:
                self._handle_execution_error(batch, batch_id, e)

    def _process_all_documents(
        self, batch: Any, batch_id: str, adapter: Any, docs: Dict[str, List], context: dict
    ) -> tuple[int, int]:
        """Procesa todos los documentos del lote."""
        success_count = 0
        error_count = 0

        for ref, rows in docs.items():
            if self._check_batch_cancellation(batch, batch_id):
                return success_count, error_count

            try:
                s, e = self._process_document(adapter, ref, rows, context, batch, batch_id)
                success_count += s
                error_count += e
            except Exception as exc:
                error_count = self._handle_document_error(batch_id, batch, ref, exc, error_count)

            self._update_batch_progress(batch, batch_id, success_count, error_count)

        return success_count, error_count

    def _check_batch_cancellation(self, batch: Any, batch_id: str) -> bool:
        """Verifica si el batch fue cancelado."""
        database.session.expire(batch)
        batch = database.session.get(ImportBatch, batch_id)
        if not batch:
            return True
        if batch.cancel_requested:
            batch.import_status = 8
            database.session.commit()
            return True
        return False

    def _handle_document_error(
        self, batch_id: str, batch: Any, ref: str, exc: Exception, error_count: int
    ) -> int:
        """Maneja error en procesamiento de documento individual."""
        database.session.rollback()
        error_count += 1
        err_record = ImportBatchError(
            batch_id=batch_id, document_ref=ref, error_type="IMPORT_ERROR", message=str(exc)
        )
        database.session.add(err_record)
        database.session.commit()
        return error_count

    def _update_batch_progress(self, batch: Any, batch_id: str, success_count: int, error_count: int) -> None:
        """Actualiza el progreso del batch durante ejecución."""
        batch = database.session.get(ImportBatch, batch_id)
        if batch:
            batch.processed_rows = min(success_count + error_count, batch.total_rows or 0)
            database.session.commit()

    def _finalize_execution(self, batch: Any, batch_id: str, success_count: int, error_count: int) -> None:
        """Finaliza la ejecución actualizando estados y contadores."""
        batch = database.session.get(ImportBatch, batch_id)
        if batch:
            batch.success_rows = success_count
            batch.error_rows = error_count
            batch.completed_at = datetime.now()
            batch.import_status = 5 if error_count == 0 else 6
            database.session.commit()

    def _handle_execution_error(self, batch: Any, batch_id: str, e: Exception) -> None:
        """Maneja errores fatales durante la ejecución."""
        batch = database.session.get(ImportBatch, batch_id)
        if batch:
            batch.import_status = 7
            err_record = ImportBatchError(batch_id=batch_id, error_type="FATAL_ERROR", message=str(e))
            database.session.add(err_record)
            database.session.commit()

    def _group_by_reference(self, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Agrupa las filas por la columna document_ref."""
        if "document_ref" not in columns:
            return {f"row_{i}": [row] for i, row in enumerate(rows)}

        docs: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            ref = str(row.get("document_ref") or "no_ref")
            if ref not in docs:
                docs[ref] = []
            docs[ref].append(row)
        return docs
