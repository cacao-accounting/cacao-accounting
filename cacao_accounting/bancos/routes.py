"""Modulo de Caja y Bancos."""

from datetime import date

from decimal import Decimal

import json


from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from flask.typing import ResponseReturnValue

from flask_login import current_user, login_required

from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    BankReconciliationMatch,
    BankReconciliationRequest,
    reconcile_bank_items,
)

from cacao_accounting.bancos.statement_service import (
    BankStatementError,
    apply_bank_matching_rule,
)

from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    BankAccountNumberingConfig,
    BankMatchingRule,
    BankTransaction,
    Book,
    ExternalCounter,
    GLEntry,
    PaymentEntry,
    PaymentReference,
    ReconciliationItem,
    User,
    database,
)

from cacao_accounting.auth.permisos import Permisos

from cacao_accounting.database.helpers import get_active_naming_series

from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

from cacao_accounting.contabilidad.posting import PostingError, cancel_document, submit_document


from cacao_accounting.document_flow.service import apply_payment_reconciliation


from cacao_accounting.document_flow.context import effective_currency


from cacao_accounting.document_flow.status import _

from cacao_accounting.document_identifiers import (
    IdentifierConfigurationError,
)

from cacao_accounting.decorators import exige_acceso_compania, modulo_activo, verifica_permiso


from cacao_accounting.version import APPNAME

from cacao_accounting.audit_trail_service import format_document_timeline, log_cancel, log_submit

from cacao_accounting.bancos.services import (
    _safe_bank_reconciliation_candidates,
    _validate_bank_account_numbering_defaults,
    _ensure_bank_account_counter_mapping,
    _lookup_series_name,
    _lookup_counter_name,
    _ensure_bank_account_numbering_config,
    _paginate_list,
    _bank_reconciliation_allocated_amount,
    _post_bank_difference_adjustment,
    _save_numbering_configs,
    _build_numbering_config_response,
    _form_decimal,
    _payment_profile_from_source_type,
    _payment_reference_date,
    _reference_outstanding,
    _create_payment_from_request,
    _payment_source_rows_from_request,
)

bancos = Blueprint("bancos", __name__, template_folder="templates")

BANCOS_TRANSACCION_LISTA_HTML = "bancos/transaccion_lista.html"

BANCOS_BANCO_CUENTA_NUEVO_HTML = "bancos/banco_cuenta_nuevo.html"

BANCOS_PAGO_LISTA_HTML = "bancos/pago_lista.html"

BANCOS_BANCOS_PAGO = "bancos.bancos_pago"

BANCOS_CONCILIACION_ENDPOINT = "bancos.bancos_conciliacion_bancaria"

BANCOS_REGLAS_MATCHING_ENDPOINT = "bancos.bancos_reglas_matching"

COMPRAS_FACTURA_COMPRA_ROUTE = "compras.compras_factura_compra"

VENTAS_FACTURA_VENTA_ROUTE = "ventas.ventas_factura_venta"

LABEL_FACTURA_COMPRA = "Factura de Compra"

LABEL_FACTURA_VENTA = "Factura de Venta"

PAYMENT_TYPES = ("pay", "receive", "internal_transfer", "debit_note", "credit_note")


def _cash_accessible_companies():
    """Return the companies readable by the current cash-management user."""
    permissions = Permisos(
        modulo=obtener_id_modulo_por_nombre("cash"),
        usuario=current_user.id,
    )
    if permissions.administrador:
        return None
    companies = permissions.obtener_companias_autorizadas() if permissions.consultar else []
    if not companies:
        return database.select(Book.entity).where(database.false())
    return database.select(Book.entity).where(Book.entity.in_(companies))


