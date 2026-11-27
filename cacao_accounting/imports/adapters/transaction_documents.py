# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptadores para documentos transaccionales de Compras y Ventas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from cacao_accounting.database import (
    Batch,
    CompanyParty,
    Currency,
    DeliveryNote,
    DeliveryNoteItem,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseRequest,
    PurchaseRequestItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    SerialNumber,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)
from cacao_accounting.document_identifiers import assign_document_identifier
from cacao_accounting.document_flow.context import company_currency, effective_currency
from cacao_accounting.document_flow.service import create_document_relation, pending_qty, qty_in_base_uom
from cacao_accounting.imports.adapters.base import (
    BaseImportAdapter,
    COMMON_DOCUMENT_HEADER_FIELDS,
    normalize_header_decimal,
    normalize_header_text,
)
from cacao_accounting.imports.utils.validation import (
    is_period_open,
    item_import_uom,
    validate_import_item,
    validate_import_uom,
    validate_import_warehouse,
)
from cacao_accounting.imports.utils.dates import parse_import_date


from cacao_accounting.i18n import _


@dataclass(frozen=True)
class TransactionImportConfig:
    """Configuración declarativa para importar un documento transaccional."""

    entity_type: str
    header_model: type[Any]
    item_model: type[Any]
    parent_field: str
    party_type: str | None = None
    party_field: str | None = None
    party_name_field: str | None = None
    source_field: str | None = None
    source_column: str | None = None
    receipt_fields: tuple[str, ...] = ()
    invoice_fields: tuple[str, ...] = ()
    include_batch_serial: bool = False


