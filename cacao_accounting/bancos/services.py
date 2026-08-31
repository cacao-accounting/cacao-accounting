"""Modulo de Caja y Bancos."""

from datetime import date, timedelta

from decimal import Decimal

import json

from typing import Any, TypedDict, cast

from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, redirect, request, url_for


from flask_login import current_user

from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    find_bank_reconciliation_candidates,
)

from cacao_accounting.bancos.statement_service import (
    BankStatementError,
    create_bank_difference_journal,
)

from cacao_accounting.database import (
    BankAccount,
    Accounts,
    BankAccountNumberingConfig,
    BankTransaction,
    DocumentRelation,
    Entity,
    ExternalCounter,
    GLEntry,
    NamingSeries,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    PurchaseOrder,
    Reconciliation,
    ReconciliationItem,
    SalesOrder,
    SalesInvoice,
    SeriesExternalCounterMap,
    database,
)

from cacao_accounting.auth.permisos import Permisos

from cacao_accounting.database.helpers import get_active_naming_series

from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

from cacao_accounting.contabilidad.posting_service import _lookup_exchange_rate

from cacao_accounting.document_flow import create_document_relation, revert_relations_for_target


from cacao_accounting.document_flow.registry import normalize_doctype


from cacao_accounting.document_flow.service import compute_outstanding_amount, refresh_outstanding_amount_cache

from cacao_accounting.document_flow.status import _

from cacao_accounting.document_identifiers import (
    IdentifierConfigurationError,
    PAYMENT_TYPE_TO_ENTITY_TYPE,
    assign_document_identifier,
)

from cacao_accounting.decorators import exige_acceso_compania

from cacao_accounting.fiscal_persistence_service import load_document_fiscal_lines, persist_document_fiscal_snapshot

from cacao_accounting.list_filters import apply_list_filters, apply_period_filter, attach_period_picker, require_period_company

from cacao_accounting.ledger_queries import primary_ledger_id


from cacao_accounting.audit_trail_service import log_create

bancos = Blueprint("bancos", __name__, template_folder="templates")

BANCOS_TRANSACCION_LISTA_HTML = "bancos/transaccion_lista.html"

BANCOS_BANCO_CUENTA_NUEVO_HTML = "bancos/banco_cuenta_nuevo.html"

BANCOS_PAGO_LISTA_HTML = "bancos/pago_lista.html"

BANCOS_BANCOS_PAGO = "bancos.bancos_pago"

BANCOS_CONCILIACION_ENDPOINT = "bancos.bancos_conciliacion_bancaria"

COMPRAS_FACTURA_COMPRA_ROUTE = "compras.compras_factura_compra"

VENTAS_FACTURA_VENTA_ROUTE = "ventas.ventas_factura_venta"

LABEL_FACTURA_COMPRA = "Factura de Compra"

LABEL_FACTURA_VENTA = "Factura de Venta"

PAYMENT_TYPES = ("pay", "receive", "internal_transfer", "debit_note", "credit_note")


def _safe_bank_reconciliation_candidates(transaction: BankTransaction) -> list[Any]:
    """Obtiene sugerencias sin romper el panel por datos bancarios históricos inválidos."""
    try:
        return find_bank_reconciliation_candidates(transaction.id)
    except BankReconciliationError:
        return []