from cacao_accounting.bancos import cash_forecast as _cf  # noqa: F401, E402


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
            company = str(payload.get("company") or "")
            exige_acceso_compania("cash", company, "editar")
            allocation_date = date.fromisoformat(payload.get("allocation_date") or date.today().isoformat())
            reconciliation = apply_payment_reconciliation(
                company=company,
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
            flash_error(exc)
        except Exception as exc:  # noqa: BLE001
            from cacao_accounting.document_flow import DocumentFlowError

            database.session.rollback()
            if isinstance(exc, DocumentFlowError):
                flash_error(exc)
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

    if company is None:
        abort(404)
    exige_acceso_compania("cash", company, "editar")

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
        return redirect(url_for(BANCOS_CONCILIACION_ENDPOINT))

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
        exige_acceso_compania("cash", company, "consultar")
        query = query.join(BankAccount, BankAccount.id == BankTransaction.bank_account_id).filter(
            BankAccount.company == company
        )
    elif not getattr(current_user, "classification", None) == "admin":
        module_id = obtener_id_modulo_por_nombre("cash")
        permissions = Permisos(modulo=module_id, usuario=current_user.id)
        companies = permissions.obtener_companias_autorizadas() if permissions.consultar else []
        if not companies:
            query = query.where(database.false())
        else:
            query = query.join(BankAccount, BankAccount.id == BankTransaction.bank_account_id).filter(
                BankAccount.company.in_(companies)
            )
    transactions = database.session.execute(query.order_by(BankTransaction.posting_date)).scalars().all()
    suggestions = {transaction.id: _safe_bank_reconciliation_candidates(transaction) for transaction in transactions}
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
    exige_acceso_compania("cash", bank_account.company, "consultar")
    transactions = (
        database.session.execute(
            database.select(BankTransaction)
            .filter_by(bank_account_id=bank_account_id, is_reconciled=False)
            .order_by(BankTransaction.posting_date)
        )
        .scalars()
        .all()
    )
    suggestions = {transaction.id: _safe_bank_reconciliation_candidates(transaction) for transaction in transactions}
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
    transaction_ids = request.form.getlist("bank_transaction_id")
    if transaction_ids:
        transactions = (
            database.session.execute(database.select(BankTransaction).filter(BankTransaction.id.in_(transaction_ids)))
            .scalars()
            .all()
        )
        companies: set[str] = set()
        for transaction in transactions:
            bank_account = database.session.get(BankAccount, transaction.bank_account_id)
            if bank_account:
                companies.add(str(bank_account.company))
        if len(companies) != 1 or company not in companies:
            abort(403)
        exige_acceso_compania("cash", company, "editar")
        if any(txn.is_reconciled for txn in transactions):
            flash(_("Una o mas transacciones ya estan reconciliadas."), "danger")
            return redirect(url_for(BANCOS_CONCILIACION_ENDPOINT, company=company))
    matches: list[BankReconciliationMatch] = []
    difference_requests: list[tuple[str, Decimal]] = []
    for transaction_id in transaction_ids:
        target = request.form.get(f"target_{transaction_id}") or ""
        amount = _form_decimal(f"amount_{transaction_id}")
        difference = _form_decimal(f"difference_{transaction_id}")
        if not target or amount <= 0:
            if difference > 0:
                flash(_("Una diferencia bancaria requiere un candidato y un monto conciliado."), "danger")
                return redirect(url_for(BANCOS_CONCILIACION_ENDPOINT, company=company))
            continue
        if difference < 0:
            flash(_("La diferencia bancaria debe ser mayor o igual a cero."), "danger")
            return redirect(url_for(BANCOS_CONCILIACION_ENDPOINT, company=company))
        if difference > 0:
            transaction = database.session.get(BankTransaction, transaction_id)
            bank_amount = _bank_reconciliation_allocated_amount(transaction) if transaction else None
            if bank_amount is None or amount + difference != bank_amount:
                flash(_("El monto conciliado más la diferencia debe coincidir con el monto bancario."), "danger")
                return redirect(url_for(BANCOS_CONCILIACION_ENDPOINT, company=company))
            difference_requests.append((transaction_id, difference))
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
        reconciliation = reconcile_bank_items(
            BankReconciliationRequest(company=company, reconciliation_date=date.today(), matches=matches)
        )
        for transaction_id, difference in difference_requests:
            transaction = database.session.get(BankTransaction, transaction_id, with_for_update=True)
            if transaction is None:
                raise BankReconciliationError("La transaccion bancaria no existe.")
            _post_bank_difference_adjustment(
                reconciliation.id,
                transaction,
                difference,
                user_id=str(current_user.id),
            )
        database.session.commit()
        flash(_("Conciliación bancaria y diferencia aplicadas correctamente."), "success")
    except BankReconciliationError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for(BANCOS_CONCILIACION_ENDPOINT, company=company))


