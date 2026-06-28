# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Caja y Bancos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date
from decimal import Decimal
import json
from typing import Any, cast

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
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, post_bank_transaction, submit_document
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
BANCOS_BANCOS_PAGO = "bancos.bancos_pago"
COMPRAS_FACTURA_COMPRA_ROUTE = "compras.compras_factura_compra"
VENTAS_FACTURA_VENTA_ROUTE = "ventas.ventas_factura_venta"
LABEL_FACTURA_COMPRA = "Factura de Compra"
LABEL_FACTURA_VENTA = "Factura de Venta"


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
    return render_template("bancos/pago_lista.html", consulta=consulta, titulo=titulo)


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
    return render_template("bancos/pago_lista.html", consulta=consulta, titulo=titulo, is_transfer_list=True)


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
        "bancos/pago_lista.html",
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
        "bancos/pago_lista.html",
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


def _crear_nota_bancaria(note_kind: str):
    """Crea una transacción bancaria manual como nota de débito/crédito."""
    company = request.form.get("company") or request.args.get("company") or None
    if request.method == "POST":
        amount = _form_decimal("amount")
        if amount <= 0:
            abort(409)
        bank_account_id = request.form.get("bank_account_id", "")
        bank_account = database.session.get(BankAccount, bank_account_id)
        if not bank_account:
            abort(400)
        if company and bank_account.company != company:
            abort(409)
        transaction = BankTransaction(
            bank_account_id=bank_account_id,
            posting_date=request.form.get("posting_date") or None,
            description=request.form.get("description") or None,
            reference_number=request.form.get("reference_number") or None,
            deposit=amount if note_kind == "credit" else None,
            withdrawal=amount if note_kind == "debit" else None,
        )
        database.session.add(transaction)
        database.session.flush()
        try:
            post_bank_transaction(transaction)
            database.session.commit()
            flash(_("Nota bancaria registrada correctamente y registrada en el libro mayor."), "success")
        except PostingError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
            if note_kind == "credit":
                return redirect(url_for("bancos.bancos_nota_credito_nueva"))
            return redirect(url_for("bancos.bancos_nota_debito_nueva"))
        list_view = "bancos.bancos_nota_credito_lista" if note_kind == "credit" else "bancos.bancos_nota_debito_lista"
        return redirect(url_for(list_view))
    cuentas_query = database.select(BankAccount).filter_by(is_active=True)
    if company:
        cuentas_query = cuentas_query.filter_by(company=company)
    cuentas = database.session.execute(cuentas_query).scalars().all()
    return render_template(
        "bancos/transaccion_nueva.html",
        titulo=("Nueva Nota de Crédito Bancario - " if note_kind == "credit" else "Nueva Nota de Débito Bancario - ")
        + APPNAME,
        note_kind=note_kind,
        cuentas=cuentas,
        company=company,
    )


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
                        allocated_amount=transaction.deposit if transaction.deposit is not None else transaction.withdrawal,
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
    rows = []
    for invoice_id in purchase_invoice_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(PurchaseInvoice, invoice_id),
            reference_type="purchase_invoice",
            label=LABEL_FACTURA_COMPRA,
            url_route=COMPRAS_FACTURA_COMPRA_ROUTE,
            url_param_name="invoice_id",
        )
    for invoice_id in sales_invoice_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(SalesInvoice, invoice_id),
            reference_type="sales_invoice",
            label=LABEL_FACTURA_VENTA,
            url_route=VENTAS_FACTURA_VENTA_ROUTE,
            url_param_name="invoice_id",
        )
    for order_id in purchase_order_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(PurchaseOrder, order_id),
            reference_type="purchase_order",
            label=_("Orden de Compra"),
            url_route="compras.compras_orden_compra",
            url_param_name="order_id",
        )
    for order_id in sales_order_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(SalesOrder, order_id),
            reference_type="sales_order",
            label=_("Orden de Venta"),
            url_route="ventas.ventas_orden_venta",
            url_param_name="order_id",
        )
    for invoice_id in purchase_credit_note_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(PurchaseInvoice, invoice_id),
            reference_type="purchase_invoice",
            label=_("Nota de Crédito de Compra"),
            url_route=COMPRAS_FACTURA_COMPRA_ROUTE,
            url_param_name="invoice_id",
            flow_source_type="purchase_credit_note",
            document_type="purchase_credit_note",
        )
    for invoice_id in purchase_debit_note_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(PurchaseInvoice, invoice_id),
            reference_type="purchase_invoice",
            label=_("Nota de Débito de Compra"),
            url_route=COMPRAS_FACTURA_COMPRA_ROUTE,
            url_param_name="invoice_id",
            flow_source_type="purchase_debit_note",
            document_type="purchase_debit_note",
        )
    for invoice_id in sales_credit_note_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(SalesInvoice, invoice_id),
            reference_type="sales_invoice",
            label=_("Nota de Crédito de Venta"),
            url_route=VENTAS_FACTURA_VENTA_ROUTE,
            url_param_name="invoice_id",
            flow_source_type="sales_credit_note",
            document_type="sales_credit_note",
        )
    for invoice_id in sales_debit_note_ids:
        _append_payment_source_row(
            rows,
            document=database.session.get(SalesInvoice, invoice_id),
            reference_type="sales_invoice",
            label=_("Nota de Débito de Venta"),
            url_route=VENTAS_FACTURA_VENTA_ROUTE,
            url_param_name="invoice_id",
            flow_source_type="sales_debit_note",
            document_type="sales_debit_note",
        )
    return rows