class PaymentPayload(TypedDict, total=False):
    """Normalized payload for the payment form."""

    payment_type: str | None
    company: str | None
    bank_account_id: str | None
    posting_date: str | None
    paid_amount: object | None
    received_amount: object | None
    party_id: str | None
    party_type: str | None
    naming_series_id: str | None
    external_counter_id: str | None
    external_number: str | None
    target_bank_account_id: str | None
    mode_of_payment: str | None
    cost_center_code: str | None
    unit_code: str | None
    project_code: str | None
    paid_from_account_id: str | None
    paid_to_account_id: str | None
    reference_date: str | None
    party_name: str | None
    reference_no: str | None
    remarks: str | None
    lines: list[dict[str, object]] | None
    advance_mode: bool | None
    tax_lines: object | None
    tax_summary: object | None


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return [("", "")]

    return [("", "")] + [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


def _validate_naming_series_default(
    *,
    company: str | None,
    naming_series_id: str,
    entity_type: str,
    error_prefix: str,
    entity_type_error: str,
) -> str:
    """Valida una serie predeterminada reutilizando el mismo patrón de negocio."""
    series = database.session.get(NamingSeries, naming_series_id)
    if not series or not series.is_active:
        raise IdentifierConfigurationError(f"{error_prefix} seleccionada no existe o está inactiva.")
    if series.entity_type != entity_type:
        raise IdentifierConfigurationError(entity_type_error)
    if series.company not in (None, company):
        raise IdentifierConfigurationError(f"{error_prefix} no pertenece a la compañía indicada.")
    return naming_series_id


def _validate_payment_series_default(
    *,
    company: str | None,
    naming_series_id: str,
) -> str:
    """Valida la serie interna predeterminada para pagos."""
    return _validate_naming_series_default(
        company=company,
        naming_series_id=naming_series_id,
        entity_type="payment_entry",
        error_prefix="La serie interna",
        entity_type_error="La serie interna debe ser para pagos.",
    )


def _validate_checkbook_default(
    *,
    company: str | None,
    external_counter_id: str,
) -> str:
    """Valida la chequera predeterminada para pagos."""
    counter = database.session.get(ExternalCounter, external_counter_id)
    if not counter or not counter.is_active:
        raise IdentifierConfigurationError("La chequera seleccionada no existe o está inactiva.")
    if counter.counter_type != "checkbook":
        raise IdentifierConfigurationError("El contador externo seleccionado debe ser una chequera.")
    if counter.company != company:
        raise IdentifierConfigurationError("La chequera no pertenece a la compañía indicada.")
    return external_counter_id


def _validate_bank_account_numbering_defaults(
    *,
    company: str | None,
    naming_series_id: str | None,
    external_counter_id: str | None,
) -> tuple[str | None, str | None]:
    """Valida la serie de pagos y chequera predeterminadas de una cuenta bancaria."""
    if naming_series_id:
        naming_series_id = _validate_payment_series_default(company=company, naming_series_id=naming_series_id)

    if external_counter_id:
        external_counter_id = _validate_checkbook_default(company=company, external_counter_id=external_counter_id)

    return naming_series_id, external_counter_id


def _ensure_bank_account_counter_mapping(bank_account: BankAccount) -> None:
    """Vincula la serie compartida con la chequera usando la cuenta como contexto."""
    if not bank_account.default_naming_series_id or not bank_account.default_external_counter_id:
        return

    condition_json = json.dumps({"bank_account_id": bank_account.id}, sort_keys=True)
    existing = database.session.execute(
        database.select(SeriesExternalCounterMap).filter_by(
            naming_series_id=bank_account.default_naming_series_id,
            external_counter_id=bank_account.default_external_counter_id,
            condition_json=condition_json,
        )
    ).scalar_one_or_none()
    if existing:
        return

    database.session.add(
        SeriesExternalCounterMap(
            naming_series_id=bank_account.default_naming_series_id,
            external_counter_id=bank_account.default_external_counter_id,
            priority=0,
            condition_json=condition_json,
        )
    )


def _payment_numbering_defaults(bank_account_id: str | None) -> tuple[str | None, str | None]:
    """Devuelve serie y chequera predeterminadas de la cuenta bancaria."""
    if not bank_account_id:
        return None, None

    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        return None, None

    return bank_account.default_naming_series_id, bank_account.default_external_counter_id


def _lookup_series_name(naming_series_id: str | None) -> str | None:
    """Retorna el nombre de una naming series."""
    if not naming_series_id:
        return None
    series = database.session.get(NamingSeries, naming_series_id)
    return series.name if series else None


def _lookup_counter_name(external_counter_id: str | None) -> str | None:
    """Retorna el nombre de un contador externo."""
    if not external_counter_id:
        return None
    counter = database.session.get(ExternalCounter, external_counter_id)
    return counter.name if counter else None


def _payment_type_to_entity_type(payment_type: str) -> str:
    """Retorna el entity_type de NamingSeries para un tipo de transaccion bancaria."""
    return PAYMENT_TYPE_TO_ENTITY_TYPE.get(payment_type, "payment_entry")


def _get_default_entity_type_for_payment_type() -> dict[str, str]:
    """Retorna el mapeo de payment_type a entity_type."""
    return dict(PAYMENT_TYPE_TO_ENTITY_TYPE)


def _ensure_bank_account_numbering_config(bank_account: BankAccount) -> None:
    """Crea configuraciones predeterminadas de numeracion para cada tipo de transaccion.

    Usa los defaults legacy (default_naming_series_id, default_external_counter_id)
    como valores iniciales para todos los tipos de transaccion.
    """
    for payment_type in PAYMENT_TYPES:
        existing = database.session.execute(
            database.select(BankAccountNumberingConfig).filter_by(
                bank_account_id=bank_account.id,
                payment_type=payment_type,
            )
        ).scalar_one_or_none()
        if existing:
            continue
        naming_series_id = bank_account.default_naming_series_id
        if naming_series_id:
            series = database.session.get(NamingSeries, naming_series_id)
            if series and series.entity_type == "payment_entry":
                naming_series_id = None
        use_external = payment_type in ("pay", "receive")
        config = BankAccountNumberingConfig(
            bank_account_id=bank_account.id,
            payment_type=payment_type,
            naming_series_id=naming_series_id,
            use_external_counter=use_external,
            external_counter_id=bank_account.default_external_counter_id if use_external else None,
        )
        database.session.add(config)


def _resolve_bank_account_numbering_config(
    bank_account_id: str | None,
    payment_type: str | None,
) -> BankAccountNumberingConfig | None:
    """Resuelve la configuracion de numeracion para una cuenta y tipo de transaccion."""
    if not bank_account_id or not payment_type:
        return None
    return database.session.execute(
        database.select(BankAccountNumberingConfig).filter_by(
            bank_account_id=bank_account_id,
            payment_type=payment_type,
        )
    ).scalar_one_or_none()


def _warn_duplicate_payment(payment):
    """CAS-20: Alerta si existe un pago similar al mismo proveedor/cliente en ±3 días.

    Regla de negocio: solo se emite advertencia (flash warning), no se detiene
    el registro del pago. El usuario decide si confirma o cancela.
    """
    payment_type = str(payment.payment_type or "").lower()
    is_outflow = payment_type in {"pay", "debit_note"}
    amount_column = PaymentEntry.paid_amount if is_outflow else PaymentEntry.received_amount
    amount = payment.paid_amount if is_outflow else payment.received_amount
    if not amount or amount <= 0:
        return
    window_start = (payment.posting_date or date.today()) - timedelta(days=3)
    window_end = (payment.posting_date or date.today()) + timedelta(days=3)
    matches = (
        database.session.execute(
            database.select(PaymentEntry).filter(
                PaymentEntry.id != payment.id,
                PaymentEntry.company == payment.company,
                PaymentEntry.party_id == payment.party_id,
                PaymentEntry.docstatus == 1,
                PaymentEntry.posting_date >= window_start,
                PaymentEntry.posting_date <= window_end,
                PaymentEntry.payment_type.in_({"pay", "debit_note"} if is_outflow else {"receive", "credit_note"}),
                amount_column == amount,
                PaymentEntry.currency == payment.currency,
            )
        )
        .scalars()
        .all()
    )
    if matches:
        flash(
            "Ya existe un pago similar ({0}) al mismo proveedor/cliente en las ultimas dias. "
            "Verifique que no sea un pago duplicado.".format(matches[0].document_no or matches[0].id),
            "warning",
        )


def _cash_authorized_companies() -> list[str]:
    """Return companies the current user may consult in cash management."""
    module_id = obtener_id_modulo_por_nombre("cash")
    permissions = Permisos(modulo=module_id, usuario=current_user.id)
    return list(permissions.obtener_companias_autorizadas()) if permissions.consultar else []


def _apply_cash_company_scope(base_query: Any, model: Any) -> Any:
    """Apply explicit or authorized company scope to a cash list query."""
    if hasattr(model, "company"):
        company = request.args.get("company")
        if company:
            exige_acceso_compania("cash", company, "consultar")
            return base_query.filter(model.company == company)
        if getattr(current_user, "classification", None) == "admin":
            return base_query
        companies = _cash_authorized_companies()
        if not companies:
            return base_query.where(database.false())
        return base_query.where(model.company.in_(companies))
    return base_query


def _cash_period_company() -> str | None:
    """Resolve the sole authorized company used by cash period filters."""
    period_company: str | None = request.args.get("company")
    if period_company or getattr(current_user, "classification", None) == "admin":
        return period_company
    companies = _cash_authorized_companies()
    return companies[0] if len(companies) == 1 else period_company


def _apply_cash_period_scope(base_query: Any, model: Any) -> Any:
    """Apply accounting period filters when the cash model supports posting dates."""
    if not hasattr(model, "posting_date"):
        return base_query
    period_from = request.args.get("accounting_period_from") or request.args.get("period_from")
    period_to = request.args.get("accounting_period_to") or request.args.get("period_to")
    period_company = _cash_period_company()
    if not (period_from or period_to or period_company):
        return base_query
    return apply_period_filter(
        base_query,
        model,
        require_period_company(("cash",), current_user=current_user, default_company=period_company),
        period_from,
        period_to,
        default_when_missing=True,
    )


def _paginate_list(model, search_fields, query=None, *, include_status: bool = True):
    """Pagina un listado aplicando los filtros GET comunes."""
    base_query = query if query is not None else database.select(model)
    base_query = _apply_cash_company_scope(base_query, model)
    base_query = _apply_cash_period_scope(base_query, model)
    filtered_query = apply_list_filters(base_query, model, search_fields, include_status=include_status)
    paginated = database.paginate(
        filtered_query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    attach_period_picker(paginated, model, "cash", current_user=current_user)
    return paginated


def _bank_account_for_note(bank_account_id: str, company: str | None, amount: Decimal) -> BankAccount:
    """Obtiene la cuenta bancaria de una nota y valida su pertenencia."""
    if amount <= 0:
        abort(409)

    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        abort(400)
    if company and bank_account.company != company:
        abort(409)
    return bank_account


def _bank_reconciliation_allocated_amount(transaction: BankTransaction) -> Decimal | None:
    """Get the amount allocated for a bank reconciliation match."""
    if transaction.deposit is not None and transaction.deposit > 0:
        return transaction.deposit
    return transaction.withdrawal


def _signed_bank_difference(transaction: BankTransaction, difference_amount: Decimal) -> Decimal:
    """Return the adjustment sign required by the bank transaction direction."""
    if transaction.deposit is not None and transaction.deposit > 0:
        return -abs(difference_amount)
    return abs(difference_amount)


def _submit_bank_difference_journal(
    reconciliation_id: str, transaction: BankTransaction, amount: Decimal, user_id: str
) -> Any:
    """Create and submit a bank difference journal without committing it."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, submit_journal

    try:
        journal = create_bank_difference_journal(
            reconciliation_id,
            amount,
            transaction_id=transaction.id,
            user_id=user_id,
        )
        submit_journal(journal.id, commit=False, user_id=user_id)
    except (BankStatementError, JournalValidationError) as exc:
        raise BankReconciliationError(str(exc)) from exc
    return journal


def _bank_difference_gl_entry(transaction: BankTransaction, journal: Any) -> tuple[BankAccount, GLEntry]:
    """Resolve the bank account and posted GL line used by the adjustment."""
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    if not bank_account or not bank_account.gl_account_id:
        raise BankReconciliationError("La transaccion no tiene cuenta bancaria GL para registrar el ajuste.")
    ledger_id = primary_ledger_id(str(bank_account.company))
    bank_entry = database.session.execute(
        database.select(GLEntry)
        .filter_by(
            company=bank_account.company,
            voucher_type="journal_entry",
            voucher_id=journal.id,
            account_id=bank_account.gl_account_id,
            ledger_id=ledger_id,
            is_cancelled=False,
            is_reversal=False,
        )
        .limit(1)
    ).scalar_one_or_none()
    if bank_entry is None:
        raise BankReconciliationError("No se encontró la línea bancaria del ajuste contabilizado.")
    return bank_account, bank_entry


def _append_bank_difference_item(
    reconciliation_id: str,
    transaction: BankTransaction,
    difference_amount: Decimal,
    reconciliation_date: date,
    bank_entry: GLEntry,
    company: str,
) -> None:
    """Attach the posted bank adjustment to its reconciliation."""
    from cacao_accounting.bancos.reconciliation_service import _allocation_context

    context = _allocation_context(transaction, company, reconciliation_date)
    database.session.add(
        ReconciliationItem(
            reconciliation_id=reconciliation_id,
            reference_type="bank_transaction",
            reference_id=transaction.id,
            amount=difference_amount,
            allocated_amount=difference_amount,
            reconciliation_date=reconciliation_date,
            status="reconciled",
            source_type="bank_transaction",
            source_id=transaction.id,
            target_type="gl_entry",
            target_id=bank_entry.id,
            **context,
        )
    )


def _post_bank_difference_adjustment(
    reconciliation_id: str,
    transaction: BankTransaction,
    difference_amount: Decimal,
    user_id: str,
) -> None:
    """Post and attach a bank-difference journal to its reconciliation."""
    reconciliation = database.session.get(Reconciliation, reconciliation_id)
    reconciliation_date = reconciliation.recon_date if reconciliation is not None else date.today()
    journal = _submit_bank_difference_journal(
        reconciliation_id,
        transaction,
        _signed_bank_difference(transaction, difference_amount),
        user_id,
    )
    bank_account, bank_entry = _bank_difference_gl_entry(transaction, journal)
    _append_bank_difference_item(
        reconciliation_id,
        transaction,
        difference_amount,
        reconciliation_date,
        bank_entry,
        str(bank_account.company),
    )
    transaction.is_reconciled = True


def _validate_numbering_config_entry(
    bank_account: BankAccount, entry: Any
) -> tuple[dict[str, Any], str | None, str | None] | None:
    """Validate one bank numbering configuration entry."""
    if not isinstance(entry, dict):
        return None
    payment_type = entry.get("payment_type")
    if payment_type not in PAYMENT_TYPES:
        return None
    naming_series_id = entry.get("naming_series_id") or None
    external_counter_id = entry.get("external_counter_id") or None
    if naming_series_id:
        series = database.session.get(NamingSeries, naming_series_id)
        if not series or series.company not in (None, bank_account.company):
            raise IdentifierConfigurationError("La serie de numeración no pertenece a la compañía de la cuenta bancaria.")
    if entry.get("use_external_counter") and external_counter_id:
        counter = database.session.get(ExternalCounter, external_counter_id)
        if not counter or counter.company != bank_account.company:
            raise IdentifierConfigurationError("La chequera no pertenece a la compañía de la cuenta bancaria.")
    return entry, naming_series_id, external_counter_id


def _save_numbering_configs(bank_account: BankAccount) -> dict[str, str]:
    """Guarda las configuraciones de numeracion enviadas en el request JSON."""
    data = request.get_json(force=True) or {}
    configs = data.get("configs") if isinstance(data, dict) else None
    if not configs or not isinstance(configs, list):
        return {"status": "ok"}

    validated: list[tuple[dict[str, Any], str | None, str | None]] = []
    for entry in configs:
        result = _validate_numbering_config_entry(bank_account, entry)
        if result is not None:
            validated.append(result)

    for entry, naming_series_id, external_counter_id in validated:
        payment_type = entry["payment_type"]
        config = _get_or_create_numbering_config(bank_account.id, payment_type)
        config.naming_series_id = naming_series_id
        config.use_external_counter = bool(entry.get("use_external_counter"))
        config.external_counter_id = external_counter_id if config.use_external_counter else None

    database.session.commit()
    return {"status": "ok"}


def _get_or_create_numbering_config(bank_account_id: str, payment_type: str) -> BankAccountNumberingConfig:
    """Obtiene o crea una configuracion de numeracion para un tipo de pago."""
    config = database.session.execute(
        database.select(BankAccountNumberingConfig).filter_by(
            bank_account_id=bank_account_id,
            payment_type=payment_type,
        )
    ).scalar_one_or_none()
    if not config:
        config = BankAccountNumberingConfig(bank_account_id=bank_account_id, payment_type=payment_type)
        database.session.add(config)
    return config


def _build_numbering_config_response(bank_account: BankAccount) -> dict[str, list[dict[str, Any]]]:
    """Construye la respuesta GET con configuraciones de numeracion por tipo de pago."""
    from cacao_accounting.document_identifiers import PAYMENT_TYPE_TO_ENTITY_TYPE as ENTITY_MAP

    configs = (
        database.session.execute(
            database.select(BankAccountNumberingConfig)
            .filter_by(bank_account_id=bank_account.id)
            .order_by(BankAccountNumberingConfig.payment_type)
        )
        .scalars()
        .all()
    )

    return {"configs": [_build_single_config_entry(pt, list(configs), ENTITY_MAP) for pt in PAYMENT_TYPES]}


def _build_single_config_entry(
    payment_type: str,
    configs: list[BankAccountNumberingConfig],
    entity_map: dict[str, str],
) -> dict[str, Any]:
    """Construye un diccionario de configuracion para un tipo de pago."""
    cfg = next((c for c in configs if c.payment_type == payment_type), None)
    entity_type = entity_map.get(payment_type, "payment_entry")
    if cfg:
        return {
            "payment_type": cfg.payment_type,
            "naming_series_id": cfg.naming_series_id,
            "use_external_counter": cfg.use_external_counter,
            "external_counter_id": cfg.external_counter_id,
            "entity_type": entity_type,
        }
    return {
        "payment_type": payment_type,
        "naming_series_id": None,
        "use_external_counter": payment_type in ("pay", "receive"),
        "external_counter_id": None,
        "entity_type": entity_type,
    }


def _form_decimal(field_name: str, default: str = "0") -> Decimal:
    """Convierte un valor de formulario a Decimal."""
    value = request.form.get(field_name)
    return Decimal(str(value if value not in (None, "") else default))


def _invoice_outstanding(invoice) -> Decimal:
    """Devuelve el saldo vivo calculado de una factura."""
    computed = compute_outstanding_amount(invoice)
    raw_cached = getattr(invoice, "outstanding_amount", None)
    if raw_cached is None:
        return computed
    cached = Decimal(str(raw_cached))
    if cached < 0:
        return computed
    if cached < computed:
        refresh_outstanding_amount_cache(invoice)
        return computed
    return min(computed, cached)


def _payment_reference_lines_from_form() -> list[dict]:
    """Construye las líneas de referencia desde el formulario HTTP."""
    lines: list[dict] = []
    index = 0
    while request.form.get(f"reference_id_{index}"):
        lines.append(
            {
                "reference_type": request.form.get(f"reference_type_{index}", ""),
                "reference_id": request.form.get(f"reference_id_{index}", ""),
                "allocated_amount": _form_decimal(f"allocated_amount_{index}", "0"),
            }
        )
        index += 1
    return lines


def _payment_reference_model(reference_type: str) -> type[Any]:
    """Resuelve el modelo real para una referencia de pago."""
    if reference_type in ("purchase_invoice", "purchase_order", "purchase_credit_note", "purchase_debit_note"):
        return PurchaseInvoice if "invoice" in reference_type or "note" in reference_type else PurchaseOrder
    if reference_type in ("sales_invoice", "sales_order", "sales_credit_note", "sales_return", "sales_debit_note"):
        is_invoice_like = "invoice" in reference_type or "note" in reference_type or "return" in reference_type
        return SalesInvoice if is_invoice_like else SalesOrder
    raise ValueError(_("Tipo de referencia inválido: {0}").format(reference_type))


def _payment_reference_expected_payment_type(flow_source_type: str) -> str | None:
    """Devuelve el tipo de pago esperado para un tipo documental origen."""
    return {
        "purchase_credit_note": "receive",
        "purchase_debit_note": "pay",
        "sales_credit_note": "pay",
        "sales_return": "pay",
        "sales_debit_note": "receive",
    }.get(flow_source_type)


def _load_payment_reference_document(reference_type: str, reference_id: str, flow_source_type: str) -> Any:
    """Obtiene el documento real referenciado para el pago con bloqueo de fila."""
    model = _payment_reference_model(reference_type)
    document = database.session.get(model, reference_id, with_for_update=True)
    if not document:
        raise ValueError(_("Documento referenciado no existe."))
    return document


def _validate_payment_reference_document(
    *,
    payment: PaymentEntry,
    document: Any,
    flow_source_type: str,
) -> None:
    """Valida compañía, tercero, estado y moneda del documento referenciado.

    CAS-03: Se valida que la moneda del pago coincida con la moneda del documento
    referenciado para evitar inconsistencias contables en pagos multimoneda.
    """
    if getattr(document, "docstatus", 0) != 1:
        raise ValueError(_("El documento referenciado debe estar aprobado."))
    if payment.company and document.company and payment.company != document.company:
        from werkzeug.exceptions import Conflict

        raise Conflict(_("El documento referenciado no pertenece a la misma compañía."))
    expected_party_type, expected_party_id = _reference_party_info(document)
    if payment.party_type and payment.party_type != expected_party_type:
        from werkzeug.exceptions import Conflict

        raise Conflict(_("El tercero del pago no es compatible con el documento referenciado."))
    if payment.party_id and expected_party_id and payment.party_id != expected_party_id:
        from werkzeug.exceptions import Conflict

        raise Conflict(_("El tercero del pago no coincide con el documento referenciado."))
    expected_payment_type = _payment_reference_expected_payment_type(flow_source_type)
    if expected_payment_type and payment.payment_type != expected_payment_type:
        raise ValueError(_("El tipo de pago no corresponde con el tipo de nota referenciada."))
    document_currency = getattr(document, "transaction_currency", None) or getattr(document, "currency", None)
    _validate_document_payment_exchange_rate(document, document_currency)


def _validate_document_payment_exchange_rate(document: Any, document_currency: str | None) -> None:
    """Require a valid historical rate before settling a foreign document."""
    company = getattr(document, "company", None)
    entity = (
        database.session.execute(database.select(Entity).filter_by(code=company)).scalar_one_or_none() if company else None
    )
    company_currency = getattr(entity, "currency", None)
    if not document_currency or not company_currency or document_currency == company_currency:
        return
    exchange_rate = getattr(document, "exchange_rate", None)
    if exchange_rate is None or Decimal(str(exchange_rate)) <= 0:
        raise ValueError(_("El documento referenciado no tiene un tipo de cambio válido para su moneda de transacción."))


def _build_payment_reference(
    *,
    payment: PaymentEntry,
    line: dict,
    document: Any,
    reference_id: str,
    reference_type: str,
    flow_source_type: str,
    allocated: Decimal,
    outstanding: Decimal,
) -> PaymentReference:
    """Construye la referencia persistible para una línea validada."""
    discount_amount = Decimal(str(line.get("discount_amount") or "0"))
    gain_loss_amount = Decimal(str(line.get("gain_loss_amount") or "0"))
    difference_amount = Decimal(str(line.get("difference_amount") or gain_loss_amount or "0"))
    document_currency = str(
        getattr(document, "transaction_currency", None) or getattr(document, "currency", None) or payment.currency or ""
    )
    payment_currency = str(payment.currency or "")
    allocation_date = payment.posting_date or date.today()
    company_entity = database.session.execute(database.select(Entity).filter_by(code=payment.company)).scalar_one_or_none()
    company_currency = str(getattr(company_entity, "currency", None) or payment.base_currency or "")
    if not payment_currency:
        payment_currency = company_currency
    if not document_currency:
        document_currency = company_currency
    document_rate = Decimal(str(getattr(document, "exchange_rate", None) or "0"))
    if document_currency == company_currency:
        document_rate = Decimal("1")
    elif document_rate <= 0:
        document_rate = _lookup_exchange_rate(document_currency, company_currency, allocation_date)
    payment_rate = Decimal(str(getattr(payment, "exchange_rate", None) or "0"))
    if payment_currency == company_currency:
        payment_rate = Decimal("1")
    elif payment_rate <= 0:
        payment_rate = _lookup_exchange_rate(payment_currency, company_currency, allocation_date)
    if document_rate <= 0 or payment_rate <= 0:
        raise ValueError(_("No existe una tasa de cambio positiva para aplicar el documento."))
    cross_rate = Decimal(str(line.get("payment_exchange_rate") or "0"))
    if cross_rate <= 0:
        cross_rate = (document_rate / payment_rate).quantize(Decimal("0.000000001"))
    if cross_rate <= 0:
        raise ValueError(_("La tasa de cambio de la referencia debe ser mayor que cero."))
    cash_document_amount = allocated - discount_amount - gain_loss_amount
    if cash_document_amount < 0:
        raise ValueError(_("Los ajustes no pueden superar el importe aplicado."))
    payment_amount = (cash_document_amount * cross_rate).quantize(Decimal("0.0001"))
    base_allocated_amount = (allocated * document_rate).quantize(Decimal("0.0001"))
    base_payment_amount = (payment_amount * payment_rate).quantize(Decimal("0.0001"))
    non_cash_base_amount = ((discount_amount + gain_loss_amount) * document_rate).quantize(Decimal("0.0001"))
    fx_difference_amount = base_allocated_amount - non_cash_base_amount - base_payment_amount
    reference_date = _payment_reference_date(document)
    outstanding_after = outstanding - allocated
    physical_reference_type = _physical_reference_type(reference_type, flow_source_type)
    return PaymentReference(
        payment_id=payment.id,
        reference_type=physical_reference_type,
        flow_source_type=flow_source_type,
        reference_id=reference_id,
        reference_document_no=getattr(document, "document_no", None) or reference_id,
        reference_date=reference_date,
        party_type=_reference_party_info(document)[0],
        party_id=_reference_party_info(document)[1],
        company=getattr(document, "company", None),
        currency=document_currency,
        total_amount=document.grand_total,
        outstanding_amount=outstanding,
        outstanding_amount_after=outstanding_after,
        allocated_amount=allocated,
        payment_currency=payment_currency,
        payment_amount=payment_amount,
        payment_exchange_rate=cross_rate,
        base_allocated_amount=base_allocated_amount,
        base_payment_amount=base_payment_amount,
        fx_difference_amount=fx_difference_amount,
        exchange_rate=document_rate,
        difference_amount=difference_amount or fx_difference_amount,
        allocation_date=allocation_date,
        discount_amount=discount_amount,
        gain_loss_amount=gain_loss_amount,
        notes=line.get("notes"),
    )


def _validate_payment_reference_line(
    *,
    payment: PaymentEntry,
    line: dict,
    allow_order_references: bool,
    processed_keys: set[tuple[str, str]],
) -> tuple[str, str, str, Decimal, Decimal]:
    """Valida una línea de referencia y devuelve sus valores normalizados."""
    reference_type = line.get("reference_type", "")
    reference_id = line.get("reference_id", "")
    allocated = Decimal(str(line.get("allocated_amount", "0")))
    discount = Decimal(str(line.get("discount_amount") or "0"))
    gain_loss = Decimal(str(line.get("gain_loss_amount") or "0"))
    requested_flow_source_type = str(line.get("flow_source_type") or reference_type)
    reference_key = (_physical_reference_type(reference_type, requested_flow_source_type), reference_id)
    if reference_key in processed_keys:
        from werkzeug.exceptions import Conflict

        raise Conflict(_("No se puede aplicar la misma factura dos veces en un pago."))
    processed_keys.add(reference_key)
    if allocated <= 0:
        if allocated < 0:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("El monto asignado no puede ser negativo."))
        return reference_type, reference_id, requested_flow_source_type, allocated, Decimal("0")
    if discount + gain_loss >= allocated:
        raise ValueError(
            _("El descuento + diferencia de cambio ({0}) no puede ser igual o mayor al monto asignado ({1}).").format(
                discount + gain_loss, allocated
            )
        )
    if normalize_doctype(requested_flow_source_type) in ("purchase_order", "sales_order") and not allow_order_references:
        raise ValueError(_("Las órdenes solo pueden referenciarse en flujo de anticipo."))
    return reference_type, reference_id, requested_flow_source_type, allocated, allocated


def _append_payment_source_row(
    rows: list[dict],
    *,
    document: Any | None,
    reference_type: str,
    label: str,
    url_route: str,
    url_param_name: str,
    flow_source_type: str | None = None,
    document_type: str | None = None,
) -> None:
    """Agrega una fila de origen cuando el documento existe y cumple el filtro."""
    if not document:
        return
    if document_type and getattr(document, "document_type", None) != document_type:
        return
    row = {
        "reference_type": reference_type,
        "label": label,
        "document": document,
        "url": url_for(url_route, **{url_param_name: document.id}),
    }
    if flow_source_type:
        row["flow_source_type"] = flow_source_type
    rows.append(row)


def _payment_source_rows(
    purchase_invoice_ids: list[str],
    sales_invoice_ids: list[str],
    purchase_order_ids: list[str],
    sales_order_ids: list[str],
    purchase_credit_note_ids: list[str],
    purchase_debit_note_ids: list[str],
    sales_credit_note_ids: list[str],
    sales_debit_note_ids: list[str],
) -> list[dict]:
    """Construye las filas origen para el formulario de pago."""
    rows: list[dict[str, Any]] = []
    for reference_type, reference_id in _payment_source_pairs(
        purchase_invoice_ids,
        sales_invoice_ids,
        purchase_order_ids,
        sales_order_ids,
        purchase_credit_note_ids,
        purchase_debit_note_ids,
        sales_credit_note_ids,
        sales_debit_note_ids,
    ):
        _append_payment_source_row(rows, **_payment_source_descriptor(reference_type, reference_id))
    return rows


def _payment_source_pairs(
    purchase_invoice_ids: list[str],
    sales_invoice_ids: list[str],
    purchase_order_ids: list[str],
    sales_order_ids: list[str],
    purchase_credit_note_ids: list[str],
    purchase_debit_note_ids: list[str],
    sales_credit_note_ids: list[str],
    sales_debit_note_ids: list[str],
) -> list[tuple[str, str]]:
    """Aplana los orígenes de pago preservando el orden de entrada."""
    pairs: list[tuple[str, str]] = []
    pairs.extend(("purchase_invoice", invoice_id) for invoice_id in purchase_invoice_ids)
    pairs.extend(("sales_invoice", invoice_id) for invoice_id in sales_invoice_ids)
    pairs.extend(("purchase_order", order_id) for order_id in purchase_order_ids)
    pairs.extend(("sales_order", order_id) for order_id in sales_order_ids)
    pairs.extend(("purchase_credit_note", invoice_id) for invoice_id in purchase_credit_note_ids)
    pairs.extend(("purchase_debit_note", invoice_id) for invoice_id in purchase_debit_note_ids)
    pairs.extend(("sales_credit_note", invoice_id) for invoice_id in sales_credit_note_ids)
    pairs.extend(("sales_debit_note", invoice_id) for invoice_id in sales_debit_note_ids)
    return pairs


def _payment_source_descriptor(reference_type: str, reference_id: str) -> dict[str, Any]:
    """Devuelve el descriptor completo para una fila de origen de pago."""
    match reference_type:
        case "purchase_invoice":
            return {
                "document": database.session.get(PurchaseInvoice, reference_id),
                "reference_type": "purchase_invoice",
                "label": LABEL_FACTURA_COMPRA,
                "url_route": COMPRAS_FACTURA_COMPRA_ROUTE,
                "url_param_name": "invoice_id",
            }
        case "sales_invoice":
            return {
                "document": database.session.get(SalesInvoice, reference_id),
                "reference_type": "sales_invoice",
                "label": LABEL_FACTURA_VENTA,
                "url_route": VENTAS_FACTURA_VENTA_ROUTE,
                "url_param_name": "invoice_id",
            }
        case "purchase_order":
            return {
                "document": database.session.get(PurchaseOrder, reference_id),
                "reference_type": "purchase_order",
                "label": _("Orden de Compra"),
                "url_route": "compras.compras_orden_compra",
                "url_param_name": "order_id",
            }
        case "sales_order":
            return {
                "document": database.session.get(SalesOrder, reference_id),
                "reference_type": "sales_order",
                "label": _("Orden de Venta"),
                "url_route": "ventas.ventas_orden_venta",
                "url_param_name": "order_id",
            }
        case "purchase_credit_note":
            return {
                "document": database.session.get(PurchaseInvoice, reference_id),
                "reference_type": "purchase_invoice",
                "label": _("Nota de Crédito de Compra"),
                "url_route": COMPRAS_FACTURA_COMPRA_ROUTE,
                "url_param_name": "invoice_id",
                "flow_source_type": "purchase_credit_note",
                "document_type": "purchase_credit_note",
            }
        case "purchase_debit_note":
            return {
                "document": database.session.get(PurchaseInvoice, reference_id),
                "reference_type": "purchase_invoice",
                "label": _("Nota de Débito de Compra"),
                "url_route": COMPRAS_FACTURA_COMPRA_ROUTE,
                "url_param_name": "invoice_id",
                "flow_source_type": "purchase_debit_note",
                "document_type": "purchase_debit_note",
            }
        case "sales_credit_note":
            return {
                "document": database.session.get(SalesInvoice, reference_id),
                "reference_type": "sales_invoice",
                "label": _("Nota de Crédito de Venta"),
                "url_route": VENTAS_FACTURA_VENTA_ROUTE,
                "url_param_name": "invoice_id",
                "flow_source_type": "sales_credit_note",
                "document_type": "sales_credit_note",
            }
        case "sales_return":
            return {
                "document": database.session.get(SalesInvoice, reference_id),
                "reference_type": "sales_invoice",
                "label": _("Devolución de Venta"),
                "url_route": VENTAS_FACTURA_VENTA_ROUTE,
                "url_param_name": "invoice_id",
                "flow_source_type": "sales_return",
                "document_type": "sales_return",
            }
        case "sales_debit_note":
            return {
                "document": database.session.get(SalesInvoice, reference_id),
                "reference_type": "sales_invoice",
                "label": _("Nota de Débito de Venta"),
                "url_route": VENTAS_FACTURA_VENTA_ROUTE,
                "url_param_name": "invoice_id",
                "flow_source_type": "sales_debit_note",
                "document_type": "sales_debit_note",
            }
        case _:
            raise ValueError(_("Tipo de referencia de pago no soportado."))


def _payment_profile_from_source_type(flow_source_type: str) -> tuple[str, str]:
    """Resuelve party_type/payment_type según el tipo documental origen."""
    match flow_source_type:
        case "purchase_invoice" | "purchase_order" | "purchase_debit_note":
            return "supplier", "pay"
        case "purchase_credit_note":
            return "supplier", "receive"
        case "sales_invoice" | "sales_order" | "sales_debit_note":
            return "customer", "receive"
        case "sales_credit_note" | "sales_return":
            return "customer", "pay"
        case _:
            return "customer", "receive"


def _reference_party_info(document: Any) -> tuple[str, str | None]:
    """Devuelve el tipo e id de tercero esperado para un documento AR/AP."""
    raw_type = normalize_doctype(str(getattr(document, "document_type", None) or getattr(document, "__tablename__", "")))
    if raw_type.startswith("purchase_"):
        return "supplier", getattr(document, "supplier_id", None)
    return "customer", getattr(document, "customer_id", None)


def _payment_reference_date(document: object) -> date | None:
    """Devuelve la fecha representativa para snapshot de referencia de pago."""
    raw_date = (
        getattr(document, "posting_date", None)
        or getattr(document, "bill_date", None)
        or getattr(document, "transaction_date", None)
        or getattr(document, "due_date", None)
    )
    return raw_date if isinstance(raw_date, date) else None


def _flow_source_type(reference_type: str, document: object, line: dict) -> str:
    """Resuelve el tipo lógico de origen que debe conservarse en trazabilidad."""
    explicit = str(line.get("flow_source_type") or "").strip().lower()
    document_type = normalize_doctype(str(getattr(document, "document_type", None) or reference_type))
    legacy_aliases = {
        "purchase_invoice": {"purchase_invoice", "purchase_credit_note", "purchase_debit_note"},
        "sales_invoice": {"sales_invoice", "sales_credit_note", "sales_debit_note", "sales_return"},
    }
    equivalent = legacy_aliases.get(document_type, {document_type})
    if explicit and normalize_doctype(explicit) not in equivalent:
        raise ValueError(_("El tipo de flujo no coincide con el tipo documental referenciado."))
    return document_type


def _physical_reference_type(reference_type: str, flow_source_type: str) -> str:
    """Normaliza el tipo físico que apunta a la tabla real referenciada."""
    source_key = normalize_doctype(flow_source_type or reference_type)
    if source_key in {"purchase_credit_note", "purchase_debit_note"}:
        return "purchase_invoice"
    if source_key in {"sales_credit_note", "sales_debit_note", "sales_return"}:
        return "sales_invoice"
    return normalize_doctype(reference_type)


def _order_outstanding(order: PurchaseOrder | SalesOrder, source_type: str) -> Decimal:
    """Calcula el monto de anticipo aún disponible para una orden."""
    rows = database.session.execute(
        database.select(PaymentReference.allocated_amount)
        .join(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            DocumentRelation.source_type == source_type,
            DocumentRelation.source_id == order.id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
            PaymentEntry.docstatus == 1,
        )
    ).scalars()
    allocated = sum((Decimal(str(value or "0")) for value in rows), Decimal("0"))
    total = Decimal(str(getattr(order, "grand_total", None) or "0"))
    pending = total - allocated
    return pending if pending > 0 else Decimal("0")


def _reference_outstanding(document: Any, flow_source_type: str) -> Decimal:
    """Calcula el saldo aplicable antes de la referencia."""
    if flow_source_type in {"purchase_order", "sales_order"}:
        return _order_outstanding(cast(PurchaseOrder | SalesOrder, document), flow_source_type)
    return _invoice_outstanding(document)


def _validate_payment_header(
    *,
    payment_type: str,
    company: str | None,
    bank_account_id: str | None,
    posting_date_raw: str | None,
    amount: Decimal,
    party_type: str | None,
    party_id: str | None,
    target_bank_account_id: str | None = None,
    allow_zero_amount: bool = False,
) -> None:
    """Validate the required Payment Entry header fields."""
    _validate_payment_header_required_fields(
        company=company,
        bank_account_id=bank_account_id,
        posting_date_raw=posting_date_raw,
        amount=amount,
        allow_zero_amount=allow_zero_amount,
    )
    validated_company = cast(str, company)
    validated_bank_account_id = cast(str, bank_account_id)
    _validate_payment_bank_account(company=validated_company, bank_account_id=validated_bank_account_id)
    _validate_payment_target_bank_account(
        company=validated_company,
        bank_account_id=validated_bank_account_id,
        payment_type=payment_type,
        target_bank_account_id=target_bank_account_id,
    )
    _validate_payment_party(payment_type=payment_type, party_type=party_type, party_id=party_id)


def _validate_payment_header_required_fields(
    *,
    company: str | None,
    bank_account_id: str | None,
    posting_date_raw: str | None,
    amount: Decimal,
    allow_zero_amount: bool = False,
) -> None:
    """Validate the required payment header fields that are independent."""
    if not company:
        raise ValueError(_("La compañía es obligatoria."))
    if not bank_account_id:
        raise ValueError(_("La cuenta bancaria es obligatoria."))
    if not posting_date_raw:
        raise ValueError(_("La fecha del pago es obligatoria."))
    if amount < 0 or (amount == 0 and not allow_zero_amount):
        raise ValueError(_("El monto del pago debe ser mayor que cero."))


def _validate_payment_bank_account(*, company: str, bank_account_id: str) -> None:
    """Validate that the payment source bank account is active and belongs to the company."""
    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        raise ValueError(_("La cuenta bancaria seleccionada no existe."))
    if bank_account.company != company:
        raise ValueError(_("La cuenta bancaria no pertenece a la misma compañía del pago."))
    if not bank_account.is_active:
        raise ValueError(_("La cuenta bancaria seleccionada está inactiva."))


def _validate_payment_target_bank_account(
    *, company: str, bank_account_id: str, payment_type: str, target_bank_account_id: str | None
) -> None:
    """Validate that the target bank account is active and belongs to the company."""
    if not target_bank_account_id:
        return
    target_bank_account = database.session.get(BankAccount, target_bank_account_id)
    if not target_bank_account:
        raise ValueError(_("La cuenta bancaria destino no existe."))
    if target_bank_account.company != company:
        raise ValueError(_("La cuenta bancaria destino no pertenece a la misma compañía del pago."))
    if not target_bank_account.is_active:
        raise ValueError(_("La cuenta bancaria destino está inactiva."))
    if payment_type == "internal_transfer":
        source_bank_account = database.session.get(BankAccount, bank_account_id)
        if source_bank_account and source_bank_account.id == target_bank_account.id:
            raise ValueError(_("La cuenta bancaria de origen y destino deben ser distintas."))
        if not target_bank_account.currency:
            raise ValueError(_("La cuenta bancaria destino no tiene moneda configurada."))


def _validate_payment_party(*, payment_type: str, party_type: str | None, party_id: str | None) -> None:
    """Validate the relationship between payment type and party."""
    if payment_type in ("pay", "receive") and (not party_type or not party_id):
        raise ValueError(_("El tercero es obligatorio para pagos y cobros."))
    if party_id and party_type not in ("supplier", "customer"):
        raise ValueError(_("El tipo de tercero del pago no es válido."))


def _save_payment_references(
    payment: PaymentEntry,
    lines: list[dict] | None = None,
    *,
    allow_order_references: bool = False,
) -> dict[str, Decimal]:
    """Guarda referencias de pago y actualiza saldos vivos de facturas."""
    if lines is None:
        lines = _payment_reference_lines_from_form()

    totals = _payment_reference_totals()
    processed_keys: set[tuple[str, str]] = set()
    for line in lines:
        totals = _process_payment_reference_line(
            payment=payment,
            line=line,
            totals=totals,
            allow_order_references=allow_order_references,
            processed_keys=processed_keys,
        )
    return totals


def _payment_reference_totals() -> dict[str, Decimal]:
    """Inicializa el acumulador de totales de referencias de pago."""
    return {
        "allocated": Decimal("0"),
        "payment_amount": Decimal("0"),
        "discount": Decimal("0"),
        "gain_loss": Decimal("0"),
    }


def _process_payment_reference_line(
    *,
    payment: PaymentEntry,
    line: dict,
    totals: dict[str, Decimal],
    allow_order_references: bool,
    processed_keys: set[tuple[str, str]],
) -> dict[str, Decimal]:
    """Valida una línea de referencia y la aplica cuando corresponde."""
    reference_type, reference_id, requested_flow_source_type, allocated, applied_amount = _validate_payment_reference_line(
        payment=payment,
        line=line,
        allow_order_references=allow_order_references,
        processed_keys=processed_keys,
    )
    if applied_amount <= 0:
        return totals
    return _apply_payment_reference_line(
        payment=payment,
        line=line,
        reference_type=reference_type,
        reference_id=reference_id,
        requested_flow_source_type=requested_flow_source_type,
        allocated=allocated,
        totals=totals,
    )


def _apply_payment_reference_line(
    *,
    payment: PaymentEntry,
    line: dict,
    reference_type: str,
    reference_id: str,
    requested_flow_source_type: str,
    allocated: Decimal,
    totals: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Aplica una linea de referencia de pago y acumula totales."""
    document = _load_payment_reference_document(reference_type, reference_id, requested_flow_source_type)
    document = cast(PurchaseInvoice | SalesInvoice | PurchaseOrder | SalesOrder, document)
    flow_source_type = _flow_source_type(reference_type, document, line)
    _validate_payment_reference_document(payment=payment, document=document, flow_source_type=flow_source_type)
    outstanding = _reference_outstanding(document, flow_source_type)
    if outstanding <= 0:
        raise ValueError(
            _("El documento {0} no tiene saldo pendiente (Saldo: {1}).").format(
                getattr(document, "document_no", reference_id), outstanding
            )
        )
    if allocated > outstanding + Decimal("0.01"):
        raise ValueError(
            _("El monto aplicado ({0}) no puede ser mayor al saldo pendiente ({1}) del documento {2}.").format(
                allocated, outstanding, getattr(document, "document_no", reference_id)
            )
        )
    reference = _build_payment_reference(
        payment=payment,
        line=line,
        document=document,
        reference_id=reference_id,
        reference_type=reference_type,
        flow_source_type=flow_source_type,
        allocated=allocated,
        outstanding=outstanding,
    )
    database.session.add(reference)
    database.session.flush()
    create_document_relation(
        source_type=flow_source_type,
        source_id=reference_id,
        source_item_id=None,
        target_type="payment_entry",
        target_id=payment.id,
        target_item_id=reference.id,
        qty=Decimal("1"),
        uom=None,
        rate=allocated,
        amount=allocated,
    )
    if flow_source_type not in {"purchase_order", "sales_order"}:
        document.outstanding_amount = reference.outstanding_amount_after
        document.base_outstanding_amount = document.outstanding_amount * (
            Decimal(str(getattr(document, "exchange_rate", None) or 1))
        )
    totals["allocated"] += allocated
    totals["payment_amount"] += Decimal(str(reference.payment_amount or "0"))
    totals["discount"] += reference.discount_amount
    totals["gain_loss"] += reference.gain_loss_amount
    return totals


def _refresh_payment_reference_document(reference_type: str, reference_id: str) -> None:
    """Actualiza el cache de saldo pendiente para documentos referenciados."""
    match reference_type:
        case "purchase_invoice" | "purchase_credit_note" | "purchase_debit_note":
            model = PurchaseInvoice
        case "sales_invoice" | "sales_credit_note" | "sales_return" | "sales_debit_note":
            model = SalesInvoice
        case "purchase_order":
            model = PurchaseOrder
        case "sales_order":
            model = SalesOrder
        case _:
            return
    document = database.session.get(model, reference_id)
    if document:
        refresh_outstanding_amount_cache(document)


def _resolve_payment_numbering(
    payload: PaymentPayload,
    payment: PaymentEntry,
    mode_of_payment: str,
) -> tuple[str | None, str | None]:
    """Resolve naming_series_id and external_counter_id for a payment."""
    config = _resolve_bank_account_numbering_config(payment.bank_account_id, payment.payment_type or "pay")
    naming_series_id = cast(str | None, payload.get("naming_series_id"))
    if naming_series_id is None:
        if config and config.naming_series_id:
            naming_series_id = config.naming_series_id
        else:
            legacy_series_id, _legacy_counter_id = _payment_numbering_defaults(payment.bank_account_id)
            naming_series_id = legacy_series_id

    external_counter_id: str | None = None
    if mode_of_payment == "check":
        external_counter_id = cast(str | None, payload.get("external_counter_id"))
        if external_counter_id is None and config and config.use_external_counter:
            external_counter_id = config.external_counter_id
        if external_counter_id is None:
            _legacy_series_id, legacy_counter_id = _payment_numbering_defaults(payment.bank_account_id)
            external_counter_id = legacy_counter_id

    return naming_series_id, external_counter_id


def _finalize_and_commit_payment(
    payment: PaymentEntry,
    payload: PaymentPayload,
    amount: Decimal,
) -> Any:
    """Validate references, persist fiscal snapshot, log, and commit."""
    ref_totals = _save_payment_references(
        payment,
        payload.get("lines") or [],
        allow_order_references=bool(payload.get("advance_mode")),
    )
    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount

    payment.unallocated_amount = compute_payment_unallocated_amount(payment)
    persist_document_fiscal_snapshot(
        company=str(payment.company or ""),
        document_type="payment_entry",
        document_id=payment.id,
        currency=payment.currency,
        tax_lines=payload.get("tax_lines"),
        tax_summary=payload.get("tax_summary"),
    )
    _validate_payment_reference_totals(amount, ref_totals, _payment_withholding_total(payment.id))
    _warn_duplicate_payment(payment)
    log_create(payment)
    database.session.commit()
    flash(_("Pago registrado correctamente."), "success")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment.id))


