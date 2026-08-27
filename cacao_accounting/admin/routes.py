"""Modulo administrativo."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from flask_login import current_user, login_required

from sqlalchemy import delete

from sqlalchemy.exc import IntegrityError

from cacao_accounting.auth import helpers, proteger_passwd
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

from cacao_accounting.auth.forms import (
    RoleForm,
    UserCreateForm,
    UserCompanyAccessForm,
    UserEditForm,
    UserPasswordForm,
    UserRoleForm,
)

from cacao_accounting.decorators import modulo_activo

from cacao_accounting.database import (
    Accounts,
    ApprovalMatrix,
    Book,
    CompanyDefaultAccount,
    Entity,
    Item,
    ItemPrice,
    Modules,
    PartyGroup,
    PriceList,
    PurchaseMatchingConfig,
    Roles,
    RolesAccess,
    RolesUser,
    SalesMatchingConfig,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    User,
    UserCompanyAccess,
    database,
)


from cacao_accounting.contabilidad.default_accounts import (
    DEFAULT_ACCOUNT_DEFINITIONS,
    DEFAULT_ACCOUNT_FIELDS,
    DefaultAccountError,
    default_account_rows,
    get_company_default_accounts,
    upsert_company_default_accounts,
)

from cacao_accounting.document_flow.status import _

from cacao_accounting.modulos import listado_modulos, obtener_modulos_disponibles, sincronizar_modulos

from cacao_accounting.printing.settings import (
    DEFAULT_VALIDATION_BASE_URL,
    external_validation_base_url,
    external_validation_enabled,
    save_external_validation_settings,
)

from cacao_accounting.inventario.valuation_settings import (
    company_has_inventory_activity,
    get_company_valuation_method,
    list_companies_with_valuation,
    update_company_valuation_method,
    valuation_method_choices,
    valuation_method_label,
)

from cacao_accounting.compras.purchase_sourcing_service import (
    get_purchase_sourcing_config,
    set_purchase_sourcing_config,
)

from cacao_accounting.admin.navigation import CONFIGURATION_SECTIONS
from cacao_accounting.admin.services import (
    _apply_user_edit,
    _can_create_user,
    _crear_usuario_desde_form,
    _date_form,
    _decimal_form,
    _email_settings_values,
    _handle_approval_matrix_post,
    _obtener_modulos_disponibles,
    _obtener_permisos_por_rol,
    _obtener_rol,
    _obtener_roles_disponibles,
    _obtener_roles_por_usuario,
    _obtener_usuario,
    _pending_approval_info,
    _populate_portal_choices,
    _process_pending_approval_post,
    _require_system_admin,
    _save_email_settings,
    _send_email_test,
    _validar_creacion_usuario,
    _validate_portal_fields,
)

from cacao_accounting.admin.session_security_service import (
    desbloquear_cuenta_usuario,
    is_session_security_enabled,
    listar_cuentas_bloqueadas,
    listar_todos_dispositivos,
    revocar_dispositivo,
    set_session_security_enabled,
    smtp_is_configured,
)
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting.ventas.services import is_sales_price_editor

from cacao_accounting.tax_rule_service import (
    TaxRuleServiceError,
    create_tax_rule,
    delete_tax_rule,
    get_tax_rule,
    list_tax_rules,
    update_tax_rule,
)

from cacao_accounting.contabilidad.ledger_mapping_service import (
    LedgerMappingError,
    create_ledger_mapping_rule,
    deactivate_ledger_mapping_rule,
    list_ledger_mapping_rules,
)


def _require_price_list_editor() -> None:
    """Allow catalog maintenance only to system admins and sales managers."""
    if not current_user.is_authenticated or not is_sales_price_editor(str(current_user.id)):
        abort(403)


def _can_manage_price_list(price_list: PriceList) -> bool:
    """Return whether the current catalog editor may manage this company list."""
    if current_user.classification == "admin":
        return True
    if not price_list.company:
        return False
    permissions = Permisos(modulo=obtener_id_modulo_por_nombre("sales"), usuario=current_user.id)
    return bool(permissions.tiene_acceso_compania(price_list.company))


def _require_price_list_company_access(price_list: PriceList) -> None:
    """Forbid sales managers from changing a list outside their companies."""
    if not _can_manage_price_list(price_list):
        abort(403)


admin = Blueprint("admin", __name__, template_folder="templates")

LISTA_MODULOS = "admin.lista_modulos"

CUENTAS_PREDETERMINADAS = "admin.cuentas_predeterminadas"

USUARIO_NO_ENCONTRADO = "Usuario no encontrado."

LISTA_USUARIOS = "admin.lista_usuarios"

LISTA_ROLES = "admin.lista_roles"

ADMIN_LISTA_GRUPOS_TERCEROS = "admin.lista_grupos_terceros"

DESKTOP_SINGLE_ADMIN_MESSAGE = "En modo escritorio solo se permite un usuario administrador."

LISTA_VALUACION_INVENTARIO = "admin.configuracion_valuacion_inventario"

BUDGET_CONTROL_VALID_ACTIONS = ("do_nothing", "notify", "block")

ADMIN_APPROVAL_MATRIX_ENDPOINT = "admin.config_approval_matrix"

ADMIN_CONTROL_PRESUPUESTARIO_ENDPOINT = "admin.config_control_presupuestario"

DEBE_SELECCIONAR_COMPANIA_MSG = "Debe seleccionar una compania."


@admin.route("/admin")
@admin.route("/ajustes")
@admin.route("/administracion")
@admin.route("/configuracion")
@admin.route("/settings")
@login_required
@modulo_activo("admin")
def admin_():
    """Definición del modulo administrativo."""
    return render_template("admin.html", configuration_sections=CONFIGURATION_SECTIONS)


@admin.route("/settings/modules", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_modulos():
    """Administra los módulos instalados en el sistema."""
    _require_system_admin()
    sincronizar_modulos()

    if request.method == "POST":
        module_id = request.form.get("module_id")
        action = request.form.get("action")
        module = database.session.get(Modules, module_id) if module_id else None

        if module is None:
            flash("Módulo no encontrado.", "danger")
            return redirect(url_for(LISTA_MODULOS))

        if module.module == "admin":
            flash("El módulo administrativo no puede deshabilitarse.", "danger")
            return redirect(url_for(LISTA_MODULOS))

        if action == "toggle":
            module.enabled = not module.enabled
            database.session.commit()
            estado = "habilitado" if module.enabled else "deshabilitado"
            flash(f"Módulo {module.module} {estado} correctamente.", "success")
            return redirect(url_for(LISTA_MODULOS))

    datos = listado_modulos()
    modulos_disponibles = obtener_modulos_disponibles()
    modulos_por_tipo = []
    standard_names = {item["module"] for item in modulos_disponibles if item["type"] == "estandar"}

    for registro in datos["modulos"]:
        modulos_por_tipo.append(
            {
                "id": registro.id,
                "module": registro.module,
                "enabled": registro.enabled,
                "default": registro.default,
                "type": "Estándar" if registro.module in standard_names else "Plugin",
                "package": next(
                    (item["package"] for item in modulos_disponibles if item["module"] == registro.module),
                    None,
                ),
            }
        )
    return render_template(
        "admin/modulos.html",
        modulos=modulos_por_tipo,
    )


@admin.route("/settings/language", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def configuracion_idioma():
    """Configuración del idioma predeterminado del sistema."""
    _require_system_admin()
    from cacao_accounting.setup.catalogs import LANGUAGE_CHOICES
    from cacao_accounting.setup.service import SETUP_LANGUAGE, get_setup_value, set_setup_value

    if request.method == "POST":
        selected_lang = request.form.get("language")
        valid_codes = [code for code, _ in LANGUAGE_CHOICES]
        if selected_lang in valid_codes:
            set_setup_value(SETUP_LANGUAGE, selected_lang)
            database.session.commit()
            flash(_("Idioma del sistema actualizado correctamente."), "success")
            return redirect(url_for("admin.configuracion_idioma"))
        flash(_("Idioma seleccionado no es válido."), "danger")

    current_lang = get_setup_value(SETUP_LANGUAGE, "es")
    return render_template(
        "admin/system_language.html",
        current_language=current_lang,
        language_choices=LANGUAGE_CHOICES,
    )


@admin.route("/settings/external-document-validation", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def external_document_validation_settings():
    """Administra la validacion externa de documentos impresos."""
    _require_system_admin()
    if request.method == "POST":
        save_external_validation_settings(
            enabled=request.form.get("enabled") == "on",
            base_url=request.form.get("base_url") or DEFAULT_VALIDATION_BASE_URL,
        )
        flash(_("Configuracion de validacion externa guardada correctamente."), "success")
        return redirect(url_for("admin.external_document_validation_settings"))

    return render_template(
        "admin/external_document_validation.html",
        enabled=external_validation_enabled(),
        base_url=external_validation_base_url(),
        fallback_url=DEFAULT_VALIDATION_BASE_URL,
    )


@admin.route("/settings/email", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def email_settings():
    """Administra la configuración del servidor de correo electrónico SMTP (Cloud-Only)."""
    _require_system_admin()
    if is_desktop_mode():
        abort(403)

    if request.method == "POST":
        if request.form.get("action") == "test_email":
            _send_email_test()
            return redirect(url_for("admin.email_settings"))
        _save_email_settings()
        flash(_("Configuración de correo electrónico guardada correctamente."), "success")
        return redirect(url_for("admin.email_settings"))

    settings = _email_settings_values()

    return render_template(
        "admin/email_settings.html",
        smtp_server=settings["smtp_server"],
        smtp_port=settings["smtp_port"],
        smtp_user=settings["smtp_user"],
        smtp_use_tls=settings["smtp_use_tls"].lower() in ("true", "1", "yes", "y", "on"),
        smtp_from_email=settings["smtp_from_email"],
        disable_transaction_emails=settings["disable_transaction_emails"].lower() in ("true", "1", "yes", "y", "on"),
        titulo=_("Configuración de Correo Electrónico"),
    )


@admin.route("/settings/email-log")
@login_required
@modulo_activo("admin")
def email_log():
    """Muestra la bitácora y cola de correos electrónicos del sistema (Cloud-Only)."""
    _require_system_admin()
    if is_desktop_mode():
        abort(403)

    from cacao_accounting.database import EmailQueue

    page = request.args.get("page", 1, type=int)
    search = (request.args.get("search") or "").strip()
    status_filter = (request.args.get("status") or "").strip()

    query = database.select(EmailQueue)

    if search:
        query = query.where(
            EmailQueue.recipient.ilike(f"%{search}%")
            | EmailQueue.subject.ilike(f"%{search}%")
            | EmailQueue.document_id.ilike(f"%{search}%")
        )

    if status_filter:
        query = query.where(EmailQueue.status == status_filter)

    query = query.order_by(EmailQueue.created.desc())

    consulta = database.paginate(query, page=page, per_page=20)

    return render_template(
        "admin/email_log.html",
        consulta=consulta,
        titulo=_("Bitácora de Correos Electrónicos"),
    )


@admin.route("/settings/email-log/<queue_id>/retry", methods=["POST"])
@login_required
@modulo_activo("admin")
def email_log_retry(queue_id: str):
    """Reintenta el envío de un correo electrónico desde la bitácora."""
    _require_system_admin()
    if is_desktop_mode():
        abort(403)

    from cacao_accounting.messaging.email import retry_email_queue_item, EmailError

    try:
        retry_email_queue_item(queue_id)
        flash(_("Correo reenviado exitosamente."), "success")
    except EmailError as exc:
        flash(_(str(exc)), "danger")
    except Exception as exc:
        flash(_(f"Error al reintentar envío: {exc}"), "danger")

    return redirect(url_for("admin.email_log"))


@admin.route("/settings/inventory-valuation", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def configuracion_valuacion_inventario():
    """Administra el metodo global de valuacion de inventario por compania."""
    _require_system_admin()
    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    selected_company = request.form.get("company") or request.args.get("company") or (companies[0].code if companies else "")

    if request.method == "POST":
        if not selected_company:
            flash(_(DEBE_SELECCIONAR_COMPANIA_MSG), "danger")
            return redirect(url_for(LISTA_VALUACION_INVENTARIO))
        try:
            update_company_valuation_method(selected_company, request.form.get("valuation_method") or "")
        except ValueError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
        else:
            database.session.commit()
            flash(_("Metodo de valuacion guardado correctamente."), "success")
        return redirect(url_for(LISTA_VALUACION_INVENTARIO, company=selected_company))

    current_method = get_company_valuation_method(selected_company) if selected_company else "moving_average"
    locked = company_has_inventory_activity(selected_company) if selected_company else False

    return render_template(
        "admin/inventory_valuation.html",
        companies=companies,
        company_rows=list_companies_with_valuation(),
        selected_company=selected_company,
        valuation_choices=valuation_method_choices(),
        current_method=current_method,
        current_method_label=valuation_method_label(current_method),
        locked=locked,
        titulo=_("Valuacion de inventarios"),
    )


@admin.route("/settings/taxes", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_impuestos():
    """Administra impuestos y cargos de compra/venta."""
    _require_system_admin()
    if request.method == "POST":
        tax = Tax(
            name=request.form.get("name") or "",
            rate=_decimal_form("rate"),
            tax_type=request.form.get("tax_type") or "percentage",
            applies_to=request.form.get("applies_to") or "both",
            account_id=request.form.get("account_id") or None,
            is_charge=bool(request.form.get("is_charge")),
            is_capitalizable=bool(request.form.get("is_capitalizable")),
            is_active=bool(request.form.get("is_active", "1")),
        )
        database.session.add(tax)
        database.session.commit()
        flash(_("Impuesto o cargo creado correctamente."), "success")
        return redirect(url_for("admin.lista_impuestos"))
    taxes = database.session.execute(database.select(Tax).order_by(Tax.name)).scalars().all()
    return render_template("admin/taxes.html", taxes=taxes, titulo=_("Impuestos y Cargos"))


@admin.route("/settings/tax-templates", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_plantillas_impuesto():
    """Administra plantillas de impuestos."""
    _require_system_admin()
    if request.method == "POST":
        template = TaxTemplate(
            name=request.form.get("name") or "",
            company=request.form.get("company") or None,
            template_type=request.form.get("template_type") or "selling",
            currency=request.form.get("currency") or None,
            is_active=bool(request.form.get("is_active", "1")),
        )
        database.session.add(template)
        database.session.commit()
        flash(_("Plantilla de impuestos creada correctamente."), "success")
        return redirect(url_for("admin.lista_plantillas_impuesto"))
    templates = database.session.execute(database.select(TaxTemplate).order_by(TaxTemplate.name)).scalars().all()
    return render_template("admin/tax_templates.html", templates=templates, titulo=_("Plantillas de Impuestos"))


@admin.route("/settings/tax-templates/<template_id>/items", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def items_plantilla_impuesto(template_id: str):
    """Administra lineas de una plantilla de impuestos."""
    _require_system_admin()
    template = database.session.get(TaxTemplate, template_id)
    if not template:
        abort(404)
    if request.method == "POST":
        item = TaxTemplateItem(
            tax_template_id=template.id,
            tax_id=request.form.get("tax_id") or "",
            sequence=int(request.form.get("sequence") or 10),
            calculation_base=request.form.get("calculation_base") or "net_document",
            behavior=request.form.get("behavior") or "additive",
            is_inclusive=bool(request.form.get("is_inclusive")),
        )
        database.session.add(item)
        database.session.commit()
        flash(_("Linea de impuesto agregada correctamente."), "success")
        return redirect(url_for("admin.items_plantilla_impuesto", template_id=template.id))
    items = (
        database.session.execute(
            database.select(TaxTemplateItem).filter_by(tax_template_id=template.id).order_by(TaxTemplateItem.sequence)
        )
        .scalars()
        .all()
    )
    taxes = database.session.execute(database.select(Tax).filter_by(is_active=True).order_by(Tax.name)).scalars().all()
    return render_template("admin/tax_template_items.html", template=template, items=items, taxes=taxes)


@admin.route("/settings/tax-rules", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_reglas_fiscales():
    """Administra reglas fiscales configurables."""
    _require_system_admin()
    editing_rule_id = request.args.get("edit")
    editing_rule = get_tax_rule(editing_rule_id) if editing_rule_id else None
    if request.method == "POST":
        try:
            rule = create_tax_rule(request.form)
            database.session.commit()
        except TaxRuleServiceError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
        else:
            flash(_("Regla fiscal creada correctamente."), "success")
            return redirect(url_for("admin.lista_reglas_fiscales", edit=rule.id))
    rules = list_tax_rules()
    return render_template("admin/tax_rules.html", rules=rules, editing_rule=editing_rule)


@admin.route("/settings/party-groups", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_grupos_terceros():
    """Administra tipos globales de clientes y proveedores."""
    _require_system_admin()
    group_type = request.args.get("group_type") or request.form.get("group_type") or ""
    if group_type not in ("customer", "supplier"):
        group_type = ""
    if request.method == "POST":
        group = PartyGroup(
            group_type=request.form.get("group_type") or "customer",
            name=request.form.get("name") or "",
            description=request.form.get("description") or None,
            is_active=request.form.get("is_active") is not None,
        )
        database.session.add(group)
        try:
            database.session.commit()
        except IntegrityError:
            database.session.rollback()
            flash(_("Ya existe un tipo de tercero con ese nombre."), "danger")
        else:
            flash(_("Tipo de tercero creado correctamente."), "success")
            return redirect(url_for(ADMIN_LISTA_GRUPOS_TERCEROS, group_type=group.group_type))
    query = database.select(PartyGroup)
    if group_type:
        query = query.filter(PartyGroup.group_type == group_type)
    groups = database.session.execute(query.order_by(PartyGroup.group_type, PartyGroup.name)).scalars().all()
    return render_template("admin/party_groups.html", groups=groups, group_type=group_type)


@admin.route("/settings/party-groups/<group_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def editar_grupo_tercero(group_id: str):
    """Edita un tipo global de tercero."""
    _require_system_admin()
    group = database.session.get(PartyGroup, group_id)
    if not group:
        abort(404)
    if request.method == "POST":
        group.group_type = request.form.get("group_type") or group.group_type
        group.name = request.form.get("name") or ""
        group.description = request.form.get("description") or None
        group.is_active = request.form.get("is_active") is not None
        try:
            database.session.commit()
        except IntegrityError:
            database.session.rollback()
            flash(_("Ya existe un tipo de tercero con ese nombre."), "danger")
        else:
            flash(_("Tipo de tercero actualizado correctamente."), "success")
            return redirect(url_for(ADMIN_LISTA_GRUPOS_TERCEROS, group_type=group.group_type))
    groups = (
        database.session.execute(database.select(PartyGroup).order_by(PartyGroup.group_type, PartyGroup.name)).scalars().all()
    )
    return render_template("admin/party_groups.html", groups=groups, editing_group=group, group_type=group.group_type)


@admin.route("/settings/party-groups/<group_id>/toggle", methods=["POST"])
@login_required
@modulo_activo("admin")
def alternar_grupo_tercero(group_id: str):
    """Activa o desactiva un tipo global de tercero."""
    _require_system_admin()
    group = database.session.get(PartyGroup, group_id)
    if not group:
        abort(404)
    group.is_active = not group.is_active
    database.session.commit()
    flash(_("Estado del tipo de tercero actualizado correctamente."), "success")
    return redirect(url_for(ADMIN_LISTA_GRUPOS_TERCEROS, group_type=group.group_type))


@admin.route("/settings/tax-rules/<rule_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def editar_regla_fiscal(rule_id: str):
    """Edita una regla fiscal."""
    _require_system_admin()
    rule = get_tax_rule(rule_id)
    if rule is None:
        abort(404)
    assert rule is not None
    if request.method == "POST":
        try:
            update_tax_rule(rule, request.form)
            database.session.commit()
        except TaxRuleServiceError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
        else:
            flash(_("Regla fiscal actualizada correctamente."), "success")
            return redirect(url_for("admin.editar_regla_fiscal", rule_id=rule.id))
    rules = list_tax_rules()
    return render_template("admin/tax_rules.html", rules=rules, editing_rule=rule)


@admin.route("/settings/tax-rules/<rule_id>/delete", methods=["POST"])
@login_required
@modulo_activo("admin")
def eliminar_regla_fiscal(rule_id: str):
    """Elimina una regla fiscal."""
    _require_system_admin()
    rule = get_tax_rule(rule_id)
    if rule is None:
        abort(404)
    assert rule is not None
    delete_tax_rule(rule)
    database.session.commit()
    flash(_("Regla fiscal eliminada correctamente."), "success")
    return redirect(url_for("admin.lista_reglas_fiscales"))


@admin.route("/settings/ledger-mapping-rules", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_reglas_mapeo_libros():
    """Administra reglas activas de sustitución de cuentas por libro."""
    _require_system_admin()
    if request.method == "POST":
        try:
            create_ledger_mapping_rule(
                source_book=request.form.get("source_book") or "",
                target_book=request.form.get("target_book") or "",
                source_account_id=request.form.get("source_account_id") or "",
                target_account_id=request.form.get("target_account_id") or "",
                description=request.form.get("description") or None,
            )
        except LedgerMappingError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
        else:
            flash(_("Regla de mapeo creada correctamente."), "success")
            return redirect(url_for("admin.lista_reglas_mapeo_libros"))
    books = (
        database.session.execute(database.select(Book).order_by(Book.entity, Book.is_primary.desc(), Book.code))
        .scalars()
        .all()
    )
    accounts = database.session.execute(database.select(Accounts).order_by(Accounts.entity, Accounts.code)).scalars().all()
    return render_template(
        "admin/ledger_mapping_rules.html",
        rules=list_ledger_mapping_rules(),
        books=books,
        accounts=accounts,
    )


@admin.route("/settings/ledger-mapping-rules/<rule_id>/deactivate", methods=["POST"])
@login_required
@modulo_activo("admin")
def desactivar_regla_mapeo_libros(rule_id: str):
    """Desactiva una regla sin borrar la configuración histórica."""
    _require_system_admin()
    try:
        deactivate_ledger_mapping_rule(rule_id)
    except LedgerMappingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    else:
        flash(_("Regla de mapeo desactivada correctamente."), "success")
    return redirect(url_for("admin.lista_reglas_mapeo_libros"))


@admin.route("/settings/price-lists", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_precios():
    """Administra listas de precios."""
    _require_price_list_editor()
    if request.method == "POST":
        price_list = PriceList(
            name=request.form.get("name") or "",
            currency=request.form.get("currency") or None,
            company=request.form.get("company") or None,
            is_buying=bool(request.form.get("is_buying")),
            is_selling=bool(request.form.get("is_selling", "1")),
            is_default=bool(request.form.get("is_default")),
            is_active=bool(request.form.get("is_active", "1")),
        )
        _require_price_list_company_access(price_list)
        database.session.add(price_list)
        database.session.flush()
        if price_list.is_default and price_list.is_selling:
            database.session.execute(
                database.update(PriceList)
                .where(PriceList.id != price_list.id, PriceList.company == price_list.company, PriceList.is_selling.is_(True))
                .values(is_default=False)
            )
            for item in database.session.execute(
                database.select(Item).where(
                    Item.is_active.is_(True), Item.is_sale_item.is_(True), Item.standard_rate.is_not(None)
                )
            ).scalars():
                database.session.add(
                    ItemPrice(
                        item_code=item.code,
                        price_list_id=price_list.id,
                        uom=item.sale_uom or item.default_uom,
                        price=item.standard_rate,
                    )
                )
        database.session.commit()
        flash(_("Lista de precios creada correctamente."), "success")
        return redirect(url_for("admin.lista_precios"))
    price_lists = [
        price_list
        for price_list in database.session.execute(database.select(PriceList).order_by(PriceList.name)).scalars().all()
        if _can_manage_price_list(price_list)
    ]
    return render_template("admin/price_lists.html", price_lists=price_lists, titulo=_("Listas de Precios"))


@admin.route("/settings/item-prices", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def precios_item():
    """Administra precios por item."""
    _require_price_list_editor()
    if request.method == "POST":
        price_list = database.session.get(PriceList, request.form.get("price_list_id") or "")
        if not price_list:
            abort(404)
        _require_price_list_company_access(price_list)
        item_price = ItemPrice(
            item_code=request.form.get("item_code") or "",
            price_list_id=request.form.get("price_list_id") or "",
            uom=request.form.get("uom") or None,
            price=_decimal_form("price"),
            min_qty=_decimal_form("min_qty", "0"),
            valid_from=_date_form("valid_from"),
            valid_upto=_date_form("valid_upto"),
        )
        database.session.add(item_price)
        database.session.commit()
        flash(_("Precio de item creado correctamente."), "success")
        return redirect(url_for("admin.precios_item"))
    price_lists = [
        price_list
        for price_list in database.session.execute(
            database.select(PriceList).filter_by(is_active=True).order_by(PriceList.name)
        )
        .scalars()
        .all()
        if _can_manage_price_list(price_list)
    ]
    allowed_list_ids = {price_list.id for price_list in price_lists}
    item_prices = [
        item_price
        for item_price in database.session.execute(database.select(ItemPrice).order_by(ItemPrice.item_code)).scalars().all()
        if item_price.price_list_id in allowed_list_ids
    ]
    return render_template(
        "admin/item_prices.html", item_prices=item_prices, price_lists=price_lists, titulo=_("Precios por Item")
    )


@admin.route("/settings/item-prices/<item_price_id>", methods=["POST"])
@login_required
@modulo_activo("admin")
def actualizar_precio_item(item_price_id: str):
    """Actualiza un precio de catálogo sin crear una segunda tarifa."""
    _require_price_list_editor()
    item_price = database.session.get(ItemPrice, item_price_id)
    if not item_price:
        abort(404)
    price_list = database.session.get(PriceList, item_price.price_list_id)
    if not price_list:
        abort(404)
    _require_price_list_company_access(price_list)
    item_price.price = _decimal_form("price")
    item_price.min_qty = _decimal_form("min_qty", "0")
    item_price.valid_from = _date_form("valid_from")
    item_price.valid_upto = _date_form("valid_upto")
    database.session.commit()
    flash(_("Precio de item actualizado correctamente."), "success")
    return redirect(url_for("admin.precios_item"))


@admin.route("/settings/purchase-reconciliation", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def config_conciliacion_compras():
    """Administra la configuracion de conciliacion de compras por compania."""
    _require_system_admin()
    from cacao_accounting.database import Entity
    from cacao_accounting.compras.purchase_reconciliation_service import seed_matching_config_for_company

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()

    if request.method == "POST":
        company = request.form.get("company") or ""
        if not company:
            flash(_(DEBE_SELECCIONAR_COMPANIA_MSG), "danger")
            return redirect(url_for("admin.config_conciliacion_compras"))

        config = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company=company)
        ).scalar_one_or_none()
        if config is None:
            config = seed_matching_config_for_company(company)
            database.session.flush()

        config.matching_type = request.form.get("matching_type") or "3-way"
        config.price_tolerance_type = request.form.get("price_tolerance_type") or "percentage"
        config.price_tolerance_value = _decimal_form("price_tolerance_value")
        config.qty_tolerance_type = request.form.get("qty_tolerance_type") or "percentage"
        config.qty_tolerance_value = _decimal_form("qty_tolerance_value")
        config.require_purchase_order = bool(request.form.get("require_purchase_order"))
        config.bridge_account_required = bool(request.form.get("bridge_account_required"))
        config.auto_reconcile = bool(request.form.get("auto_reconcile"))
        config.allow_price_difference = bool(request.form.get("allow_price_difference"))
        default_accounts = get_company_default_accounts(company)
        if default_accounts is None:
            default_accounts = CompanyDefaultAccount(company=company)
            database.session.add(default_accounts)
        default_accounts.apply_advances_automatically = bool(request.form.get("apply_advances_automatically"))
        database.session.commit()
        flash(_("Configuracion de conciliacion de compras guardada correctamente."), "success")
        return redirect(url_for("admin.config_conciliacion_compras"))

    configs = (
        database.session.execute(database.select(PurchaseMatchingConfig).order_by(PurchaseMatchingConfig.company))
        .scalars()
        .all()
    )
    default_accounts = (
        database.session.execute(database.select(CompanyDefaultAccount).order_by(CompanyDefaultAccount.company))
        .scalars()
        .all()
    )
    advance_settings = {config.company: bool(config.apply_advances_automatically) for config in default_accounts}

    return render_template(
        "admin/purchase_reconciliation_config.html",
        configs=configs,
        companies=companies,
        advance_settings=advance_settings,
        titulo=_("Configuracion de Conciliacion de Compras"),
    )


@admin.route("/settings/purchase-sourcing", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def config_abastecimiento_compras():
    """Administra las reglas globales del comparativo de ofertas."""
    _require_system_admin()
    if request.method == "POST":
        try:
            minimum = int(request.form.get("minimum_offers") or "2")
            set_purchase_sourcing_config(bool(request.form.get("require_comparison")), minimum)
            database.session.commit()
            flash(_("Configuración de abastecimiento guardada correctamente."), "success")
        except ValueError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
        return redirect(url_for("admin.config_abastecimiento_compras"))
    return render_template(
        "admin/purchase_sourcing_config.html",
        config=get_purchase_sourcing_config(),
        titulo=_("Configuración de Abastecimiento"),
    )


@admin.route("/settings/sales-matching", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def config_conciliacion_ventas():
    """Administra la configuracion de matching de ventas por compania."""
    _require_system_admin()

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()

    if request.method == "POST":
        company = request.form.get("company") or ""
        if not company:
            flash(_(DEBE_SELECCIONAR_COMPANIA_MSG), "danger")
            return redirect(url_for("admin.config_conciliacion_ventas"))

        config = database.session.execute(database.select(SalesMatchingConfig).filter_by(company=company)).scalar_one_or_none()
        if config is None:
            config = SalesMatchingConfig(company=company)
            database.session.add(config)
            database.session.flush()

        config.matching_type = request.form.get("matching_type") or "3-way"
        config.price_tolerance_type = request.form.get("price_tolerance_type") or "percentage"
        config.price_tolerance_value = _decimal_form("price_tolerance_value")
        config.require_sales_order = bool(request.form.get("require_sales_order"))
        config.allow_price_difference = bool(request.form.get("allow_price_difference"))
        database.session.commit()
        flash(_("Configuracion de conciliacion de ventas guardada correctamente."), "success")
        return redirect(url_for("admin.config_conciliacion_ventas"))

    configs = (
        database.session.execute(database.select(SalesMatchingConfig).order_by(SalesMatchingConfig.company)).scalars().all()
    )

    return render_template(
        "admin/sales_matching_config.html",
        configs=configs,
        companies=companies,
        titulo=_("Configuracion de Conciliacion de Ventas"),
    )


@admin.route("/settings/budget-control", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def config_control_presupuestario():
    """Administra la configuración de control presupuestario por compañía."""
    _require_system_admin()
    from cacao_accounting.setup.repository import get_setup_value, set_setup_value

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    selected_company = request.values.get("company") or (companies[0].code if companies else "")

    if request.method == "POST":
        company = request.form.get("company") or ""
        if not company:
            flash(_("Debe seleccionar una compañía."), "danger")
            return redirect(url_for(ADMIN_CONTROL_PRESUPUESTARIO_ENDPOINT))

        enabled = request.form.get("enabled") == "on"
        action = request.form.get("action_on_exceeded") or "notify"

        if action not in BUDGET_CONTROL_VALID_ACTIONS:
            flash(_("Política de control presupuestario no válida."), "danger")
            return redirect(url_for(ADMIN_CONTROL_PRESUPUESTARIO_ENDPOINT, company=company))

        set_setup_value(f"budget_control_enabled_{company}", "1" if enabled else "0")
        set_setup_value(f"budget_control_action_{company}", action)

        database.session.commit()
        flash(_("Configuración de control presupuestario guardada correctamente."), "success")
        return redirect(url_for(ADMIN_CONTROL_PRESUPUESTARIO_ENDPOINT, company=company))

    enabled_val = get_setup_value(f"budget_control_enabled_{selected_company}", "0") == "1"
    action_val = get_setup_value(f"budget_control_action_{selected_company}", "notify")

    configs_list = []
    for comp in companies:
        c_enabled = get_setup_value(f"budget_control_enabled_{comp.code}", "0") == "1"
        c_action = get_setup_value(f"budget_control_action_{comp.code}", "notify")
        configs_list.append(
            {
                "company": comp.code,
                "enabled": c_enabled,
                "action": c_action,
            }
        )

    return render_template(
        "admin/budget_control_config.html",
        companies=companies,
        selected_company=selected_company,
        enabled=enabled_val,
        action=action_val,
        configs=configs_list,
        titulo=_("Control Presupuestario"),
    )


@admin.route("/settings/default-accounts", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def cuentas_predeterminadas():
    """Administra cuentas contables predeterminadas por compania."""
    _require_system_admin()
    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    selected_company = request.form.get("company") or request.args.get("company") or (companies[0].code if companies else "")

    if request.method == "POST":
        action = request.form.get("action") or "save"
        if not selected_company:
            flash(_(DEBE_SELECCIONAR_COMPANIA_MSG), "danger")
            return redirect(url_for(CUENTAS_PREDETERMINADAS))

        if action == "delete":
            config = get_company_default_accounts(selected_company)
            if config:
                database.session.delete(config)
                database.session.commit()
                flash(_("Configuracion de cuentas predeterminadas eliminada correctamente."), "success")
            return redirect(url_for(CUENTAS_PREDETERMINADAS, company=selected_company))

        values = {field: request.form.get(field) or None for field in DEFAULT_ACCOUNT_FIELDS}
        try:
            config = upsert_company_default_accounts(selected_company, values)
        except DefaultAccountError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
            return redirect(url_for(CUENTAS_PREDETERMINADAS, company=selected_company))
        config.apply_advances_automatically = bool(request.form.get("apply_advances_automatically"))
        database.session.commit()
        flash(_("Cuentas predeterminadas guardadas correctamente."), "success")
        return redirect(url_for(CUENTAS_PREDETERMINADAS, company=selected_company))

    config = get_company_default_accounts(selected_company) if selected_company else None
    configs = (
        database.session.execute(database.select(CompanyDefaultAccount).order_by(CompanyDefaultAccount.company))
        .scalars()
        .all()
    )

    return render_template(
        "admin/default_accounts.html",
        companies=companies,
        configs=configs,
        definitions=DEFAULT_ACCOUNT_DEFINITIONS,
        rows=default_account_rows(config),
        selected_company=selected_company,
        config=config,
        titulo=_("Cuentas por defecto"),
    )


@admin.route("/settings/users", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_usuarios():
    """Administra los usuarios del sistema."""
    _require_system_admin()
    if request.method == "POST":
        user_id = request.form.get("user_id")
        action = request.form.get("action")
        usuario = _obtener_usuario(user_id) if user_id else None

        if usuario is None:
            flash(USUARIO_NO_ENCONTRADO, "danger")
            return redirect(url_for(LISTA_USUARIOS))

        if action == "toggle":
            usuario.active = not bool(usuario.active)
            database.session.commit()
            estado = "habilitado" if usuario.active else "deshabilitado"
            flash(f"Usuario {usuario.user} {estado} correctamente.", "success")
            return redirect(url_for(LISTA_USUARIOS))

    usuarios = database.session.execute(database.select(User).order_by(User.user)).scalars().all()
    roles_por_usuario = {
        usuario.id: ", ".join([rol.name for rol in _obtener_roles_por_usuario(usuario.id)]) for usuario in usuarios
    }

    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios,
        roles_por_usuario=roles_por_usuario,
        can_create_user=_can_create_user(),
    )


@admin.route("/settings/users/new", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def crear_usuario():
    """Crea un nuevo usuario en el sistema."""
    _require_system_admin()
    if not _can_create_user():
        if request.method == "POST":
            abort(403)
        flash(DESKTOP_SINGLE_ADMIN_MESSAGE, "danger")
        return redirect(url_for(LISTA_USUARIOS))

    form = UserCreateForm()
    _populate_portal_choices(form)
    if form.validate_on_submit() and _validate_portal_fields(form) and _validar_creacion_usuario(form):
        nuevo_usuario = _crear_usuario_desde_form(form)
        database.session.add(nuevo_usuario)
        database.session.commit()
        flash("Usuario creado correctamente.", "success")
        return redirect(url_for(LISTA_USUARIOS))

    return render_template(
        "admin/usuario_form.html",
        form=form,
        titulo="Crear Usuario",
        accion="Nuevo Usuario",
        tiene_clave=True,
    )


@admin.route("/settings/users/<string:user_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def editar_usuario(user_id: str):
    """Edita los datos básicos de un usuario."""
    _require_system_admin()
    usuario = _obtener_usuario(user_id)
    if usuario is None:
        flash(USUARIO_NO_ENCONTRADO, "danger")
        return redirect(url_for(LISTA_USUARIOS))

    form = UserEditForm(obj=usuario)
    _populate_portal_choices(form)
    if form.validate_on_submit() and _validate_portal_fields(form) and _apply_user_edit(form, usuario):
        database.session.commit()
        flash("Usuario actualizado correctamente.", "success")
        return redirect(url_for(LISTA_USUARIOS))

    return render_template(
        "admin/usuario_form.html",
        form=form,
        titulo="Editar Usuario",
        accion="Actualizar Usuario",
        usuario=usuario,
        tiene_clave=False,
    )


@admin.route("/settings/users/<string:user_id>/roles", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def usuario_roles(user_id: str):
    """Asigna roles a un usuario."""
    _require_system_admin()
    usuario = _obtener_usuario(user_id)
    if usuario is None:
        flash(USUARIO_NO_ENCONTRADO, "danger")
        return redirect(url_for(LISTA_USUARIOS))

    if usuario.classification in ("customer", "supplier"):
        flash("Solo los usuarios de tipo 'system' pueden tener roles de acceso.", "warning")
        return redirect(url_for(LISTA_USUARIOS))

    roles = _obtener_roles_disponibles()
    form = UserRoleForm()
    form.roles.choices = [(rol.id, rol.name) for rol in roles]

    if request.method == "GET":
        form.roles.data = [rol.id for rol in _obtener_roles_por_usuario(usuario.id)]

    if form.validate_on_submit():
        seleccionado = [rol_id for rol_id in form.roles.data if rol_id]
        database.session.execute(delete(RolesUser).where(RolesUser.user_id == usuario.id))
        for rol_id in seleccionado:
            database.session.add(RolesUser(user_id=usuario.id, role_id=rol_id, active=True))
        database.session.commit()
        flash("Roles actualizados correctamente.", "success")
        return redirect(url_for(LISTA_USUARIOS))

    return render_template(
        "admin/usuario_roles.html",
        form=form,
        usuario=usuario,
    )


@admin.route("/settings/users/<string:user_id>/companies", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def usuario_companias(user_id: str):
    """Asigna el alcance de compañías a un usuario interno en Cloud."""
    _require_system_admin()
    if is_desktop_mode():
        abort(403)
    usuario = _obtener_usuario(user_id)
    if usuario is None:
        flash(USUARIO_NO_ENCONTRADO, "danger")
        return redirect(url_for(LISTA_USUARIOS))
    if usuario.classification in ("customer", "supplier"):
        flash("Solo los usuarios internos pueden tener compañías asignadas.", "warning")
        return redirect(url_for(LISTA_USUARIOS))

    form = UserCompanyAccessForm()
    companies = (
        database.session.execute(database.select(Entity).where(Entity.enabled.is_(True)).order_by(Entity.code)).scalars().all()
    )
    form.companies.choices = [
        (company.code, f"{company.code} - {company.name or company.company_name}") for company in companies
    ]
    if request.method == "GET":
        form.companies.data = list(
            database.session.execute(
                database.select(UserCompanyAccess.company_code)
                .where(UserCompanyAccess.user_id == usuario.id)
                .order_by(UserCompanyAccess.company_code)
            ).scalars()
        )
    if form.validate_on_submit():
        selected = set(form.companies.data or [])
        database.session.execute(delete(UserCompanyAccess).where(UserCompanyAccess.user_id == usuario.id))
        database.session.add_all(
            [UserCompanyAccess(user_id=usuario.id, company_code=company_code) for company_code in selected]
        )
        database.session.commit()
        flash("Compañías actualizadas correctamente.", "success")
        return redirect(url_for(LISTA_USUARIOS))
    return render_template("admin/usuario_companias.html", form=form, usuario=usuario)


@admin.route("/settings/users/<string:user_id>/password", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def usuario_password(user_id: str):
    """Cambia la contraseña de un usuario."""
    _require_system_admin()
    usuario = _obtener_usuario(user_id)
    if usuario is None:
        flash(USUARIO_NO_ENCONTRADO, "danger")
        return redirect(url_for(LISTA_USUARIOS))

    form = UserPasswordForm()
    if form.validate_on_submit():
        if not helpers.validar_clave_segura(form.password.data):
            form.password.errors.append(
                "Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos."
            )
        else:
            usuario.password = proteger_passwd(form.password.data)
            database.session.commit()
            flash("Contraseña actualizada correctamente.", "success")
            return redirect(url_for(LISTA_USUARIOS))

    return render_template(
        "admin/usuario_password.html",
        form=form,
        usuario=usuario,
    )


@admin.route("/settings/roles")
@login_required
@modulo_activo("admin")
def lista_roles():
    """Lista los roles disponibles en el sistema."""
    _require_system_admin()
    roles = database.session.execute(database.select(Roles).order_by(Roles.name)).scalars().all()
    return render_template("admin/roles.html", roles=roles)


@admin.route("/settings/roles/new", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def crear_rol():
    """Crea un nuevo rol."""
    _require_system_admin()
    form = RoleForm()
    if form.validate_on_submit():
        existe_rol = database.session.execute(database.select(Roles).filter_by(name=form.name.data)).scalar_one_or_none()
        if existe_rol is not None:
            form.name.errors.append("El nombre del rol ya está en uso.")
        else:
            nuevo_rol = Roles(name=form.name.data, note=form.note.data or "")
            database.session.add(nuevo_rol)
            database.session.commit()
            flash("Rol creado correctamente.", "success")
            return redirect(url_for(LISTA_ROLES))

    return render_template(
        "admin/rol_form.html",
        form=form,
        titulo="Crear Rol",
        accion="Guardar rol",
    )


@admin.route("/settings/roles/<string:role_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def editar_rol(role_id: str):
    """Edita un rol existente."""
    _require_system_admin()
    rol = _obtener_rol(role_id)
    if rol is None:
        flash("Rol no encontrado.", "danger")
        return redirect(url_for(LISTA_ROLES))

    form = RoleForm(obj=rol)
    if form.validate_on_submit():
        existe_rol = database.session.execute(
            database.select(Roles).filter(Roles.name == form.name.data).filter(Roles.id != rol.id)
        ).scalar_one_or_none()
        if existe_rol is not None:
            form.name.errors.append("El nombre del rol ya está en uso.")
        else:
            rol.name = form.name.data
            rol.note = form.note.data or ""
            database.session.commit()
            flash("Rol actualizado correctamente.", "success")
            return redirect(url_for(LISTA_ROLES))

    return render_template(
        "admin/rol_form.html",
        form=form,
        titulo="Editar Rol",
        accion="Actualizar rol",
        rol=rol,
    )


@admin.route("/settings/roles/<string:role_id>/permissions", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def rol_permisos(role_id: str):
    """Asigna permisos a un rol por módulo."""
    _require_system_admin()
    rol = _obtener_rol(role_id)
    if rol is None:
        flash("Rol no encontrado.", "danger")
        return redirect(url_for(LISTA_ROLES))

    modulos = _obtener_modulos_disponibles()
    acciones = [
        ("access", "Acceso"),
        ("update", "Actualizar"),
        ("set_null", "Anular"),
        ("approve", "Autorizar"),
        ("bi", "BI"),
        ("close", "Cerrar"),
        ("setup", "Configurar"),
        ("view", "Consultar"),
        ("create", "Crear"),
        ("edit", "Editar"),
        ("delete", "Eliminar"),
        ("import_", "Importar"),
        ("report", "Reportes"),
        ("request", "Solicitar"),
        ("validate", "Validar"),
    ]
    permisos_existentes = {
        perm.module_id: {accion: getattr(perm, accion, False) for accion, _label in acciones}
        for perm in _obtener_permisos_por_rol(role_id)
    }

    if request.method == "POST":
        database.session.execute(database.delete(RolesAccess).where(RolesAccess.rol_id == role_id))
        for modulo in modulos:
            permiso_kwargs = {"rol_id": role_id, "module_id": modulo.id}
            for accion, _label in acciones:
                permiso_kwargs[accion] = request.form.get(f"perm_{modulo.id}_{accion}") == "on"
            if any(permiso_kwargs[action] for action, _label in acciones):
                database.session.add(RolesAccess(**permiso_kwargs))
        database.session.commit()
        flash("Permisos del rol actualizados correctamente.", "success")
        return redirect(url_for(LISTA_ROLES))

    return render_template(
        "admin/rol_permisos.html",
        rol=rol,
        modulos=modulos,
        permisos_existentes=permisos_existentes,
        acciones=acciones,
    )


@admin.route("/settings/approval-matrix", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def config_approval_matrix():
    """Administra la matriz de aprobación de documentos por compañía."""
    _require_system_admin()
    from cacao_accounting.setup.repository import get_setup_value, set_setup_value

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    selected_company = request.values.get("company") or (companies[0].code if companies else "")

    redirect_response = _handle_approval_matrix_post(set_setup_value, selected_company)
    if redirect_response is not None:
        return redirect_response

    global_enabled = get_setup_value(f"approval_engine_enabled_{selected_company}", "0") == "1"
    stmt = (
        database.select(ApprovalMatrix)
        .filter_by(company_id=selected_company)
        .order_by(ApprovalMatrix.document_type, ApprovalMatrix.approval_level)
    )
    rules = database.session.execute(stmt).scalars().all()

    roles = database.session.execute(database.select(Roles).order_by(Roles.name)).scalars().all()
    users = database.session.execute(database.select(User).order_by(User.user)).scalars().all()

    from cacao_accounting.document_flow.registry import DOCUMENT_TYPES

    doc_types = [(k, v.label) for k, v in DOCUMENT_TYPES.items()]

    return render_template(
        "admin/approval_matrix.html",
        companies=companies,
        selected_company=selected_company,
        global_enabled=global_enabled,
        rules=rules,
        roles=roles,
        users=users,
        doc_types=doc_types,
        titulo=_("Matriz de Aprobaciones"),
    )


@admin.route("/me/pending-approvals", methods=["GET", "POST"])
@login_required
def pending_approvals():
    """Listado de documentos que requieren la aprobación del usuario actual."""
    from cacao_accounting.approval_engine import ApprovalEngine, get_model_class
    from cacao_accounting.database import ApprovalRequest, User
    from cacao_accounting.document_flow.registry import DOCUMENT_TYPES

    if request.method == "POST":
        _process_pending_approval_post(ApprovalRequest, get_model_class)
        return redirect(url_for("admin.pending_approvals"))

    stmt_all = (
        database.select(ApprovalRequest)
        .filter(ApprovalRequest.status.startswith("Pending"))
        .order_by(ApprovalRequest.created_at.desc())
    )
    all_pending = database.session.execute(stmt_all).scalars().all()

    my_pending = [_pending_approval_info(req, get_model_class, ApprovalEngine, User, DOCUMENT_TYPES) for req in all_pending]
    my_pending = [item for item in my_pending if item is not None]

    return render_template(
        "admin/pending_approvals.html",
        pending_list=my_pending,
        titulo=_("Mis Aprobaciones Pendientes"),
    )


@admin.route("/settings/session-security", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def session_security_settings():
    """Administra la configuración de seguridad de sesión y dispositivos reconocidos."""
    _require_system_admin()
    if is_desktop_mode():
        abort(403)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle":
            if not smtp_is_configured():
                flash(
                    _("Debe configurar el servidor SMTP antes de activar la protección de orígenes."),
                    "danger",
                )
                return redirect(url_for("admin.session_security_settings"))
            new_state = request.form.get("enabled") == "on"
            set_session_security_enabled(new_state)
            database.session.commit()
            estado = _("activada") if new_state else _("desactivada")
            flash(_("Protección de orígenes {}.").format(estado), "success")
            return redirect(url_for("admin.session_security_settings"))
        if action == "revoke":
            device_id = request.form.get("device_id")
            if device_id and revocar_dispositivo(device_id):
                database.session.commit()
                flash(_("Dispositivo revocado correctamente."), "success")
            return redirect(url_for("admin.session_security_settings"))
        if action == "unlock":
            user_id = request.form.get("user_id")
            if user_id and desbloquear_cuenta_usuario(user_id):
                database.session.commit()
                flash(_("Cuenta desbloqueada correctamente."), "success")
            return redirect(url_for("admin.session_security_settings"))

    enabled = is_session_security_enabled()
    smtp_ok = smtp_is_configured()
    dispositivos = listar_todos_dispositivos()
    cuentas_bloqueadas = listar_cuentas_bloqueadas()

    return render_template(
        "admin/session_security.html",
        enabled=enabled,
        smtp_configured=smtp_ok,
        dispositivos=dispositivos,
        cuentas_bloqueadas=cuentas_bloqueadas,
        titulo=_("Seguridad de Sesión"),
    )