@bancos.route("/bank-statement/import", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_extracto_importar():
    """Redirige al asistente de importación compartido."""
    flash(
        _("La importación de extractos bancarios ahora se realiza a través del asistente de importación compartido."),
        "info",
    )
    return redirect(url_for("imports.new"))


@bancos.route("/bank-matching-rules", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_reglas_matching():
    """Administra reglas de matching bancario."""
    company_scope = _cash_accessible_companies()
    accounts_query = database.select(BankAccount).filter_by(is_active=True)
    rules_query = database.select(BankMatchingRule)
    if company_scope is not None:
        accounts_query = accounts_query.where(BankAccount.company.in_(company_scope))
        rules_query = rules_query.where(BankMatchingRule.company.in_(company_scope))
    accounts = database.session.execute(accounts_query.order_by(BankAccount.account_name)).scalars().all()
    if request.method == "POST":
        company = request.form.get("company") or ""
        exige_acceso_compania("cash", company, "editar")
        bank_account_id = request.form.get("bank_account_id") or None
        if bank_account_id:
            bank_account = database.session.get(BankAccount, bank_account_id)
            if not bank_account:
                flash(_("La cuenta bancaria seleccionada no existe."), "danger")
                return redirect(url_for(BANCOS_REGLAS_MATCHING_ENDPOINT))
            if bank_account.company != company:
                flash(_("La cuenta bancaria no pertenece a la compañía de la regla."), "danger")
                return redirect(url_for(BANCOS_REGLAS_MATCHING_ENDPOINT))
        rule = BankMatchingRule(
            company=company,
            bank_account_id=bank_account_id,
            name=request.form.get("name") or "",
            days_tolerance=int(request.form.get("days_tolerance") or 7),
            amount_tolerance=Decimal(request.form.get("amount_tolerance") or "0"),
            reference_contains=request.form.get("reference_contains") or None,
            priority=int(request.form.get("priority") or 100),
            is_active=bool(request.form.get("is_active", "1")),
            auto_reconcile=bool(request.form.get("auto_reconcile")),
        )
        database.session.add(rule)
        database.session.commit()
        flash(_("Regla de matching creada correctamente."), "success")
        return redirect(url_for(BANCOS_REGLAS_MATCHING_ENDPOINT))
    rules = database.session.execute(rules_query.order_by(BankMatchingRule.priority)).scalars().all()
    return render_template(
        "bancos/reglas_matching.html", accounts=accounts, rules=rules, titulo=_("Reglas de Matching Bancario")
    )


@bancos.route("/bank-matching-rules/<rule_id>/run", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_regla_matching_ejecutar(rule_id: str):
    """Ejecuta una regla de matching para una cuenta y rango."""
    try:
        rule = database.session.get(BankMatchingRule, rule_id)
        if not rule:
            raise BankStatementError("La regla de matching no existe.")
        exige_acceso_compania("cash", rule.company, "editar")
        bank_account_id = request.form.get("bank_account_id") or ""
        if bank_account_id:
            bank_account = database.session.get(BankAccount, bank_account_id)
            if not bank_account:
                raise BankStatementError("La cuenta bancaria indicada no existe.")
            if bank_account.company != rule.company:
                raise BankStatementError("La cuenta bancaria no pertenece a la compañía de la regla.")
        date_from = date.fromisoformat(request.form.get("date_from") or date.today().isoformat())
        date_to = date.fromisoformat(request.form.get("date_to") or date.today().isoformat())
        result = apply_bank_matching_rule(rule_id, bank_account_id, (date_from, date_to))
        flash(
            _("Regla ejecutada: {count} transacciones evaluadas.").format(count=len(result.candidates_by_transaction)),
            "success",
        )
    except BankStatementError as exc:
        flash(_(str(exc)), "danger")
    return redirect(url_for(BANCOS_REGLAS_MATCHING_ENDPOINT))


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
@verifica_permiso("cash", "crear")
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
        exige_acceso_compania("cash", company, "crear")
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
        _ensure_bank_account_numbering_config(cuenta)
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
    exige_acceso_compania("cash", registro.company, "consultar")
    titulo = registro.account_name + " - " + APPNAME

    from cacao_accounting.document_identifiers import PAYMENT_TYPE_TO_ENTITY_TYPE as ENTITY_MAP

    PAYMENT_TYPE_LABELS = {
        "pay": _("Pago a Proveedor"),
        "receive": _("Cobro de Cliente"),
        "internal_transfer": _("Transferencia Interna"),
        "debit_note": _("Nota de Debito"),
        "credit_note": _("Nota de Credito"),
    }

    configs = (
        database.session.execute(
            database.select(BankAccountNumberingConfig)
            .filter_by(bank_account_id=account_id)
            .order_by(BankAccountNumberingConfig.payment_type)
        )
        .scalars()
        .all()
    )

    numbering_configs = []
    for payment_type in PAYMENT_TYPES:
        cfg = next((c for c in configs if c.payment_type == payment_type), None)
        entity_type = ENTITY_MAP.get(payment_type, "payment_entry")
        naming_series_name = None
        counter_name = None
        if cfg:
            naming_series_name = _lookup_series_name(cfg.naming_series_id)
            counter_name = _lookup_counter_name(cfg.external_counter_id)
            numbering_configs.append(
                {
                    "payment_type": cfg.payment_type,
                    "label": PAYMENT_TYPE_LABELS.get(payment_type, payment_type),
                    "naming_series_id": cfg.naming_series_id,
                    "naming_series_name": naming_series_name,
                    "use_external_counter": cfg.use_external_counter,
                    "external_counter_id": cfg.external_counter_id,
                    "counter_name": counter_name,
                    "entity_type": entity_type,
                }
            )
        else:
            numbering_configs.append(
                {
                    "payment_type": payment_type,
                    "label": PAYMENT_TYPE_LABELS.get(payment_type, payment_type),
                    "naming_series_id": None,
                    "naming_series_name": None,
                    "use_external_counter": payment_type in ("pay", "receive"),
                    "external_counter_id": None,
                    "counter_name": None,
                    "entity_type": entity_type,
                }
            )

    company = registro.company
    naming_series_options = []
    for et in set(ENTITY_MAP.values()):
        series_list = get_active_naming_series(entity_type=et, company=company)
        for s in series_list:
            naming_series_options.append({"value": s.id, "label": f"{s.name} ({s.prefix_template})"})

    external_counter_options = []
    counters = (
        database.session.execute(database.select(ExternalCounter).filter_by(company=company, is_active=True)).scalars().all()
    )
    for c in counters:
        external_counter_options.append({"value": c.id, "label": f"{c.name} ({c.next_suggested_formatted})"})

    return render_template(
        "bancos/banco_cuenta.html",
        registro=registro,
        titulo=titulo,
        numbering_configs=numbering_configs,
        naming_series_options=naming_series_options,
        external_counter_options=external_counter_options,
        PAYMENT_TYPES=PAYMENT_TYPES,
    )


@bancos.route("/bank-account/<account_id>/numbering-config", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria_numbering_config(account_id: str) -> ResponseReturnValue:
    """Gestiona la configuracion de numeracion por tipo de transaccion."""
    bank_account = database.session.get(BankAccount, account_id)
    if not bank_account:
        abort(404)
    if request.method == "POST":
        exige_acceso_compania("cash", bank_account.company, "editar")
        try:
            return _save_numbering_configs(bank_account)
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            return {"status": "error", "message": str(exc)}, 400

    exige_acceso_compania("cash", bank_account.company, "consultar")
    return _build_numbering_config_response(bank_account)


@bancos.route("/payment/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_nuevo():
    """Formulario para crear un nuevo pago."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

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
                    "currency": effective_currency(document) or "",
                    "reference_label": row.get("label", ""),
                    # JSON/Alpine must receive the exact decimal representation;
                    # converting to float here loses financial precision before
                    # the user can confirm the allocation.
                    "total_amount": str(Decimal(str(document.grand_total or 0))),
                    "outstanding_amount": str(Decimal(str(outstanding))),
                    "allocated_amount": str(Decimal(str(outstanding))),
                }
            )

        initial_payment = {
            "company": first.company,
            "flow_locked": True,
            "party_id": getattr(first, "supplier_id", None) or getattr(first, "customer_id", None),
            "party_type": party_type,
            "payment_type": payment_type,
            "currency": effective_currency(first) or "",
            "paid_amount": str(initial_amount),
            "lines": lines,
            "advance_mode": any(row["reference_type"] in ("purchase_order", "sales_order") for row in source_rows),
        }

    transaction_config = {}

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
    exige_acceso_compania("cash", registro.company, "consultar")

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
    from cacao_accounting.database import WithholdingCertificate

    withholding_certificate = database.session.execute(
        database.select(WithholdingCertificate).filter_by(payment_id=registro.id)
    ).scalar_one_or_none()

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
        withholding_certificate=withholding_certificate,
        audit_timeline=format_document_timeline("payment_entry", registro.id),
    )


@bancos.route("/payment/<payment_id>/submit", methods=["POST"])
@modulo_activo("cash")
@login_required
@verifica_permiso("cash", "autorizar")
def bancos_pago_submit(payment_id: str):
    """Aprueba y contabiliza un pago."""
    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    exige_acceso_compania("cash", registro.company, "autorizar")
    if registro.docstatus != 0:
        abort(400)
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.handle_submission(registro, current_user, "Pago"):
            return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))

        submit_document(registro)  # type: ignore[misc]
        log_submit(registro)
        database.session.commit()
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    flash(_("Pago aprobado y contabilizado."), "success")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))


@bancos.route("/payment/<payment_id>/cancel", methods=["POST"])
@modulo_activo("cash")
@login_required
@verifica_permiso("cash", "anular")
def bancos_pago_cancel(payment_id: str):
    """Cancela un pago con reverso contable.

    Los ``PaymentReference`` NO se eliminan: es diseño append-only.
    La cancelacion crea entradas GL de reverso pero preserva las
    referencias de pago como historial funcional. Los saldos de los
    documentos referenciados se recalculan via
    ``_refresh_payment_reference_document``.
    """
    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    exige_acceso_compania("cash", registro.company, "anular")
    if registro.docstatus != 1:
        abort(400)
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash(_("Debe indicar el motivo de la anulación."), "danger")
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    try:
        from cacao_accounting.approval_engine import ApprovalEngine

        if ApprovalEngine.is_enabled(registro.company):
            ApprovalEngine.request_cancellation(
                registro,
                reason=reason,
                cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
            )
            database.session.commit()
            flash(_("Solicitud de cancelación enviada para aprobación (Pendiente de Cancelación)."), "info")
            return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))

        cancel_document(
            registro,
            reason=reason,
            actor_user_id=str(current_user.id),
            cancellation_date=request.form.get("cancellation_date") or registro.posting_date,
        )  # type: ignore[misc]
        log_cancel(registro)
        database.session.commit()
    except PostingError as exc:  # type: ignore[misc]
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    flash(_("Pago cancelado con reverso contable."), "warning")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