def _create_payment_from_request():
    """Create a payment from the submitted request payload."""
    try:
        payload = _payment_payload_from_request()
        payment, amount, mode_of_payment = _build_payment_from_payload(payload)
        payment.payment_type = payment.payment_type or payload.get("payment_type") or "pay"
        entity_type = _payment_type_to_entity_type(payment.payment_type)
        naming_series_id, external_counter_id = _resolve_payment_numbering(payload, payment, mode_of_payment)
        assign_document_identifier(
            document=payment,
            entity_type=entity_type,
            posting_date_raw=payload.get("posting_date"),
            naming_series_id=naming_series_id,
            external_counter_id=external_counter_id,
            external_number=None,
            external_context=_payment_identifier_context(payment, mode_of_payment),
        )
        return _finalize_and_commit_payment(payment, payload, amount)
    except (ValueError, ArithmeticError) as exc:
        database.session.rollback()
        flash_error(exc)
    except Exception as exc:  # noqa: BLE001
        from werkzeug.exceptions import HTTPException

        database.session.rollback()
        if isinstance(exc, HTTPException):
            flash(exc.description or str(exc), "danger")
        else:
            raise
    return None


def _payment_payload_from_request() -> PaymentPayload:
    """Return the payment payload from the request body or form fields."""
    payload_raw = request.form.get("payment_payload")
    if payload_raw:
        return cast(PaymentPayload, json.loads(payload_raw))
    return {
        "payment_type": request.form.get("payment_type"),
        "company": request.form.get("company"),
        "bank_account_id": request.form.get("bank_account_id"),
        "posting_date": request.form.get("posting_date"),
        "paid_amount": request.form.get("paid_amount") or request.form.get("received_amount"),
        "party_id": request.form.get("party_id"),
        "party_type": request.form.get("party_type"),
        "naming_series_id": request.form.get("naming_series"),
        "external_counter_id": request.form.get("external_counter_id"),
        "external_number": request.form.get("external_number"),
        "target_bank_account_id": request.form.get("target_bank_account_id"),
        "mode_of_payment": request.form.get("mode_of_payment"),
        "cost_center_code": request.form.get("cost_center_code"),
        "unit_code": request.form.get("unit_code"),
        "project_code": request.form.get("project_code"),
    }


