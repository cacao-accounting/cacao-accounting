# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Caja y Bancos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date
from decimal import Decimal
import json
from typing import Any, TypedDict, cast

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    BankReconciliationMatch,
    BankReconciliationRequest,
    find_bank_reconciliation_candidates,
    reconcile_bank_items,
)
from cacao_accounting.bancos.statement_service import (
    BankStatementError,
    apply_bank_matching_rule,
    import_bank_statement,
)
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    BankMatchingRule,
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
    ReconciliationItem,
    SalesOrder,
    SalesInvoice,
    SeriesExternalCounterMap,
    User,
    database,
)
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, _lookup_exchange_rate, cancel_document, submit_document
from cacao_accounting.document_flow import create_document_relation, revert_relations_for_target
from cacao_accounting.document_flow.service import apply_payment_reconciliation
from cacao_accounting.document_flow.registry import normalize_doctype
from cacao_accounting.document_flow.service import compute_outstanding_amount, refresh_outstanding_amount_cache
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.fiscal_persistence_service import persist_document_fiscal_snapshot
from cacao_accounting.list_filters import apply_list_filters
from cacao_accounting.version import APPNAME
from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_create, log_submit

bancos = Blueprint("bancos", __name__, template_folder="templates")

BANCOS_TRANSACCION_LISTA_HTML = "bancos/transaccion_lista.html"
BANCOS_BANCO_CUENTA_NUEVO_HTML = "bancos/banco_cuenta_nuevo.html"
BANCOS_PAGO_LISTA_HTML = "bancos/pago_lista.html"
BANCOS_BANCOS_PAGO = "bancos.bancos_pago"
COMPRAS_FACTURA_COMPRA_ROUTE = "compras.compras_factura_compra"
VENTAS_FACTURA_VENTA_ROUTE = "ventas.ventas_factura_venta"
LABEL_FACTURA_COMPRA = "Factura de Compra"
LABEL_FACTURA_VENTA = "Factura de Venta"


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


def _paginate_list(model, search_fields, query=None, *, include_status: bool = True):
    """Pagina un listado aplicando los filtros GET comunes."""
    base_query = query if query is not None else database.select(model)
    filtered_query = apply_list_filters(base_query, model, search_fields, include_status=include_status)
    return database.paginate(
        filtered_query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )


@bancos.route("/")
@bancos.route("/caja")
@bancos.route("/tesoreria")
@bancos.route("/bancos")
@bancos.route("/cash")
@modulo_activo("cash")
@login_required
def bancos_():
    """Pantalla principal del modulo de bancos."""
    return render_template("bancos.html")


@bancos.route("/bank/list")
@modulo_activo("cash")
@login_required
def bancos_banco_lista():
    """Listado de bancos."""
    consulta = _paginate_list(
        Bank,
        (Bank.name, Bank.swift_code),
        include_status=False,
    )
    titulo = "Listado de Bancos - " + APPNAME
    return render_template("bancos/banco_lista.html", consulta=consulta, titulo=titulo)


@bancos.route("/bank-account/list")
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria_lista():
    """Listado de cuentas bancarias."""
    consulta = _paginate_list(
        BankAccount,
        (BankAccount.account_name, BankAccount.account_no, BankAccount.iban, BankAccount.company, BankAccount.currency),
        include_status=False,
    )
    titulo = "Listado de Cuentas Bancarias - " + APPNAME
    return render_template("bancos/banco_cuenta_lista.html", consulta=consulta, titulo=titulo)


@bancos.route("/payment/list")
@modulo_activo("cash")
@login_required
def bancos_pago_lista():
    """Listado de entradas de pago."""
    consulta = _paginate_list(
        PaymentEntry,
        (PaymentEntry.document_no, PaymentEntry.party_name, PaymentEntry.reference_no, PaymentEntry.remarks),
        database.select(PaymentEntry).filter(PaymentEntry.payment_type.in_(("receive", "pay"))),
    )
    titulo = "Listado de Pagos - " + APPNAME
    return render_template(BANCOS_PAGO_LISTA_HTML, consulta=consulta, titulo=titulo)