class TransactionDocumentAdapter(BaseImportAdapter):
    """Adaptador genérico para documentos por encabezado y líneas."""

    columns = [
        "document_ref",
        "fecha",
        "moneda",
        "tipo_cambio",
        "tercero",
        "documento_origen",
        "linea_origen_id",
        "producto",
        "descripcion",
        "uom",
        "cantidad",
        "precio_unitario",
        "bodega",
        "lote",
        "numero_serie",
        "notas",
    ]
    required_columns = ["document_ref", "fecha", "producto", "cantidad", "precio_unitario"]

    SOURCE_LINE_SPECS: dict[str, tuple[tuple[str, type[Any], str], ...]] = {
        "supplier_quotation": (("purchase_quotation", PurchaseQuotationItem, "purchase_quotation_id"),),
        "purchase_receipt": (("purchase_order", PurchaseOrderItem, "purchase_order_id"),),
        "purchase_invoice": (("purchase_order", PurchaseOrderItem, "purchase_order_id"),),
        "sales_quotation": (("sales_request", SalesRequestItem, "sales_request_id"),),
        "sales_order": (("sales_quotation", SalesQuotationItem, "sales_quotation_id"),),
        "delivery_note": (("sales_order", SalesOrderItem, "sales_order_id"),),
        "sales_invoice": (("sales_order", SalesOrderItem, "sales_order_id"),),
        "purchase_order": (
            ("purchase_request", PurchaseRequestItem, "purchase_request_id"),
            ("purchase_quotation", PurchaseQuotationItem, "purchase_quotation_id"),
            ("supplier_quotation", SupplierQuotationItem, "supplier_quotation_id"),
        ),
    }

    def __init__(self, config: TransactionImportConfig) -> None:
        """Inicializa el adaptador con la configuración del documento."""
        self.config = config

    def validate_row(self, row_data: dict[str, Any]) -> list[str]:
        """Valida fila individual incluyendo montos numéricos."""
        errors = super().validate_row(row_data)
        for field in ("cantidad", "precio_unitario"):
            try:
                amount = self._finite_decimal(row_data.get(field), field)
            except ValueError:
                errors.append(_("Valor numérico inválido en columna '%(field)s'.") % {"field": field})
                continue
            if field == "cantidad" and amount <= 0:
                errors.append(_("La cantidad debe ser mayor que cero."))
            if field == "precio_unitario" and amount < 0:
                errors.append(_("El precio unitario no puede ser negativo."))
        return errors

    @staticmethod
    def _finite_decimal(value: Any, field: str) -> Decimal:
        """Convierte un valor Decimal y rechaza entradas inválidas o no finitas."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return Decimal("0")
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(_("%(field)s debe ser un número decimal válido.") % {"field": field}) from exc
        if not amount.is_finite():
            raise ValueError(_("%(field)s debe ser finito.") % {"field": field})
        return amount

    def _validate_source_document(self, first_row: dict[str, Any], source: Any, company_id: str, errors: list[str]) -> None:
        """Validate the optional upstream document and its party/company scope."""
        if not first_row.get("documento_origen"):
            return
        if source is None:
            errors.append(_("El documento origen no existe o no corresponde al flujo importado."))
        elif source.docstatus != 1:
            errors.append(_("El documento origen debe estar aprobado."))
        elif source.company != company_id:
            errors.append(_("El documento origen debe pertenecer a la compañía de la importación."))
        elif getattr(source, "supplier_id", None) and getattr(source, "supplier_id") != first_row.get("tercero"):
            errors.append(_("El tercero del documento origen no coincide con la fila importada."))
        elif getattr(source, "customer_id", None) and getattr(source, "customer_id") != first_row.get("tercero"):
            errors.append(_("El tercero del documento origen no coincide con la fila importada."))

    @staticmethod
    def _source_model(source_type: str, source_id: str) -> Any | None:
        """Load a source document for an explicitly recognized flow type."""
        source_models = {
            "purchase_request": PurchaseRequest,
            "purchase_quotation": PurchaseQuotation,
            "supplier_quotation": SupplierQuotation,
            "purchase_order": PurchaseOrder,
            "sales_request": SalesRequest,
            "sales_quotation": SalesQuotation,
            "sales_order": SalesOrder,
        }
        model = source_models.get(source_type)
        return database.session.get(model, source_id) if model else None

    def _source_matches(self, source_id: Any, source_line_id: Any) -> list[tuple[str, Any, Any]]:
        """Resolve a source document and line only when the pair is unique."""
        if not source_id or not source_line_id:
            return []
        matches = []
        for source_type, item_model, parent_field in self.SOURCE_LINE_SPECS.get(self.config.entity_type, ()):
            source_item = database.session.get(item_model, str(source_line_id))
            if source_item is None or str(getattr(source_item, parent_field, "")) != str(source_id):
                continue
            source = self._source_model(source_type, str(source_id))
            if source is not None:
                matches.append((source_type, source, source_item))
        return matches

    def _source_line_allocation(
        self, row: dict[str, Any], company_id: str
    ) -> tuple[tuple[str, str, str], Decimal] | str | None:
        """Validate one explicit source-line mapping and return its base quantity."""
        source_id = row.get("documento_origen")
        source_line_id = row.get("linea_origen_id")
        if not source_id and not source_line_id:
            return None
        matches = self._source_matches(source_id, source_line_id)
        validation_error = self._source_line_validation_error(row, company_id, (source_id, source_line_id, matches))
        if validation_error:
            return validation_error
        try:
            qty = self._finite_decimal(row.get("cantidad"), "cantidad")
            base_qty = qty_in_base_uom(row.get("producto"), qty, row.get("uom"))
        except ValueError as exc:
            return str(exc)
        source_type = matches[0][0]
        return ((source_type, str(source_id), str(source_line_id)), base_qty)

    def _source_line_validation_error(
        self,
        row: dict[str, Any],
        company_id: str,
        source_reference: tuple[Any, Any, list[tuple[str, Any, Any]]],
    ) -> str | None:
        """Return the first integrity error for a source document and line pair."""
        source_id, source_line_id, matches = source_reference
        if not source_id or not source_line_id:
            return _("Cada fila con origen requiere documento_origen y linea_origen_id.")
        if len(matches) != 1:
            return _("La línea origen no existe, no pertenece al documento indicado o es ambigua.")
        _source_type, source, source_item = matches[0]
        if source.docstatus != 1 or source.company != company_id:
            return _("El documento origen debe estar aprobado y pertenecer a la compañía importada.")
        source_party = getattr(source, "supplier_id", None) or getattr(source, "customer_id", None)
        if source_party and source_party != row.get("tercero"):
            return _("El tercero del documento origen no coincide con la fila importada.")
        if getattr(source_item, "item_code", None) != row.get("producto"):
            return _("La línea destino usa un artículo distinto al de la línea origen.")
        return None

    def _validate_source_quantities(self, accumulated: dict[tuple[str, str, str], Decimal], errors: list[str]) -> None:
        """Check aggregate imported quantities against each source line's balance."""
        for (source_type, source_id, source_line_id), imported_qty in accumulated.items():
            try:
                available_qty = pending_qty(
                    source_type, source_id, source_line_id, self.config.entity_type, exclude_draft_targets=True
                )
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))
                continue
            if imported_qty > available_qty:
                errors.append(_("La cantidad importada excede el pendiente de la línea origen."))

    def _validate_source_lines(self, rows: list[dict[str, Any]], company_id: str, errors: list[str]) -> None:
        """Require each imported source reference to identify one valid source line."""
        accumulated: dict[tuple[str, str, str], Decimal] = {}
        for row in rows:
            allocation = self._source_line_allocation(row, company_id)
            if isinstance(allocation, str):
                errors.append(allocation)
            elif allocation:
                key, base_qty = allocation
                accumulated[key] = accumulated.get(key, Decimal("0")) + base_qty
        self._validate_source_quantities(accumulated, errors)

    def validate_batch_documents(self, documents: dict[str, list[dict[str, Any]]], context: dict[str, Any]) -> list[str]:
        """Reject combined source-line over-allocation across documents in one file."""
        required_by_source = self._batch_source_quantities(documents, context.get("company_id") or "")
        errors = []
        for (source_type, source_id, source_line_id), required_qty in required_by_source.items():
            try:
                available_qty = pending_qty(
                    source_type, source_id, source_line_id, self.config.entity_type, exclude_draft_targets=True
                )
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))
                continue
            if required_qty > available_qty:
                errors.append(_("La cantidad importada en el archivo excede el pendiente de una línea origen."))
        return errors

    def _batch_source_quantities(
        self, documents: dict[str, list[dict[str, Any]]], company_id: str
    ) -> dict[tuple[str, str, str], Decimal]:
        """Collect the file-wide quantities for valid source-line references."""
        required_by_source: dict[tuple[str, str, str], Decimal] = {}
        for rows in documents.values():
            for row in rows:
                allocation = self._batch_source_line_allocation(row, company_id)
                if allocation:
                    key, base_qty = allocation
                    required_by_source[key] = required_by_source.get(key, Decimal("0")) + base_qty
        return required_by_source

    def _batch_source_line_allocation(
        self, row: dict[str, Any], company_id: str
    ) -> tuple[tuple[str, str, str], Decimal] | None:
        """Return a valid source-line quantity for file-wide allocation checks."""
        source_id = row.get("documento_origen")
        source_line_id = row.get("linea_origen_id")
        if not source_id or not source_line_id:
            return None
        matches = self._source_matches(source_id, source_line_id)
        if len(matches) != 1:
            return None
        source_type, source, source_item = matches[0]
        source_party = getattr(source, "supplier_id", None) or getattr(source, "customer_id", None)
        if source.company != company_id or source.docstatus != 1:
            return None
        if (source_party and source_party != row.get("tercero")) or getattr(source_item, "item_code", None) != row.get(
            "producto"
        ):
            return None
        try:
            qty = self._finite_decimal(row.get("cantidad"), "cantidad")
            base_qty = qty_in_base_uom(row.get("producto"), qty, row.get("uom"))
        except ValueError:
            return None
        return ((source_type, str(source_id), str(source_line_id)), base_qty)

    def _validate_document_row(
        self, row: dict[str, Any], company_id: str, errors: list[str], posting_date: date | None = None
    ) -> None:
        """Validate warehouse, stock-item and batch constraints for one row."""
        item, item_error = validate_import_item(row.get("producto"), self.config.entity_type)
        if item_error:
            errors.append(item_error)
        if item is not None:
            uom_error = validate_import_uom(item_import_uom(item, row.get("uom")))
            if uom_error:
                errors.append(uom_error)
        try:
            qty_in_base_uom(row.get("producto"), self._finite_decimal(row.get("cantidad"), "cantidad"), row.get("uom"))
        except ValueError as exc:
            errors.append(str(exc))
        warehouse_code = row.get("bodega")
        warehouse_error = validate_import_warehouse(warehouse_code, company_id)
        if warehouse_error:
            errors.append(warehouse_error)
        if (
            item is not None
            and item.is_stock_item
            and not warehouse_code
            and self.config.entity_type in {"purchase_receipt", "delivery_note"}
        ):
            errors.append(_("El item de inventario '%(item)s' requiere una bodega.") % {"item": item.code})
        errors.extend(self._validate_row_batch(row.get("producto"), row.get("lote"), posting_date))
        errors.extend(
            self._validate_row_serial(
                row.get("producto"),
                row.get("cantidad"),
                row.get("uom"),
                row.get("numero_serie"),
                row.get("bodega"),
            )
        )

    def _validate_row_serial(
        self, item_code: Any, quantity: Any, uom: Any, serial_no: Any, warehouse: Any = None
    ) -> list[str]:
        """Valida serie, cantidad base, duplicados y estado contextual."""
        if not self.config.include_batch_serial or not item_code:
            return []
        item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
        if item is None or not item.has_serial_no:
            return []
        cleaned = str(serial_no or "").strip()
        if not cleaned:
            return [_("El item de inventario '%(item)s' requiere numero de serie.") % {"item": item.code}]
        try:
            base_quantity = qty_in_base_uom(item.code, quantity, uom)
        except ValueError:
            return []
        if base_quantity != Decimal("1"):
            return [_("Cada linea del item serializado '%(item)s' debe mover exactamente una unidad.") % {"item": item.code}]
        existing = database.session.execute(database.select(SerialNumber).filter_by(serial_no=cleaned)).scalar_one_or_none()
        if existing is not None and existing.item_code != item.code:
            return [_("El numero de serie '%(serial)s' ya esta registrado para otro articulo.") % {"serial": cleaned}]
        return self._validate_existing_serial_state(existing, warehouse)

    def _serial_outgoing(self) -> bool:
        return self.config.entity_type == "delivery_note"

    def _validate_existing_serial_state(self, existing: Any, warehouse: Any) -> list[str]:
        if existing is None:
            return []
        if self._serial_outgoing():
            if existing.serial_status != "available":
                return [_("El serial '%(serial)s' no esta disponible para salida.") % {"serial": existing.serial_no}]
            if warehouse and existing.warehouse and str(existing.warehouse) != str(warehouse):
                return [_("El serial '%(serial)s' no se encuentra en la bodega de salida.") % {"serial": existing.serial_no}]
            return []
        if existing.serial_status == "cancelled":
            return []
        if existing.serial_status == "delivered" and self.config.entity_type in {"purchase_receipt"}:
            return []
        return [
            _("El serial '%(serial)s' ya existe y no puede reingresarse en este tipo de documento.")
            % {"serial": existing.serial_no}
        ]

    def validate_document(self, document_data: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[str]:
        """Valida fecha, período, origen, bodega, tercero y moneda del documento."""
        header_fields = dict(COMMON_DOCUMENT_HEADER_FIELDS)
        header_fields.update(
            {
                "moneda": (("moneda", "transaction_currency"), normalize_header_text),
                "tipo_cambio": (("tipo_cambio", "exchange_rate"), normalize_header_decimal),
                "tercero": (("tercero",), normalize_header_text),
                "documento_origen": (("documento_origen",), normalize_header_text),
                "notas": (("notas",), normalize_header_text),
            }
        )
        errors = self.validate_header_consistency(document_data, header_fields)
        first_row = document_data[0]
        if self.config.party_field and not first_row.get("tercero"):
            errors.append(_("La columna tercero es obligatoria para este tipo de registro."))
        try:
            posting_date = parse_import_date(first_row.get("fecha"))
        except (ValueError, TypeError):
            errors.append(_("La fecha debe ser una fecha válida."))
            return errors
        company_id = (context or {}).get("company_id") or ""
        if not is_period_open(company_id, posting_date):
            errors.append(_("El periodo contable para la fecha %(date)s está cerrado o no existe.") % {"date": posting_date})
        source = self._source_document(first_row.get("documento_origen"))
        self._validate_source_document(first_row, source, company_id, errors)
        self._validate_source_lines(document_data, company_id, errors)
        if self.config.party_field and first_row.get("tercero"):
            if self._eligible_party(first_row.get("tercero"), company_id) is None:
                errors.append(
                    _("El tercero debe existir, estar activo, tener el rol requerido y estar habilitado para la compañía.")
                )
        seen_serials: set[str] = set()
        for row in document_data:
            self._validate_document_row(row, company_id, errors, posting_date)
            self._validate_duplicate_serial(row, seen_serials, errors)
        try:
            self._currency_and_rate(first_row, source, company_id, posting_date)
        except ValueError as exc:
            errors.append(str(exc))
        return errors

    def _validate_duplicate_serial(self, row: dict[str, Any], seen_serials: set[str], errors: list[str]) -> None:
        if not self.config.include_batch_serial:
            return
        serial_no = str(row.get("numero_serie") or "").strip()
        item_code = row.get("producto")
        item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
        if not serial_no or item is None or not item.has_serial_no:
            return
        if serial_no in seen_serials:
            errors.append(
                _("El numero de serie '%(serial)s' esta duplicado en el documento importado.") % {"serial": serial_no}
            )
            return
        seen_serials.add(serial_no)

    def _validate_row_batch(self, item_code: Any, batch_no: Any, posting_date: date | None = None) -> list[str]:
        """Valida que el lote de la fila exista en el maestro y aplique al item."""
        if not self.config.include_batch_serial or not item_code:
            return []
        item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
        if item is None or not item.is_stock_item:
            return []
        cleaned = str(batch_no or "").strip()
        if (item.has_batch or item.has_expiry_date) and not cleaned:
            return [f"El item de inventario '{item.code}' requiere lote."]
        if not cleaned:
            return []
        batch = database.session.execute(
            database.select(Batch).filter_by(item_code=item.code, batch_no=cleaned)
        ).scalar_one_or_none()
        if batch is None:
            return [f"El lote '{cleaned}' del item '{item.code}' no existe en el maestro de lotes."]
        if not batch.is_active:
            return [f"El lote '{cleaned}' del item '{item.code}' está inactivo."]
        if item.has_expiry_date and batch.expiry_date and posting_date and batch.expiry_date <= posting_date:
            return [
                _("El lote '%(batch)s' del item '%(item)s' está vencido para la fecha de contabilización.")
                % {"batch": cleaned, "item": item.code}
            ]
        return []

    def build_document(self, document_data: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        """Construye encabezado e ítems desde las filas del archivo."""
        first_row = document_data[0]
        company_id = str(context.get("company_id") or "")
        if self.config.party_field and self._eligible_party(first_row.get("tercero"), company_id) is None:
            raise ValueError(
                _("El tercero debe existir, estar activo, tener el rol requerido y estar habilitado para la compañía.")
            )
        posting_date = parse_import_date(first_row.get("fecha"))
        source = self._source_document(first_row.get("documento_origen"))
        transaction_currency, base_currency, exchange_rate = self._currency_and_rate(
            first_row, source, company_id, posting_date
        )
        header = self.config.header_model(
            company=company_id,
            posting_date=posting_date,
            document_date=posting_date,
            docstatus=0,
            remarks=first_row.get("notas") or f"Importación masiva: {first_row.get('document_ref')}",
            transaction_currency=transaction_currency,
            base_currency=base_currency,
            exchange_rate=exchange_rate,
        )
        self._apply_party(header, first_row.get("tercero"))
        self._apply_source(header, first_row.get("documento_origen"))

        items, total_qty, total = self._build_document_items(document_data, exchange_rate)
        self._apply_totals(header, total_qty, total, exchange_rate)
        return {
            "header": header,
            "items": items,
            "source_lines": [(row.get("documento_origen"), row.get("linea_origen_id")) for row in document_data],
            "entity_type": self.config.entity_type,
            "naming_series_id": context.get("sequence_id"),
        }

    def _build_document_items(
        self, document_data: list[dict[str, Any]], exchange_rate: Decimal
    ) -> tuple[list[Any], Decimal, Decimal]:
        """Build imported lines and compute their transaction-currency totals."""
        items = []
        total_qty = Decimal("0")
        total = Decimal("0")
        for row in document_data:
            item, item_error = validate_import_item(row.get("producto"), self.config.entity_type)
            if item_error:
                raise ValueError(item_error)
            if item is None:
                raise ValueError(_("El artículo no existe."))
            effective_uom = item_import_uom(item, row.get("uom"))
            uom_error = validate_import_uom(effective_uom)
            if uom_error:
                raise ValueError(uom_error)
            qty = self._finite_decimal(row.get("cantidad"), "cantidad")
            rate = self._finite_decimal(row.get("precio_unitario"), "precio_unitario")
            if rate < 0:
                raise ValueError(_("El precio unitario no puede ser negativo."))
            amount = qty * rate
            item = self.config.item_model(
                item_code=row.get("producto"),
                item_name=row.get("descripcion") or "",
                qty=qty,
                uom=effective_uom,
                qty_in_base_uom=qty_in_base_uom(row.get("producto"), qty, effective_uom),
                rate=rate,
                amount=amount,
                warehouse=row.get("bodega") or None,
            )
            self._apply_optional_item_fields(item, amount * exchange_rate, row, exchange_rate)
            items.append(item)
            total_qty += qty
            total += amount
        return items, total_qty, total

    def persist_document(self, document: Any) -> None:
        """Persist header, assign identifier, and save document lines."""
        header = document["header"]
        database.session.add(header)
        database.session.flush()

        assign_document_identifier(
            document=header,
            entity_type=document["entity_type"],
            posting_date_raw=header.posting_date,
            naming_series_id=document["naming_series_id"],
        )

        for item in document["items"]:
            setattr(item, self.config.parent_field, header.id)
            database.session.add(item)
        database.session.flush()
        for item, (source_id, source_line_id) in zip(document["items"], document.get("source_lines", [])):
            if not source_id and not source_line_id:
                continue
            matches = self._source_matches(source_id, source_line_id)
            if len(matches) != 1:
                raise ValueError(_("La línea origen no existe, no pertenece al documento indicado o es ambigua."))
            source_type = matches[0][0]
            create_document_relation(
                source_type=source_type,
                source_id=str(source_id),
                source_item_id=str(source_line_id),
                target_type=document["entity_type"],
                target_id=header.id,
                target_item_id=item.id,
                qty=item.qty,
                uom=getattr(item, "uom", None),
                rate=getattr(item, "rate", None),
                amount=getattr(item, "amount", None),
            )

    def _apply_party(self, header: Any, party_id: Any) -> None:
        if not self.config.party_field:
            return
        party = self._eligible_party(party_id, str(getattr(header, "company", "")))
        if party is None:
            raise ValueError(
                _("El tercero debe existir, estar activo, tener el rol requerido y estar habilitado para la compañía.")
            )
        setattr(header, self.config.party_field, party_id or None)
        if self.config.party_name_field:
            setattr(header, self.config.party_name_field, party.name if party else None)

    def _eligible_party(self, party_id: Any, company_id: str) -> Party | None:
        """Resolve a party with its configured role and active company membership."""
        if not party_id:
            return None
        query = database.select(Party).filter(Party.id == party_id, Party.is_active.is_(True))
        if self.config.party_type == "customer":
            query = query.filter(Party.is_customer.is_(True))
        elif self.config.party_type == "supplier":
            query = query.filter(Party.is_supplier.is_(True))
        if self.config.party_type:
            if not company_id:
                return None
            query = query.join(CompanyParty, CompanyParty.party_id == Party.id).filter(
                CompanyParty.company == company_id,
                CompanyParty.is_active.is_(True),
            )
        return database.session.execute(query).scalar_one_or_none()

    def _apply_source(self, header: Any, source_id: Any) -> None:
        if self.config.source_field and source_id:
            setattr(header, self.config.source_field, source_id)

    def _source_document(self, source_id: Any) -> Any | None:
        """Resuelve el documento origen permitido por el tipo importado."""
        if not source_id:
            return None
        source_models = {
            "supplier_quotation": PurchaseQuotation,
            "purchase_receipt": PurchaseOrder,
            "purchase_invoice": PurchaseOrder,
            "sales_quotation": SalesRequest,
            "sales_order": SalesQuotation,
            "delivery_note": SalesOrder,
            "sales_invoice": SalesOrder,
        }
        source_model = source_models.get(self.config.entity_type)
        if source_model:
            return database.session.get(source_model, source_id)
        if self.config.entity_type == "purchase_order" and source_id:
            candidates = [
                self._source_model(source_type, str(source_id))
                for source_type, _item_model, _parent_field in self.SOURCE_LINE_SPECS["purchase_order"]
            ]
            matches = [candidate for candidate in candidates if candidate is not None]
            return matches[0] if len(matches) == 1 else None
        return None

    def _currency_and_rate(
        self, first_row: dict[str, Any], source: Any | None, company: str, posting_date: date
    ) -> tuple[str | None, str | None, Decimal]:
        """Resuelve moneda funcional y tasa, rechazando conversiones implicitas 1:1.

        La moneda transaccional debe venir explicita en la primera fila o
        heredarse del documento origen. No se permite inferir desde la
        compania: si falta, se rechaza con ``ValueError``.
        """
        base_currency = company_currency(company)
        if not base_currency:
            raise ValueError(_("La compañía no tiene moneda funcional configurada."))
        row_currency = first_row.get("moneda") or first_row.get("transaction_currency")
        source_currency = effective_currency(source)
        if row_currency:
            transaction_currency = str(row_currency).strip()
        elif source_currency:
            transaction_currency = source_currency
        else:
            raise ValueError(
                _(
                    "El documento importado requiere una moneda transaccional explicita en la primera fila "
                    "o un documento origen con moneda transaccional persistida."
                )
            )
        self._validate_transaction_currency(transaction_currency)
        explicit_rate = first_row.get("tipo_cambio") or first_row.get("exchange_rate")
        explicit_decimal = self._finite_decimal(explicit_rate, "tipo de cambio") if explicit_rate not in (None, "") else None
        if transaction_currency == base_currency:
            return transaction_currency, base_currency, Decimal("1")
        if explicit_decimal is not None:
            rate = explicit_decimal
        elif source is not None and getattr(source, "exchange_rate", None):
            rate = self._finite_decimal(source.exchange_rate, "tipo de cambio")
        else:
            from cacao_accounting.contabilidad.posting import PostingError, _lookup_exchange_rate

            try:
                rate = _lookup_exchange_rate(transaction_currency, base_currency, posting_date)
            except PostingError as exc:
                raise ValueError(
                    _("No existe tipo de cambio para %(transaction_currency)s -> %(base_currency)s en %(posting_date)s.")
                    % {
                        "transaction_currency": transaction_currency,
                        "base_currency": base_currency,
                        "posting_date": posting_date,
                    }
                ) from exc
        if not rate.is_finite():
            raise ValueError(_("Tipo de Cambio debe ser finito."))
        if rate <= 0:
            raise ValueError(_("El tipo de cambio debe ser positivo."))
        return transaction_currency, base_currency, rate

    @staticmethod
    def _validate_transaction_currency(transaction_currency: str) -> None:
        """Rechaza códigos de moneda inexistentes o inactivos antes de importar."""
        currency = database.session.execute(
            database.select(Currency).filter_by(code=transaction_currency)
        ).scalar_one_or_none()
        if currency is None:
            raise ValueError(
                _("La moneda transaccional '%(currency)s' no existe en el catálogo.") % {"currency": transaction_currency}
            )
        if not currency.active:
            raise ValueError(_("La moneda transaccional '%(currency)s' está inactiva.") % {"currency": transaction_currency})

    def _apply_totals(self, header: Any, total_qty: Decimal, total: Decimal, exchange_rate: Decimal = Decimal("1")) -> None:
        if hasattr(header, "total_qty"):
            header.total_qty = total_qty
        for field in ("total", "base_total", "net_total", "grand_total", "base_grand_total"):
            if hasattr(header, field):
                value = total if not field.startswith("base_") else (total * exchange_rate).quantize(Decimal("0.0001"))
                setattr(header, field, value)
        for field in ("outstanding_amount", "base_outstanding_amount"):
            if hasattr(header, field):
                value = total if field == "outstanding_amount" else (total * exchange_rate).quantize(Decimal("0.0001"))
                setattr(header, field, value)

    def _apply_optional_item_fields(
        self, item: Any, amount: Decimal, row: dict[str, Any], exchange_rate: Decimal = Decimal("1")
    ) -> None:
        self._apply_item_amount_fields(item, amount)
        self._apply_item_rate_fields(item, exchange_rate)
        self._apply_item_zero_fields(item, self.config.receipt_fields)
        self._apply_item_zero_fields(item, self.config.invoice_fields)
        self._apply_item_batch_serial_fields(item, row)

    def _apply_item_amount_fields(self, item: Any, amount: Decimal) -> None:
        if hasattr(item, "base_amount"):
            item.base_amount = amount

    def _apply_item_rate_fields(self, item: Any, exchange_rate: Decimal = Decimal("1")) -> None:
        for field in ("base_rate", "valuation_rate"):
            if hasattr(item, field):
                setattr(item, field, (item.rate * exchange_rate).quantize(Decimal("0.0001")))

    def _apply_item_zero_fields(self, item: Any, fields: tuple[str, ...]) -> None:
        for field in fields:
            if hasattr(item, field):
                setattr(item, field, Decimal("0"))

    def _apply_item_batch_serial_fields(self, item: Any, row: dict[str, Any]) -> None:
        if not self.config.include_batch_serial:
            return
        if hasattr(item, "batch_id"):
            item.batch_id = self._resolve_batch_id(item.item_code, row.get("lote"))
        if hasattr(item, "serial_no"):
            item.serial_no = row.get("numero_serie") or None

    def _resolve_batch_id(self, item_code: Any, batch_no: Any) -> str | None:
        """Resuelve el numero de lote del archivo al registro del maestro.

        La columna ``lote`` contiene el numero legible del lote, no su
        identificador interno: se resuelve contra el maestro por item y numero
        de lote y se rechaza la fila cuando el lote no existe, en lugar de
        persistir un texto que el posting nunca podria validar.
        """
        if batch_no is None:
            return None
        cleaned = str(batch_no).strip()
        if not cleaned:
            return None
        batch = database.session.execute(
            database.select(Batch).filter_by(item_code=item_code, batch_no=cleaned)
        ).scalar_one_or_none()
        if batch is None:
            raise ValueError(
                _("El lote '%(batch)s' del item '%(item)s' no existe en el maestro de lotes.")
                % {"batch": cleaned, "item": item_code}
            )
        if not batch.is_active:
            raise ValueError(
                _("El lote '%(batch)s' del item '%(item)s' está inactivo.") % {"batch": cleaned, "item": item_code}
            )
        return batch.id


class PurchaseRequestAdapter(TransactionDocumentAdapter):
    """Adaptador para Solicitudes de Compra."""

    def __init__(self) -> None:
        """Configura importación de solicitudes de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_request",
                header_model=PurchaseRequest,
                item_model=PurchaseRequestItem,
                parent_field="purchase_request_id",
            )
        )


class PurchaseQuotationAdapter(TransactionDocumentAdapter):
    """Adaptador para Solicitudes de Cotización."""

    def __init__(self) -> None:
        """Configura importación de solicitudes de cotización."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_quotation",
                header_model=PurchaseQuotation,
                item_model=PurchaseQuotationItem,
                parent_field="purchase_quotation_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
            )
        )