def _resolve_payment_exchange_rate(payload: PaymentPayload, payment_currency: str, company: str | None) -> Decimal:
    """Determine the exchange rate for a payment."""
    company_entity = (
        database.session.execute(database.select(Entity).filter(Entity.code == company)).scalars().first() if company else None
    )
    company_currency = company_entity.currency if company_entity else None
    posting_date_raw = payload.get("posting_date")
    if company_currency and payment_currency != company_currency and posting_date_raw:
        return _lookup_exchange_rate(payment_currency, company_currency, posting_date_raw)  # type: ignore[misc]
    return Decimal("1")


def _apply_internal_transfer_amounts(
    payment: PaymentEntry, payload: PaymentPayload, payment_type: str, amount: Decimal, target_bank: BankAccount | None
) -> None:
    """Apply multi-currency adjustments for internal transfers."""
    if payment_type != "internal_transfer":
        return
    transfer_rate = Decimal(str(payload.get("exchange_rate") or "1"))
    if transfer_rate <= 0:
        raise ValueError(_("La transferencia multimoneda requiere un tipo de cambio positivo."))
    if target_bank and target_bank.currency:
        payment.received_amount = (amount * transfer_rate).quantize(Decimal("0.0001"))
        payment.base_received_amount = None


def _build_payment_from_payload(payload: PaymentPayload) -> tuple[PaymentEntry, Decimal, str]:
    """Build a PaymentEntry from the normalized payload."""
    payment_type = str(payload.get("payment_type") or "receive")
    company = cast(str | None, payload.get("company"))
    bank_account_id = cast(str | None, payload.get("bank_account_id"))
    amount = Decimal(str(payload.get("paid_amount") or "0"))
    target_bank_account_id = cast(str | None, payload.get("target_bank_account_id"))

    _validate_payment_header(
        payment_type=payment_type,
        company=company,
        bank_account_id=bank_account_id,
        posting_date_raw=payload.get("posting_date"),
        amount=amount,
        party_type=payload.get("party_type"),
        party_id=payload.get("party_id"),
        target_bank_account_id=target_bank_account_id,
        allow_zero_amount=_allows_fully_withheld_payment(payload, amount),
    )
    # La compañía enviada por el cliente no es una autorización.  Bloquear
    # antes de crear y hacer flush evita dejar borradores cross-company.
    exige_acceso_compania("cash", str(company), "crear", allow_unauthenticated=True)

    paid_from_account_id, paid_to_account_id = _resolve_gl_accounts(
        payload, payment_type, bank_account_id, target_bank_account_id
    )
    _validate_payment_gl_accounts(
        company=str(company),
        payment_type=payment_type,
        bank_account_id=bank_account_id,
        target_bank_account_id=target_bank_account_id,
        paid_from_account_id=paid_from_account_id,
        paid_to_account_id=paid_to_account_id,
    )
    reference_date = _parse_reference_date(payload.get("reference_date"))
    payment_currency = _get_payment_currency(bank_account_id)
    target_bank = database.session.get(BankAccount, target_bank_account_id) if target_bank_account_id else None
    mode_of_payment = str(payload.get("mode_of_payment") or "").strip().lower()

    exchange_rate = _resolve_payment_exchange_rate(payload, payment_currency, company)
    base_currency = _payment_base_currency(company)
    payment = _create_payment_entry(
        payload=payload,
        payment_type=payment_type,
        company=company,
        bank_account_id=bank_account_id,
        target_bank_account_id=target_bank_account_id,
        amount=amount,
        payment_currency=payment_currency,
        reference_date=reference_date,
        mode_of_payment=mode_of_payment,
        paid_from_account_id=paid_from_account_id,
        paid_to_account_id=paid_to_account_id,
        exchange_rate=exchange_rate,
        base_currency=base_currency,
    )
    _update_payment_amounts(payment, payment_type, amount)
    _apply_internal_transfer_amounts(payment, payload, payment_type, amount, target_bank)
    database.session.add(payment)
    database.session.flush()
    return payment, amount, mode_of_payment


