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

        batch.import_status = 4  # Procesando validación
        database.session.commit()

        try:
            if batch.record_type != "journal_entry" and batch.accounting_book_id:
                database.session.add(
                    ImportBatchError(
                        batch_id=batch_id,
                        field_name="accounting_book_id",
                        error_type="BUSINESS_RULE",
                        message="El libro contable solo se permite para comprobantes contables.",
                    )
                )
                batch.import_status = 7
                database.session.commit()
                return

            reader = self._get_reader(batch.source_format)
            adapter = self._get_adapter(batch.record_type)
            table = reader.read(batch.source_path)
            normalized_rows = self._normalize_rows(table.columns, table.rows)

            # Limpiar errores previos
            ImportBatchError.query.filter_by(batch_id=batch_id).delete()

            # Validación estructural
            errors = []
            # Validar columnas prohibidas
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

            # Validar columnas requeridas
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

            if errors:
                for err in errors:
                    database.session.add(err)
                batch.import_status = 7  # Fallido (validación estructural)
                database.session.commit()
                return

            # Agrupar por document_ref
            docs = self._group_by_reference(table.columns, normalized_rows)
            batch.total_rows = len(normalized_rows)

            # Validación de filas y negocio (pre-importación)
            business_errors_count = 0
            for ref, rows in docs.items():
                # Validación de filas
                for i, row in enumerate(rows):
                    row_errors = adapter.validate_row(row)
                    for err_msg in row_errors:
                        business_errors_count += 1
                        database.session.add(
                            ImportBatchError(
                                batch_id=batch_id,
                                row_number=i + 1,
                                document_ref=ref,
                                error_type="ROW_VALIDATION",
                                message=err_msg,
                            )
                        )

                # Validación de documento (negocio)
                doc_errors = adapter.validate_document(rows, {"company_id": batch.company_id})
                for err_msg in doc_errors:
                    business_errors_count += 1
                    database.session.add(
                        ImportBatchError(batch_id=batch_id, document_ref=ref, error_type="BUSINESS_RULE", message=err_msg)
                    )

            if business_errors_count > 0:
                batch.import_status = 2  # Validado (con errores de negocio)
            else:
                batch.import_status = 3  # Listo para ejecutar

            database.session.commit()

        except Exception as e:
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

        # Para la vista previa en HTML necesitamos los valores como lista
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

        # Solo permitir ejecutar lotes en estado 'Listo' (3)
        # El estado 'Validado con errores' (2) debe corregirse y re-validarse
        if batch.import_status != 3:
            return

        reader = self._get_reader(batch.source_format)
        table = reader.read(batch.source_path)

        # Cambiar a estado procesando inmediatamente para evitar doble ejecución
        batch.import_status = 4  # Procesando
        database.session.commit()

        if len(table.rows) > IMPORT_SYNC_MAX_ROWS:
            # Async
            thread = threading.Thread(
                target=self._execute_task,
                args=(current_app._get_current_object(), batch_id),  # type: ignore[attr-defined]
                daemon=True,
            )
            thread.start()
        else:
            # Sync
            self._execute_task(current_app._get_current_object(), batch_id)  # type: ignore[attr-defined]

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

        doc_date = None
        if isinstance(doc_obj, dict):
            doc_date = doc_obj.get("posting_date")
        elif hasattr(doc_obj, "posting_date"):
            doc_date = doc_obj.posting_date

        if doc_date:
            if isinstance(doc_date, str):
                try:
                    doc_date = datetime.strptime(doc_date, "%Y-%m-%d").date()
                except ValueError:
                    doc_date = None
            if doc_date and not is_period_open(batch.company_id, doc_date):
                raise ValueError(f"El periodo contable para la fecha {doc_date} está cerrado.")

        adapter.persist_document(doc_obj)
        database.session.commit()
        return 1, 0

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

                success_count = 0
                error_count = 0

                for ref, rows in docs.items():
                    database.session.expire(batch)
                    batch = database.session.get(ImportBatch, batch_id)
                    if not batch:
                        return
                    if batch.cancel_requested:
                        batch.import_status = 8
                        database.session.commit()
                        return

                    try:
                        s, e = self._process_document(adapter, ref, rows, context, batch, batch_id)
                        success_count += s
                        error_count += e
                    except Exception as exc:
                        database.session.rollback()
                        error_count += 1
                        err_record = ImportBatchError(
                            batch_id=batch_id, document_ref=ref, error_type="IMPORT_ERROR", message=str(exc)
                        )
                        database.session.add(err_record)
                        database.session.commit()

                    batch = database.session.get(ImportBatch, batch_id)
                    if batch:
                        batch.processed_rows = min(success_count + error_count, batch.total_rows or 0)
                        database.session.commit()

                batch = database.session.get(ImportBatch, batch_id)
                if batch:
                    batch.success_rows = success_count
                    batch.error_rows = error_count
                    batch.completed_at = datetime.now()
                    batch.import_status = 5 if error_count == 0 else 6
                    database.session.commit()

            except Exception as e:
                batch = database.session.get(ImportBatch, batch_id)
                if batch:
                    batch.import_status = 7
                    err_record = ImportBatchError(batch_id=batch_id, error_type="FATAL_ERROR", message=str(e))
                    database.session.add(err_record)
                    database.session.commit()

    def _group_by_reference(self, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Agrupa las filas por la columna document_ref."""
        if "document_ref" not in columns:
            # Si no hay document_ref, cada fila es un documento
            return {f"row_{i}": [row] for i, row in enumerate(rows)}

        docs: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            ref = str(row.get("document_ref") or "no_ref")
            if ref not in docs:
                docs[ref] = []
            docs[ref].append(row)
        return docs