@bancos.route("/payment-reconciliation", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_conciliacion_facturas_pagos():
    """Interfaz dedicada para aplicar pagos existentes contra facturas."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        try:
            payload = json.loads(request.form.get("payment_reconciliation_payload") or "{}")
            allocation_date = date.fromisoformat(payload.get("allocation_date") or date.today().isoformat())
            reconciliation = apply_payment_reconciliation(
                company=str(payload.get("company") or ""),
                party_type=str(payload.get("party_type") or ""),
                party_id=str(payload.get("party_id") or ""),
                allocation_date=allocation_date,
                lines=list(payload.get("lines") or []),
            )
            database.session.commit()
            flash(_("Conciliación de facturas y pagos aplicada correctamente."), "success")
            return redirect(url_for("bancos.bancos_conciliacion_facturas_pagos", reconciliation_id=reconciliation.id))
        except ValueError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
        except Exception as exc:  # noqa: BLE001
            from cacao_accounting.document_flow import DocumentFlowError

            database.session.rollback()
            if isinstance(exc, DocumentFlowError):
                flash(str(exc), "danger")
            else:
                raise

    return render_template(
        "bancos/conciliacion_facturas_pagos.html",
        titulo="Conciliación Facturas/Pagos - " + APPNAME,
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/transfer/list")
@modulo_activo("cash")
@login_required
def bancos_transferencia_lista():
    """Listado de transferencias internas."""
    consulta = _paginate_list(
        PaymentEntry,
        (PaymentEntry.document_no, PaymentEntry.party_name, PaymentEntry.reference_no, PaymentEntry.remarks),
        database.select(PaymentEntry).filter_by(payment_type="internal_transfer"),
    )
    titulo = "Listado de Transferencias Internas - " + APPNAME
    return render_template(BANCOS_PAGO_LISTA_HTML, consulta=consulta, titulo=titulo, is_transfer_list=True)


@bancos.route("/payment/debit-note/list")
@modulo_activo("cash")
@login_required
def bancos_nota_debito_lista():
    """Listado de notas de débito bancario (retiros)."""
    consulta = _paginate_list(
        PaymentEntry,
        (PaymentEntry.document_no, PaymentEntry.party_name, PaymentEntry.reference_no, PaymentEntry.remarks),
        database.select(PaymentEntry).filter_by(payment_type="debit_note"),
    )
    titulo = "Listado de Notas de Débito Bancario - " + APPNAME
    return render_template(
        BANCOS_PAGO_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        page_heading=_("Listado de Notas de Débito Bancario"),
        new_url=url_for("bancos.bancos_nota_debito_nueva"),
    )


@bancos.route("/payment/credit-note/list")
@modulo_activo("cash")
@login_required
def bancos_nota_credito_lista():
    """Listado de notas de crédito bancario (depósitos)."""
    consulta = _paginate_list(
        PaymentEntry,
        (PaymentEntry.document_no, PaymentEntry.party_name, PaymentEntry.reference_no, PaymentEntry.remarks),
        database.select(PaymentEntry).filter_by(payment_type="credit_note"),
    )
    titulo = "Listado de Notas de Crédito Bancario - " + APPNAME
    return render_template(
        BANCOS_PAGO_LISTA_HTML,
        consulta=consulta,
        titulo=titulo,
        page_heading=_("Listado de Notas de Crédito Bancario"),
        new_url=url_for("bancos.bancos_nota_credito_nueva"),
    )


@bancos.route("/bank-transaction/list")
@modulo_activo("cash")
@login_required
def bancos_transaccion_lista():
    """Listado de transacciones bancarias."""
    consulta = _paginate_list(
        BankTransaction,
        (BankTransaction.description, BankTransaction.reference_number),
        include_status=False,
    )
    titulo = "Listado de Transacciones Bancarias - " + APPNAME
    return render_template(BANCOS_TRANSACCION_LISTA_HTML, consulta=consulta, titulo=titulo)


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


@bancos.route("/bank-transaction/reconcile", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_transaccion_reconciliar():
    """Marca transacciones bancarias seleccionadas como conciliadas."""
    transaction_ids = request.form.getlist("transaction_id")
    if not transaction_ids:
        abort(400)

    transactions = (
        database.session.execute(database.select(BankTransaction).filter(BankTransaction.id.in_(transaction_ids)))
        .scalars()
        .all()
    )
    if not transactions:
        abort(404)
    if any(transaction.is_reconciled for transaction in transactions):
        abort(409)

    company = None
    for transaction in transactions:
        bank_account = database.session.get(BankAccount, transaction.bank_account_id)
        if not bank_account:
            abort(404)
        if company is None:
            company = bank_account.company
        elif bank_account.company != company:
            abort(409)
        duplicated_item = database.session.execute(
            database.select(ReconciliationItem.id)
            .filter_by(reference_type="bank_transaction", reference_id=transaction.id)
            .limit(1)
        ).scalar_one_or_none()
        if duplicated_item:
            abort(409)

    try:
        reconcile_bank_items(
            BankReconciliationRequest(
                company=str(company),
                reconciliation_date=date.today(),
                matches=[
                    BankReconciliationMatch(
                        bank_transaction_id=transaction.id,
                        target_type="gl_entry",
                        target_id=str(request.form.get(f"target_id_{transaction.id}") or ""),
                        allocated_amount=_bank_reconciliation_allocated_amount(transaction),
                    )
                    for transaction in transactions
                    if request.form.get(f"target_id_{transaction.id}")
                ],
            )
        )
    except BankReconciliationError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("bancos.bancos_conciliacion_bancaria"))

    database.session.commit()
    flash(_("Transacciones bancarias conciliadas correctamente."), "success")
    return redirect(url_for("bancos.bancos_transaccion_lista"))


def _bank_reconciliation_allocated_amount(transaction: BankTransaction) -> Decimal | None:
    """Get the amount allocated for a bank reconciliation match."""
    if transaction.deposit is not None:
        return transaction.deposit
    return transaction.withdrawal


@bancos.route("/bank-reconciliation")
@modulo_activo("cash")
@login_required
def bancos_conciliacion_bancaria():
    """Panel de conciliacion bancaria con transacciones pendientes."""
    company = request.args.get("company") or None
    query = database.select(BankTransaction).filter_by(is_reconciled=False)
    if company:
        query = query.join(BankAccount, BankAccount.id == BankTransaction.bank_account_id).filter(
            BankAccount.company == company
        )
    transactions = database.session.execute(query.order_by(BankTransaction.posting_date)).scalars().all()
    suggestions = {transaction.id: find_bank_reconciliation_candidates(transaction.id) for transaction in transactions}
    return render_template(
        "bancos/conciliacion_bancaria.html",
        titulo="Conciliación Bancaria - " + APPNAME,
        transactions=transactions,
        suggestions=suggestions,
        company=company,
    )


@bancos.route("/bank-reconciliation/<bank_account_id>")
@modulo_activo("cash")
@login_required
def bancos_conciliacion_bancaria_cuenta(bank_account_id: str):
    """Panel de conciliacion bancaria filtrado por cuenta."""
    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        abort(404)
    transactions = (
        database.session.execute(
            database.select(BankTransaction)
            .filter_by(bank_account_id=bank_account_id, is_reconciled=False)
            .order_by(BankTransaction.posting_date)
        )
        .scalars()
        .all()
    )
    suggestions = {transaction.id: find_bank_reconciliation_candidates(transaction.id) for transaction in transactions}
    return render_template(
        "bancos/conciliacion_bancaria.html",
        titulo="Conciliación Bancaria - " + APPNAME,
        transactions=transactions,
        suggestions=suggestions,
        company=bank_account.company,
    )


@bancos.route("/bank-reconciliation/apply", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_conciliacion_bancaria_aplicar() -> ResponseReturnValue:
    """Aplica conciliaciones bancarias seleccionadas."""
    company = request.form.get("company") or "cacao"
    matches: list[BankReconciliationMatch] = []
    for transaction_id in request.form.getlist("bank_transaction_id"):
        target = request.form.get(f"target_{transaction_id}") or ""
        amount = _form_decimal(f"amount_{transaction_id}")
        if not target or amount <= 0:
            continue
        target_type, target_id = target.split(":", 1)
        matches.append(
            BankReconciliationMatch(
                bank_transaction_id=transaction_id,
                target_type=target_type,
                target_id=target_id,
                allocated_amount=amount,
            )
        )
    try:
        reconcile_bank_items(BankReconciliationRequest(company=company, reconciliation_date=date.today(), matches=matches))
        database.session.commit()
        flash(_("Conciliación bancaria aplicada correctamente."), "success")
    except BankReconciliationError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for("bancos.bancos_conciliacion_bancaria", company=company))


@bancos.route("/bank-statement/import", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_extracto_importar():
    """Importa extractos bancarios CSV con preview."""
    accounts = (
        database.session.execute(database.select(BankAccount).filter_by(is_active=True).order_by(BankAccount.account_name))
        .scalars()
        .all()
    )
    result = None
    if request.method == "POST":
        mapping = {
            "date": request.form.get("date_column") or "date",
            "reference": request.form.get("reference_column") or "reference",
            "description": request.form.get("description_column") or "description",
            "deposit": request.form.get("deposit_column") or "deposit",
            "withdrawal": request.form.get("withdrawal_column") or "withdrawal",
        }
        try:
            result = import_bank_statement(
                request.files["statement_file"],
                mapping,
                request.form.get("bank_account_id") or "",
                preview=request.form.get("action") == "preview",
            )
            if request.form.get("action") == "import":
                database.session.commit()
                flash(_("Extracto importado correctamente."), "success")
                return redirect(url_for("bancos.bancos_transaccion_lista"))
        except (BankStatementError, KeyError) as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
    return render_template(
        "bancos/extracto_importar.html", accounts=accounts, result=result, titulo=_("Importar Extracto Bancario")
    )


@bancos.route("/bank-matching-rules", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_reglas_matching():
    """Administra reglas de matching bancario."""
    accounts = (
        database.session.execute(database.select(BankAccount).filter_by(is_active=True).order_by(BankAccount.account_name))
        .scalars()
        .all()
    )
    if request.method == "POST":
        rule = BankMatchingRule(
            company=request.form.get("company") or "",
            bank_account_id=request.form.get("bank_account_id") or None,
            name=request.form.get("name") or "",
            days_tolerance=int(request.form.get("days_tolerance") or 7),
            amount_tolerance=Decimal(request.form.get("amount_tolerance") or "0"),
            reference_contains=request.form.get("reference_contains") or None,
            priority=int(request.form.get("priority") or 100),
            is_active=bool(request.form.get("is_active", "1")),
        )
        database.session.add(rule)
        database.session.commit()
        flash(_("Regla de matching creada correctamente."), "success")
        return redirect(url_for("bancos.bancos_reglas_matching"))
    rules = database.session.execute(database.select(BankMatchingRule).order_by(BankMatchingRule.priority)).scalars().all()
    return render_template(
        "bancos/reglas_matching.html", accounts=accounts, rules=rules, titulo=_("Reglas de Matching Bancario")
    )


@bancos.route("/bank-matching-rules/<rule_id>/run", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_regla_matching_ejecutar(rule_id: str):
    """Ejecuta una regla de matching para una cuenta y rango."""
    try:
        date_from = date.fromisoformat(request.form.get("date_from") or date.today().isoformat())
        date_to = date.fromisoformat(request.form.get("date_to") or date.today().isoformat())
        result = apply_bank_matching_rule(rule_id, request.form.get("bank_account_id") or "", (date_from, date_to))
        flash(
            _("Regla ejecutada: {count} transacciones evaluadas.").format(count=len(result.candidates_by_transaction)),
            "success",
        )
    except BankStatementError as exc:
        flash(_(str(exc)), "danger")
    return redirect(url_for("bancos.bancos_reglas_matching"))


@bancos.route("/payment/debit-note/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_nota_debito_nueva():
    """Formulario de nota de débito bancaria (utiliza PaymentEntry)."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        return bancos_pago_nuevo()

    return render_template(
        "bancos/nota_nueva.html",
        titulo=_("Nueva Nota de Débito Bancario") + " - " + APPNAME,
        payment_type="debit_note",
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/payment/credit-note/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_nota_credito_nueva():
    """Formulario de nota de crédito bancaria (utiliza PaymentEntry)."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        return bancos_pago_nuevo()

    return render_template(
        "bancos/nota_nueva.html",
        titulo=_("Nueva Nota de Crédito Bancario") + " - " + APPNAME,
        payment_type="credit_note",
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/payment/transfer/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_transferencia_nueva():
    """Formulario de transferencia entre cuentas bancarias."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        return bancos_pago_nuevo()

    return render_template(
        "bancos/transferencia_nueva.html",
        titulo=_("Nueva Transferencia Bancaria") + " - " + APPNAME,
        payment_type="internal_transfer",
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/bank/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_banco_nuevo():
    """Formulario para crear un nuevo banco."""
    from cacao_accounting.bancos.forms import FormularioBanco

    formulario = FormularioBanco()
    titulo = "Nuevo Banco - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        banco = Bank(
            name=request.form.get("name"),
            swift_code=request.form.get("swift_code"),
        )
        database.session.add(banco)
        database.session.commit()
        return redirect("/cash_management/bank/list")
    return render_template("bancos/banco_nuevo.html", form=formulario, titulo=titulo)


@bancos.route("/bank/<bank_id>")
@modulo_activo("cash")
@login_required
def bancos_banco(bank_id):
    """Detalle de banco."""
    from flask import abort

    registro = database.session.get(Bank, bank_id)
    if not registro:
        abort(404)
    titulo = registro.name + " - " + APPNAME
    return render_template("bancos/banco.html", registro=registro, titulo=titulo)


@bancos.route("/bank-account/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria_nuevo():
    """Formulario para crear una nueva cuenta bancaria."""
    from cacao_accounting.bancos.forms import FormularioCuentaBancaria
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial, obtener_lista_monedas

    formulario = FormularioCuentaBancaria()
    formulario.bank_id.choices = [(b[0].id, b[0].name) for b in database.session.execute(database.select(Bank)).all()]
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.currency.choices = [("", "")] + obtener_lista_monedas()
    titulo = "Nueva Cuenta Bancaria - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        gl_account_id = request.form.get("gl_account_id") or None
        company = request.form.get("company")
        default_naming_series_id = request.form.get("default_naming_series_id") or None
        default_external_counter_id = request.form.get("default_external_counter_id") or None
        if gl_account_id:
            gl_account = database.session.get(Accounts, gl_account_id)
            if not gl_account or gl_account.entity != company or gl_account.account_type != "bank":
                flash(_("Seleccione una cuenta contable de tipo banco para la compañía indicada."), "danger")
                return render_template(BANCOS_BANCO_CUENTA_NUEVO_HTML, form=formulario, titulo=titulo)
        try:
            default_naming_series_id, default_external_counter_id = _validate_bank_account_numbering_defaults(
                company=company,
                naming_series_id=default_naming_series_id,
                external_counter_id=default_external_counter_id,
            )
        except IdentifierConfigurationError as exc:
            flash(_(str(exc)), "danger")
            return render_template(BANCOS_BANCO_CUENTA_NUEVO_HTML, form=formulario, titulo=titulo)
        cuenta = BankAccount(
            bank_id=request.form.get("bank_id"),
            company=company,
            account_name=request.form.get("account_name"),
            account_no=request.form.get("account_no"),
            iban=request.form.get("iban"),
            currency=request.form.get("currency") or None,
            gl_account_id=gl_account_id,
            default_naming_series_id=default_naming_series_id,
            default_external_counter_id=default_external_counter_id,
        )
        database.session.add(cuenta)
        database.session.flush()
        _ensure_bank_account_counter_mapping(cuenta)
        database.session.commit()
        return redirect("/cash_management/bank-account/list")
    return render_template(BANCOS_BANCO_CUENTA_NUEVO_HTML, form=formulario, titulo=titulo)


@bancos.route("/bank-account/<account_id>")
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria(account_id):
    """Detalle de cuenta bancaria."""
    from flask import abort

    registro = database.session.get(BankAccount, account_id)
    if not registro:
        abort(404)
    titulo = registro.account_name + " - " + APPNAME
    return render_template("bancos/banco_cuenta.html", registro=registro, titulo=titulo)


def _form_decimal(field_name: str, default: str = "0") -> Decimal:
    """Convierte un valor de formulario a Decimal."""
    value = request.form.get(field_name)
    return Decimal(str(value if value not in (None, "") else default))


def _invoice_outstanding(invoice) -> Decimal:
    """Devuelve el saldo vivo calculado de una factura."""
    computed = compute_outstanding_amount(invoice)
    cached_values = []
    for attr in ("outstanding_amount", "base_outstanding_amount"):
        raw = getattr(invoice, attr, None)
        if raw is None:
            continue
        value = Decimal(str(raw))
        if value >= 0:
            cached_values.append(value)
    if not cached_values:
        return computed
    return min([computed, *cached_values])


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
    document = database.session.query(model).with_for_update().get(reference_id)
    if not document:
        raise ValueError(_("Documento referenciado no existe."))
    return document


def _validate_payment_reference_document(
    *,
    payment: PaymentEntry,
    document: Any,
    flow_source_type: str,
) -> None:
    """Valida compañía, tercero y estado del documento referenciado."""
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
        currency=getattr(document, "currency", None) or getattr(payment, "currency", None),
        total_amount=document.grand_total,
        outstanding_amount=outstanding,
        outstanding_amount_after=outstanding_after,
        allocated_amount=allocated,
        exchange_rate=Decimal(str(line.get("exchange_rate") or getattr(document, "exchange_rate", None) or 1)),
        difference_amount=difference_amount,
        allocation_date=payment.posting_date,
        discount_amount=discount_amount,
        gain_loss_amount=gain_loss_amount,
        notes=line.get("notes"),
    )


def _validate_payment_reference_line(
    *,
    payment: PaymentEntry,
    line: dict,
    allow_order_references: bool,
) -> tuple[str, str, str, Decimal, Decimal]:
    """Valida una línea de referencia y devuelve sus valores normalizados."""
    reference_type = line.get("reference_type", "")
    reference_id = line.get("reference_id", "")
    allocated = Decimal(str(line.get("allocated_amount", "0")))
    requested_flow_source_type = str(line.get("flow_source_type") or reference_type)
    reference_key = (normalize_doctype(requested_flow_source_type), reference_id)
    if reference_key in _validate_payment_reference_line.processed_keys:  # type: ignore[attr-defined]
        from werkzeug.exceptions import Conflict

        raise Conflict(_("No se puede aplicar la misma factura dos veces en un pago."))
    _validate_payment_reference_line.processed_keys.add(reference_key)  # type: ignore[attr-defined]
    if allocated <= 0:
        if allocated < 0:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("El monto asignado no puede ser negativo."))
        return reference_type, reference_id, requested_flow_source_type, allocated, Decimal("0")
    if normalize_doctype(requested_flow_source_type) in ("purchase_order", "sales_order") and not allow_order_references:
        raise ValueError(_("Las órdenes solo pueden referenciarse en flujo de anticipo."))
    return reference_type, reference_id, requested_flow_source_type, allocated, allocated


_validate_payment_reference_line.processed_keys = set()  # type: ignore[attr-defined]


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
    if explicit:
        return normalize_doctype(explicit)
    return normalize_doctype(str(getattr(document, "document_type", None) or reference_type))


def _physical_reference_type(reference_type: str, flow_source_type: str) -> str:
    """Normaliza el tipo físico que apunta a la tabla real referenciada."""
    source_key = normalize_doctype(flow_source_type or reference_type)
    if source_key in {"purchase_credit_note", "purchase_debit_note"}:
        return "purchase_invoice"
    if source_key in {"sales_credit_note", "sales_debit_note"}:
        return "sales_invoice"
    return normalize_doctype(reference_type)


def _order_outstanding(order: PurchaseOrder | SalesOrder, source_type: str) -> Decimal:
    """Calcula el monto de anticipo aún disponible para una orden."""
    rows = database.session.execute(
        database.select(PaymentReference.allocated_amount)
        .join(DocumentRelation, DocumentRelation.target_item_id == PaymentReference.id)
        .where(
            DocumentRelation.source_type == source_type,
            DocumentRelation.source_id == order.id,
            DocumentRelation.target_type == "payment_entry",
            DocumentRelation.status == "active",
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
) -> None:
    """Validate the required Payment Entry header fields."""
    _validate_payment_header_required_fields(
        company=company,
        bank_account_id=bank_account_id,
        posting_date_raw=posting_date_raw,
        amount=amount,
    )
    validated_company = cast(str, company)
    validated_bank_account_id = cast(str, bank_account_id)
    _validate_payment_bank_account(company=validated_company, bank_account_id=validated_bank_account_id)
    _validate_payment_target_bank_account(company=validated_company, target_bank_account_id=target_bank_account_id)
    _validate_payment_party(payment_type=payment_type, party_type=party_type, party_id=party_id)


def _validate_payment_header_required_fields(
    *,
    company: str | None,
    bank_account_id: str | None,
    posting_date_raw: str | None,
    amount: Decimal,
) -> None:
    """Validate the required payment header fields that are independent."""
    if not company:
        raise ValueError(_("La compañía es obligatoria."))
    if not bank_account_id:
        raise ValueError(_("La cuenta bancaria es obligatoria."))
    if not posting_date_raw:
        raise ValueError(_("La fecha del pago es obligatoria."))
    if amount <= 0:
        raise ValueError(_("El monto del pago debe ser mayor que cero."))


def _validate_payment_bank_account(*, company: str, bank_account_id: str) -> None:
    """Validate that the payment bank account exists and belongs to the company."""
    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        raise ValueError(_("La cuenta bancaria seleccionada no existe."))
    if bank_account.company != company:
        raise ValueError(_("La cuenta bancaria no pertenece a la misma compañía del pago."))


def _validate_payment_target_bank_account(*, company: str, target_bank_account_id: str | None) -> None:
    """Validate that the target bank account exists and belongs to the company."""
    if not target_bank_account_id:
        return
    target_bank_account = database.session.get(BankAccount, target_bank_account_id)
    if not target_bank_account:
        raise ValueError(_("La cuenta bancaria destino no existe."))
    if target_bank_account.company != company:
        raise ValueError(_("La cuenta bancaria destino no pertenece a la misma compañía del pago."))


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
    _reset_payment_reference_line_cache()
    for line in lines:
        totals = _process_payment_reference_line(
            payment=payment,
            line=line,
            totals=totals,
            allow_order_references=allow_order_references,
        )
    return totals


def _payment_reference_totals() -> dict[str, Decimal]:
    """Inicializa el acumulador de totales de referencias de pago."""
    return {
        "allocated": Decimal("0"),
        "discount": Decimal("0"),
        "gain_loss": Decimal("0"),
    }


def _reset_payment_reference_line_cache() -> None:
    """Reinicia el cache de validación de líneas de referencias de pago."""
    _validate_payment_reference_line.processed_keys = set()  # type: ignore[attr-defined]


def _process_payment_reference_line(
    *,
    payment: PaymentEntry,
    line: dict,
    totals: dict[str, Decimal],
    allow_order_references: bool,
) -> dict[str, Decimal]:
    """Valida una línea de referencia y la aplica cuando corresponde."""
    reference_type, reference_id, requested_flow_source_type, allocated, applied_amount = _validate_payment_reference_line(
        payment=payment,
        line=line,
        allow_order_references=allow_order_references,
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
        document.base_outstanding_amount = document.outstanding_amount
    totals["allocated"] += allocated
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


@bancos.route("/payment/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_nuevo():
    """Formulario para crear un nuevo pago."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    if request.method == "POST":
        response = _create_payment_from_request()
        if response is not None:
            return response

    source_rows = _payment_source_rows_from_request()

    initial_payment = {}
    if source_rows:
        first_row = source_rows[0]
        first = first_row["document"]
        first_flow_source_type = first_row.get("flow_source_type", first_row["reference_type"])
        party_type, payment_type = _payment_profile_from_source_type(first_flow_source_type)
        initial_amount = Decimal("0")
        lines: list[dict] = []
        for row in source_rows:
            document = row["document"]
            flow_source_type = row.get("flow_source_type", row["reference_type"])
            outstanding = _reference_outstanding(document, flow_source_type)
            initial_amount += outstanding
            reference_date_value = _payment_reference_date(document)
            lines.append(
                {
                    "reference_type": row["reference_type"],
                    "flow_source_type": flow_source_type,
                    "reference_id": document.id,
                    "document_no": document.document_no or document.id,
                    "reference_date": reference_date_value.isoformat() if reference_date_value else "",
                    "currency": getattr(document, "currency", None) or "",
                    "reference_label": row.get("label", ""),
                    "total_amount": float(document.grand_total or 0),
                    "outstanding_amount": float(outstanding),
                    "allocated_amount": float(outstanding),
                }
            )

        initial_payment = {
            "company": first.company,
            "party_id": getattr(first, "supplier_id", None) or getattr(first, "customer_id", None),
            "party_type": party_type,
            "payment_type": payment_type,
            "currency": getattr(first, "currency", None) or "",
            "paid_amount": float(initial_amount),
            "lines": lines,
            "advance_mode": any(row["reference_type"] in ("purchase_order", "sales_order") for row in source_rows),
        }

    transaction_config = {
        "columns": get_column_preferences(getattr(current_user, "id", None), "banking.payment_entry"),
    }

    return render_template(
        "bancos/pago_nuevo.html",
        titulo="Nuevo Pago - " + APPNAME,
        initial_payment=initial_payment,
        transaction_config=transaction_config,
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


def _create_payment_from_request():
    """Create a payment from the submitted request payload."""
    try:
        payload = _payment_payload_from_request()
        payment, amount, mode_of_payment = _build_payment_from_payload(payload)
        default_series_id, default_counter_id = _payment_numbering_defaults(payment.bank_account_id)
        naming_series_id, external_counter_id = _payment_identifier_inputs(
            payload=payload,
            mode_of_payment=mode_of_payment,
            default_series_id=default_series_id,
            default_counter_id=default_counter_id,
        )
        assign_document_identifier(
            document=payment,
            entity_type="payment_entry",
            posting_date_raw=payload.get("posting_date"),
            naming_series_id=naming_series_id,
            external_counter_id=external_counter_id,
            external_number=None,
            external_context=_payment_identifier_context(payment, mode_of_payment),
        )
        ref_totals = _save_payment_references(
            payment,
            payload.get("lines") or [],
            allow_order_references=bool(payload.get("advance_mode")),
        )
        _validate_payment_reference_totals(amount, ref_totals)
        persist_document_fiscal_snapshot(
            company=str(payment.company or ""),
            document_type="payment_entry",
            document_id=payment.id,
            currency=payment.currency,
            tax_lines=payload.get("tax_lines"),
            tax_summary=payload.get("tax_summary"),
        )
        log_create(payment)
        database.session.commit()
        flash(_("Pago registrado correctamente."), "success")
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment.id))
    except (ValueError, ArithmeticError) as exc:
        database.session.rollback()
        flash(str(exc), "danger")
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
    )

    paid_from_account_id, paid_to_account_id = _resolve_gl_accounts(
        payload, payment_type, bank_account_id, target_bank_account_id
    )
    reference_date = _parse_reference_date(payload.get("reference_date"))
    payment_currency = _get_payment_currency(bank_account_id)
    mode_of_payment = str(payload.get("mode_of_payment") or "").strip().lower()

    company_entity = database.session.get(Entity, company) if company else None
    company_currency = company_entity.currency if company_entity else None
    posting_date_raw = payload.get("posting_date")
    if company_currency and payment_currency != company_currency and posting_date_raw:
        exchange_rate = _lookup_exchange_rate(payment_currency, company_currency, posting_date_raw)
    else:
        exchange_rate = Decimal("1")

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
    )
    _update_payment_amounts(payment, payment_type, amount)
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
) -> PaymentEntry:
    """Create a PaymentEntry object from payload data."""
    return PaymentEntry(
        payment_type=payment_type,
        company=company,
        bank_account_id=bank_account_id,
        target_bank_account_id=target_bank_account_id,
        currency=payment_currency,
        transaction_currency=payment_currency,
        exchange_rate=exchange_rate,
        paid_amount=amount if payment_type in ("pay", "debit_note", "internal_transfer") else Decimal("0"),
        received_amount=amount if payment_type in ("receive", "credit_note", "internal_transfer") else Decimal("0"),
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


def _validate_payment_reference_totals(amount: Decimal, ref_totals: dict[str, Decimal]) -> None:
    """Validate the totals assigned to payment references."""
    allocated = ref_totals["allocated"]
    discount = ref_totals["discount"]
    gain_loss = ref_totals["gain_loss"]
    if (allocated - discount - gain_loss) > amount + Decimal("0.01"):
        raise ValueError(_("El monto aplicado no puede ser mayor al monto total del pago."))


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


@bancos.route("/payment/<payment_id>")
@modulo_activo("cash")
@login_required
def bancos_pago(payment_id):
    """Detalle de pago."""
    from flask import abort

    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)

    # Entradas contables
    lineas_gl = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment_id))
        .scalars()
        .all()
    )

    # Referencias (facturas aplicadas)
    referencias = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment_id)).scalars().all()

    # Nombres para mostrar
    banco = database.session.get(BankAccount, registro.bank_account_id) if registro.bank_account_id else None
    banco_destino = None
    if registro.payment_type == "internal_transfer" and registro.paid_to_account_id:
        banco_destino = (
            database.session.execute(
                database.select(BankAccount).filter_by(company=registro.company, gl_account_id=registro.paid_to_account_id)
            )
            .scalars()
            .first()
        )

    creador = database.session.get(User, registro.created_by) if registro.created_by else None

    titulo = (registro.document_no or payment_id) + " - " + APPNAME
    return render_template(
        "bancos/pago.html",
        registro=registro,
        titulo=titulo,
        lineas_gl=lineas_gl,
        referencias=referencias,
        banco=banco,
        banco_destino=banco_destino,
        creador=creador,
        audit_timeline=format_document_timeline("payment_entry", registro.id),
    )


@bancos.route("/payment/<payment_id>/submit", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_submit(payment_id: str):
    """Aprueba y contabiliza un pago."""
    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        submit_document(registro)
        log_submit(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    flash(_("Pago aprobado y contabilizado."), "success")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))


@bancos.route("/payment/<payment_id>/cancel", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_cancel(payment_id: str):
    """Cancela un pago con reverso contable."""
    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    try:
        cancel_document(registro)
        revert_relations_for_target("payment_entry", registro.id, reason="payment_cancelled")
        references = (
            database.session.execute(database.select(PaymentReference).filter_by(payment_id=registro.id)).scalars().all()
        )
        affected_docs = {
            (ref.flow_source_type or ref.reference_type, ref.reference_id)
            for ref in references
            if (ref.flow_source_type or ref.reference_type) and ref.reference_id
        }
        for reference_type, reference_id in affected_docs:
            _refresh_payment_reference_document(reference_type, reference_id)
        log_cancel(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    flash(_("Pago cancelado con reverso contable."), "warning")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