def _resolve_gl_accounts(
    payload: PaymentPayload,
    payment_type: str,
    bank_account_id: str | None,
    target_bank_account_id: str | None,
) -> tuple[str | None, str | None]:
    """Resolve GL account IDs from bank accounts for internal transfers."""
    paid_from_account_id = payload.get("paid_from_account_id")
    paid_to_account_id = payload.get("paid_to_account_id")

    if payment_type == "internal_transfer":
        source_bank = database.session.get(BankAccount, bank_account_id) if bank_account_id else None
        target_bank = database.session.get(BankAccount, target_bank_account_id) if target_bank_account_id else None
        if source_bank and not paid_from_account_id:
            paid_from_account_id = source_bank.gl_account_id
        if target_bank and not paid_to_account_id:
            paid_to_account_id = target_bank.gl_account_id

    return paid_from_account_id, paid_to_account_id


def _validate_payment_gl_accounts(
    *,
    company: str,
    payment_type: str,
    bank_account_id: str | None,
    target_bank_account_id: str | None,
    paid_from_account_id: str | None,
    paid_to_account_id: str | None,
) -> None:
    """Ensure explicit payment accounts belong to the payment company."""
    for account_id in (paid_from_account_id, paid_to_account_id):
        if not account_id:
            continue
        account = database.session.get(Accounts, account_id)
        if account is None or account.entity != company:
            raise ValueError("La cuenta GL del pago debe pertenecer a la compañía del documento.")

    if payment_type != "internal_transfer":
        return
    source_bank = database.session.get(BankAccount, bank_account_id) if bank_account_id else None
    target_bank = database.session.get(BankAccount, target_bank_account_id) if target_bank_account_id else None
    if source_bank and source_bank.gl_account_id != paid_from_account_id:
        raise ValueError("La cuenta GL de origen debe coincidir con la cuenta bancaria de origen.")
    if target_bank and target_bank.gl_account_id != paid_to_account_id:
        raise ValueError("La cuenta GL destino debe coincidir con la cuenta bancaria destino.")