class SupplierQuotationAdapter(TransactionDocumentAdapter):
    """Adaptador para Cotizaciones de Proveedor."""

    def __init__(self) -> None:
        """Configura importación de cotizaciones de proveedor."""
        super().__init__(
            TransactionImportConfig(
                entity_type="supplier_quotation",
                header_model=SupplierQuotation,
                item_model=SupplierQuotationItem,
                parent_field="supplier_quotation_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                source_field="purchase_quotation_id",
            )
        )


class PurchaseOrderAdapter(TransactionDocumentAdapter):
    """Adaptador para Órdenes de Compra."""

    def __init__(self) -> None:
        """Configura importación de órdenes de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_order",
                header_model=PurchaseOrder,
                item_model=PurchaseOrderItem,
                parent_field="purchase_order_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                receipt_fields=("received_qty",),
                invoice_fields=("billed_qty",),
            )
        )


class PurchaseReceiptAdapter(TransactionDocumentAdapter):
    """Adaptador para Recepciones de Compra."""

    def __init__(self) -> None:
        """Configura importación de recepciones de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_receipt",
                header_model=PurchaseReceipt,
                item_model=PurchaseReceiptItem,
                parent_field="purchase_receipt_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                source_field="purchase_order_id",
                include_batch_serial=True,
            )
        )