def _payment_profile_from_source_type(flow_source_type: str) -> tuple[str, str]:
    """Resuelve party_type/payment_type según el tipo documental origen."""
    mapping = {
        "purchase_invoice": ("supplier", "pay"),
        "sales_invoice": ("customer", "receive"),
        "purchase_order": ("supplier", "pay"),
        "sales_order": ("customer", "receive"),
        "purchase_credit_note": ("supplier", "receive"),
        "purchase_debit_note": ("supplier", "pay"),
        "sales_credit_note": ("customer", "pay"),
        "sales_debit_note": ("customer", "receive"),
    }
    return mapping.get(flow_source_type, ("customer", "receive"))


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
    """Valida los campos obligatorios del encabezado de Payment Entry."""
    if not company:
        raise ValueError(_("La compañía es obligatoria."))
    if not bank_account_id:
        raise ValueError(_("La cuenta bancaria es obligatoria."))
    if not posting_date_raw:
        raise ValueError(_("La fecha del pago es obligatoria."))
    if amount <= 0:
        raise ValueError(_("El monto del pago debe ser mayor que cero."))

    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        raise ValueError(_("La cuenta bancaria seleccionada no existe."))
    if bank_account.company != company:
        raise ValueError(_("La cuenta bancaria no pertenece a la misma compañía del pago."))

    if target_bank_account_id:
        target_bank_account = database.session.get(BankAccount, target_bank_account_id)
        if not target_bank_account:
            raise ValueError(_("La cuenta bancaria destino no existe."))
        if target_bank_account.company != company:
            raise ValueError(_("La cuenta bancaria destino no pertenece a la misma compañía del pago."))

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
        lines = []
        i = 0
        while request.form.get(f"reference_id_{i}"):
            lines.append(
                {
                    "reference_type": request.form.get(f"reference_type_{i}", ""),
                    "reference_id": request.form.get(f"reference_id_{i}", ""),
                    "allocated_amount": _form_decimal(f"allocated_amount_{i}", "0"),
                }
            )
            i += 1

    totals = {
        "allocated": Decimal("0"),
        "discount": Decimal("0"),
        "gain_loss": Decimal("0"),
    }
    processed_reference_keys: set[tuple[str, str]] = set()
    for line in lines:
        reference_type = line.get("reference_type", "")
        reference_id = line.get("reference_id", "")
        allocated = Decimal(str(line.get("allocated_amount", "0")))
        requested_flow_source_type = str(line.get("flow_source_type") or reference_type)
        reference_key = (normalize_doctype(requested_flow_source_type), reference_id)
        if reference_key in processed_reference_keys:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("No se puede aplicar la misma factura dos veces en un pago."))
        processed_reference_keys.add(reference_key)
        if allocated <= 0:
            if allocated < 0:
                from werkzeug.exceptions import Conflict

                raise Conflict(_("El monto asignado no puede ser negativo."))
            continue
        if normalize_doctype(requested_flow_source_type) in ("purchase_order", "sales_order") and not allow_order_references:
            raise ValueError(_("Las órdenes solo pueden referenciarse en flujo de anticipo."))
        if reference_type in ("purchase_invoice", "purchase_order", "purchase_credit_note", "purchase_debit_note"):
            model = PurchaseInvoice if "invoice" in reference_type or "note" in reference_type else PurchaseOrder
            invoice = database.session.get(model, reference_id)
        elif reference_type in ("sales_invoice", "sales_order", "sales_credit_note", "sales_debit_note"):
            model = SalesInvoice if "invoice" in reference_type or "note" in reference_type else SalesOrder
            invoice = database.session.get(model, reference_id)
        else:
            raise ValueError(_("Tipo de referencia inválido: {0}").format(reference_type))
        if not invoice:
            raise ValueError(_("Documento referenciado no existe."))
        invoice = cast(PurchaseInvoice | SalesInvoice, invoice)
        if getattr(invoice, "docstatus", 0) != 1:
            raise ValueError(_("El documento referenciado debe estar aprobado."))
        if payment.company and invoice.company and payment.company != invoice.company:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("El documento referenciado no pertenece a la misma compañía."))
        expected_party_type, expected_party_id = _reference_party_info(invoice)
        if payment.party_type and payment.party_type != expected_party_type:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("El tercero del pago no es compatible con el documento referenciado."))
        if payment.party_id and expected_party_id and payment.party_id != expected_party_id:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("El tercero del pago no coincide con el documento referenciado."))
        flow_source_type = _flow_source_type(reference_type, invoice, line)
        expected_payment_type_by_note = {
            "purchase_credit_note": "receive",
            "purchase_debit_note": "pay",
            "sales_credit_note": "pay",
            "sales_debit_note": "receive",
        }
        expected_payment_type = expected_payment_type_by_note.get(flow_source_type)
        if expected_payment_type and payment.payment_type != expected_payment_type:
            raise ValueError(_("El tipo de pago no corresponde con el tipo de nota referenciada."))
        physical_reference_type = _physical_reference_type(reference_type, flow_source_type)
        outstanding = _reference_outstanding(invoice, flow_source_type)
        if outstanding <= 0:
            raise ValueError(
                _("El documento {0} no tiene saldo pendiente (Saldo: {1}).").format(
                    getattr(invoice, "document_no", reference_id), outstanding
                )
            )
        if allocated > outstanding + Decimal("0.01"):
            raise ValueError(
                _("El monto aplicado ({0}) no puede ser mayor al saldo pendiente ({1}) del documento {2}.").format(
                    allocated, outstanding, getattr(invoice, "document_no", reference_id)
                )
            )
        discount_amount = Decimal(str(line.get("discount_amount") or "0"))
        gain_loss_amount = Decimal(str(line.get("gain_loss_amount") or "0"))
        difference_amount = Decimal(str(line.get("difference_amount") or gain_loss_amount or "0"))
        reference_date = _payment_reference_date(invoice)
        outstanding_after = outstanding - allocated
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type=physical_reference_type,
            flow_source_type=flow_source_type,
            reference_id=reference_id,
            reference_document_no=getattr(invoice, "document_no", None) or reference_id,
            reference_date=reference_date,
            party_type=expected_party_type,
            party_id=expected_party_id,
            company=getattr(invoice, "company", None),
            currency=getattr(invoice, "currency", None) or getattr(payment, "currency", None),
            total_amount=invoice.grand_total,
            outstanding_amount=outstanding,
            outstanding_amount_after=outstanding_after,
            allocated_amount=allocated,
            exchange_rate=Decimal(str(line.get("exchange_rate") or getattr(invoice, "exchange_rate", None) or 1)),
            difference_amount=difference_amount,
            allocation_date=payment.posting_date,
            discount_amount=discount_amount,
            gain_loss_amount=gain_loss_amount,
            notes=line.get("notes"),
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
            invoice.outstanding_amount = outstanding_after
            invoice.base_outstanding_amount = invoice.outstanding_amount
        totals["allocated"] += allocated
        totals["discount"] += discount_amount
        totals["gain_loss"] += gain_loss_amount
    return totals