def _parse_reference_date(reference_date_raw: str | None) -> date | None:
    """Parse reference date from ISO string."""
    if reference_date_raw:
        return date.fromisoformat(reference_date_raw)
    return None


def _get_payment_currency(bank_account_id: str | None) -> str:
    """Get payment currency from bank account."""
    bank_account = database.session.get(BankAccount, bank_account_id) if bank_account_id else None
    payment_currency = bank_account.currency if bank_account else None
    if not payment_currency:
        raise ValueError(_("La cuenta bancaria seleccionada no tiene moneda configurada."))
    return payment_currency


def _payment_base_currency(company: str | None) -> str | None:
    """Return the company functional currency snapshot for a payment."""
    if not company:
        return None
    company_entity = (
        database.session.execute(database.select(Entity).filter(Entity.code == company)).scalars().first() if company else None
    )
    return str(company_entity.currency) if company_entity and company_entity.currency else None


def _create_payment_entry(
    payload: PaymentPayload,
    payment_type: str,
    company: str | None,
    bank_account_id: str | None,
    target_bank_account_id: str | None,
    amount: Decimal,
    payment_currency: str,
    reference_date: date | None,
    mode_of_payment: str,
    paid_from_account_id: str | None,
    paid_to_account_id: str | None,
    exchange_rate: Decimal | None = None,
    base_currency: str | None = None,
) -> PaymentEntry:
    """Create a PaymentEntry object from payload data."""
    return PaymentEntry(
        payment_type=payment_type,
        company=company,
        bank_account_id=bank_account_id,
        target_bank_account_id=target_bank_account_id,
        currency=payment_currency,
        transaction_currency=payment_currency,
        base_currency=base_currency,
        exchange_rate=exchange_rate,
        paid_amount=amount if payment_type in ("pay", "debit_note", "internal_transfer") else Decimal("0"),
        received_amount=amount if payment_type in ("receive", "credit_note", "internal_transfer") else Decimal("0"),
        unallocated_amount=amount,
        party_type=cast(str | None, payload.get("party_type")),
        party_id=cast(str | None, payload.get("party_id")),
        party_name=cast(str | None, payload.get("party_name")),
        paid_from_account_id=paid_from_account_id,
        paid_to_account_id=paid_to_account_id,
        cost_center_code=cast(str | None, payload.get("cost_center_code")),
        unit_code=cast(str | None, payload.get("unit_code")),
        project_code=cast(str | None, payload.get("project_code")),
        reference_no=cast(str | None, payload.get("reference_no")),
        reference_date=reference_date,
        mode_of_payment=mode_of_payment,
        remarks=cast(str | None, payload.get("remarks")),
        docstatus=0,
    )