class PurchaseInvoiceAdapter(TransactionDocumentAdapter):
    """Adaptador para Facturas de Compra."""

    def __init__(self) -> None:
        """Configura importación de facturas de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_invoice",
                header_model=PurchaseInvoice,
                item_model=PurchaseInvoiceItem,
                parent_field="purchase_invoice_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                source_field="purchase_order_id",
            )
        )


class SalesRequestAdapter(TransactionDocumentAdapter):
    """Adaptador para Pedidos de Venta."""

    def __init__(self) -> None:
        """Configura importación de pedidos de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_request",
                header_model=SalesRequest,
                item_model=SalesRequestItem,
                parent_field="sales_request_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
            )
        )


class SalesQuotationAdapter(TransactionDocumentAdapter):
    """Adaptador para Cotizaciones de Venta."""

    def __init__(self) -> None:
        """Configura importación de cotizaciones de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_quotation",
                header_model=SalesQuotation,
                item_model=SalesQuotationItem,
                parent_field="sales_quotation_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_request_id",
            )
        )


class SalesOrderAdapter(TransactionDocumentAdapter):
    """Adaptador para Órdenes de Venta."""

    def __init__(self) -> None:
        """Configura importación de órdenes de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_order",
                header_model=SalesOrder,
                item_model=SalesOrderItem,
                parent_field="sales_order_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_quotation_id",
                receipt_fields=("delivered_qty",),
                invoice_fields=("billed_qty",),
            )
        )


class DeliveryNoteAdapter(TransactionDocumentAdapter):
    """Adaptador para Notas de Entrega."""

    def __init__(self) -> None:
        """Configura importación de notas de entrega."""
        super().__init__(
            TransactionImportConfig(
                entity_type="delivery_note",
                header_model=DeliveryNote,
                item_model=DeliveryNoteItem,
                parent_field="delivery_note_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_order_id",
                include_batch_serial=True,
            )
        )


class SalesInvoiceAdapter(TransactionDocumentAdapter):
    """Adaptador para Facturas de Venta."""

    def __init__(self) -> None:
        """Configura importación de facturas de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_invoice",
                header_model=SalesInvoice,
                item_model=SalesInvoiceItem,
                parent_field="sales_invoice_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_order_id",
                include_batch_serial=True,
            )
        )