def _refresh_payment_reference_document(reference_type: str, reference_id: str) -> None:
    """Actualiza el cache de saldo pendiente para documentos referenciados."""
    model_map = {
        "purchase_invoice": PurchaseInvoice,
        "sales_invoice": SalesInvoice,
        "purchase_order": PurchaseOrder,
        "sales_order": SalesOrder,
        "purchase_credit_note": PurchaseInvoice,
        "purchase_debit_note": PurchaseInvoice,
        "sales_credit_note": SalesInvoice,
        "sales_debit_note": SalesInvoice,
    }
    model = model_map.get(reference_type)
    if not model:
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
        try:
            payload_raw = request.form.get("payment_payload")
            if payload_raw:
                payload = json.loads(payload_raw)
            else:
                # Fallback para pruebas unitarias que no envían payment_payload
                payload = {
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
            payment_type = payload.get("payment_type") or "receive"
            company = payload.get("company")
            bank_account_id = payload.get("bank_account_id")
            amount = Decimal(str(payload.get("paid_amount") or "0"))
            target_bank_account_id = payload.get("target_bank_account_id")
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

            paid_from_account_id = payload.get("paid_from_account_id")
            paid_to_account_id = payload.get("paid_to_account_id")
            if payment_type == "internal_transfer":
                source_bank = database.session.get(BankAccount, bank_account_id) if bank_account_id else None
                target_bank = database.session.get(BankAccount, target_bank_account_id) if target_bank_account_id else None
                if source_bank and not paid_from_account_id:
                    paid_from_account_id = source_bank.gl_account_id
                if target_bank and not paid_to_account_id:
                    paid_to_account_id = target_bank.gl_account_id

            reference_date_raw = payload.get("reference_date")
            reference_date = date.fromisoformat(reference_date_raw) if reference_date_raw else None
            bank_account = database.session.get(BankAccount, bank_account_id) if bank_account_id else None
            payment_currency = bank_account.currency if bank_account else None
            if not payment_currency:
                raise ValueError(_("La cuenta bancaria seleccionada no tiene moneda configurada."))
            mode_of_payment = str(payload.get("mode_of_payment") or "").strip().lower()

            payment = PaymentEntry(
                payment_type=payment_type,
                company=company,
                bank_account_id=bank_account_id,
                target_bank_account_id=target_bank_account_id,
                currency=payment_currency,
                transaction_currency=payment_currency,
                exchange_rate=None,
                paid_amount=amount if payment_type in ("pay", "debit_note", "internal_transfer") else Decimal("0"),
                received_amount=amount if payment_type in ("receive", "credit_note", "internal_transfer") else Decimal("0"),
                party_type=payload.get("party_type"),
                party_id=payload.get("party_id"),
                party_name=payload.get("party_name"),
                paid_from_account_id=paid_from_account_id,
                paid_to_account_id=paid_to_account_id,
                cost_center_code=payload.get("cost_center_code"),
                unit_code=payload.get("unit_code"),
                project_code=payload.get("project_code"),
                reference_no=payload.get("reference_no"),
                reference_date=reference_date,
                mode_of_payment=mode_of_payment,
                remarks=payload.get("remarks"),
                docstatus=0,
            )

            if payment_type in ("pay", "debit_note", "internal_transfer"):
                payment.paid_amount = amount
                payment.base_paid_amount = amount
            if payment_type in ("receive", "credit_note", "internal_transfer"):
                payment.received_amount = amount
                payment.base_received_amount = amount

            database.session.add(payment)
            database.session.flush()

            default_series_id, default_counter_id = _payment_numbering_defaults(payment.bank_account_id)
            naming_series_id = payload.get("naming_series_id") or default_series_id
            external_counter_id = None
            external_number = None
            if mode_of_payment == "check":
                external_counter_id = payload.get("external_counter_id") or default_counter_id

            ext_context = {
                "payment_type": payment_type,
                "mode_of_payment": mode_of_payment,
            }
            if mode_of_payment == "check":
                ext_context["bank_account_id"] = payment.bank_account_id
            assign_document_identifier(
                document=payment,
                entity_type="payment_entry",
                posting_date_raw=payload.get("posting_date"),
                naming_series_id=naming_series_id,
                external_counter_id=external_counter_id,
                external_number=external_number,
                external_context=ext_context,
            )

            lines = payload.get("lines") or []
            ref_totals = _save_payment_references(
                payment,
                lines,
                allow_order_references=bool(payload.get("advance_mode")),
            )
            allocated = ref_totals["allocated"]
            discount = ref_totals["discount"]
            gain_loss = ref_totals["gain_loss"]

            if (allocated - discount - gain_loss) > amount + Decimal("0.01"):
                raise ValueError(_("El monto aplicado no puede ser mayor al monto total del pago."))
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

    from_purchase_invoice_ids = request.values.getlist("from_purchase_invoice")
    from_sales_invoice_ids = request.values.getlist("from_sales_invoice")
    from_purchase_order_ids = request.values.getlist("from_purchase_order")
    from_sales_order_ids = request.values.getlist("from_sales_order")
    from_purchase_credit_note_ids = request.values.getlist("from_purchase_credit_note")
    from_purchase_debit_note_ids = request.values.getlist("from_purchase_debit_note")
    from_sales_credit_note_ids = request.values.getlist("from_sales_credit_note")
    from_sales_debit_note_ids = request.values.getlist("from_sales_debit_note")
    source_rows = _payment_source_rows(
        from_purchase_invoice_ids,
        from_sales_invoice_ids,
        from_purchase_order_ids,
        from_sales_order_ids,
        from_purchase_credit_note_ids,
        from_purchase_debit_note_ids,
        from_sales_credit_note_ids,
        from_sales_debit_note_ids,
    )

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