def _update_payment_amounts(payment: PaymentEntry, payment_type: str, amount: Decimal) -> None:
    """Update payment amounts based on payment type and exchange rate."""
    rate = payment.exchange_rate if payment.exchange_rate else Decimal("1")
    if payment_type in ("pay", "debit_note", "internal_transfer"):
        payment.paid_amount = amount
        payment.base_paid_amount = (amount * rate).quantize(Decimal("0.0001"))
    if payment_type in ("receive", "credit_note", "internal_transfer"):
        payment.received_amount = amount
        payment.base_received_amount = (amount * rate).quantize(Decimal("0.0001"))


def _payment_identifier_inputs(
    *,
    payload: dict[str, object | None],
    mode_of_payment: str,
    default_series_id: str | None,
    default_counter_id: str | None,
) -> tuple[str | None, str | None]:
    """Resolve numbering inputs for the payment identifier."""
    naming_series_id = cast(str | None, payload.get("naming_series_id") or default_series_id)
    external_counter_id = None
    if mode_of_payment == "check":
        external_counter_id = cast(str | None, payload.get("external_counter_id") or default_counter_id)
    return naming_series_id, external_counter_id


def _payment_identifier_context(payment: PaymentEntry, mode_of_payment: str) -> dict[str, str]:
    """Build the external context for payment numbering."""
    context = {
        "payment_type": payment.payment_type,
        "mode_of_payment": mode_of_payment,
    }
    if mode_of_payment == "check":
        context["bank_account_id"] = str(payment.bank_account_id or "")
    return context


def _validate_payment_reference_totals(
    amount: Decimal, ref_totals: dict[str, Decimal], withholding_total: Decimal = Decimal("0")
) -> None:
    """Validate the totals assigned to payment references."""
    allocated = ref_totals["allocated"]
    payment_amount = ref_totals.get("payment_amount", allocated)
    if payment_amount > amount + withholding_total + Decimal("0.0001"):
        raise ValueError(_("El monto aplicado no puede ser mayor al monto total del pago."))


def _allows_fully_withheld_payment(payload: PaymentPayload, amount: Decimal) -> bool:
    """Allow zero cash only for a pay/receive entry settling a reference."""
    if amount != 0 or payload.get("payment_type") not in {"pay", "receive"}:
        return False
    return any(Decimal(str(line.get("allocated_amount") or "0")) > 0 for line in payload.get("lines") or [])


def _payment_withholding_total(payment_id: str) -> Decimal:
    """Return the canonical withholding total persisted for a payment."""
    return sum(
        (
            Decimal(str(line.amount or "0"))
            for line in load_document_fiscal_lines("payment_entry", payment_id)
            if line.tax_type == "withholding"
        ),
        Decimal("0"),
    )


def _payment_source_rows_from_request() -> list[dict[str, object]]:
    """Load payment source rows from the current request."""
    return _payment_source_rows(
        request.values.getlist("from_purchase_invoice"),
        request.values.getlist("from_sales_invoice"),
        request.values.getlist("from_purchase_order"),
        request.values.getlist("from_sales_order"),
        request.values.getlist("from_purchase_credit_note"),
        request.values.getlist("from_purchase_debit_note"),
        request.values.getlist("from_sales_credit_note"),
        request.values.getlist("from_sales_debit_note"),
    )


def _apply_payment_cancellation_hooks(payment: PaymentEntry) -> None:
    """Revert payment relations and bank reconciliation links atomically."""
    payment.unallocated_amount = Decimal("0")
    revert_relations_for_target("payment_entry", payment.id, reason="payment_cancelled")
    linked_transactions = (
        database.session.execute(database.select(BankTransaction).filter_by(payment_entry_id=payment.id)).scalars().all()
    )
    for transaction in linked_transactions:
        transaction.is_reconciled = False
        transaction.payment_entry_id = None
    database.session.execute(
        database.update(ReconciliationItem)
        .where(
            ReconciliationItem.target_type == "payment_entry",
            ReconciliationItem.target_id == payment.id,
            ReconciliationItem.status != "cancelled",
        )
        .values(status="cancelled")
    )
    references = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment.id)).scalars().all()
    affected_docs = {
        (reference.flow_source_type or reference.reference_type, reference.reference_id)
        for reference in references
        if (reference.flow_source_type or reference.reference_type) and reference.reference_id
    }
    for reference_type, reference_id in affected_docs:
        _refresh_payment_reference_document(reference_type, reference_id)
