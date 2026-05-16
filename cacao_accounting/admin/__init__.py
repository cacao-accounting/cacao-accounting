# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo administrativo."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from decimal import Decimal
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import delete

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import helpers, proteger_passwd
from cacao_accounting.auth.forms import (
    RoleForm,
    UserCreateForm,
    UserEditForm,
    UserPasswordForm,
    UserRoleForm,
)
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.database import (
    CompanyDefaultAccount,
    Entity,
    ItemPrice,
    Modules,
    PriceList,
    PurchaseMatchingConfig,
    Roles,
    RolesAccess,
    RolesUser,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    User,
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

admin = Blueprint("admin", __name__, template_folder="templates")

# Constants for duplicated literals
LISTA_MODULOS = "admin.lista_modulos"
CUENTAS_PREDETERMINADAS = "admin.cuentas_predeterminadas"
USUARIO_NO_ENCONTRADO = "Usuario no encontrado."
LISTA_USUARIOS = "admin.lista_usuarios"
LISTA_ROLES = "admin.lista_roles"


def _require_system_admin() -> None:
    """Restringe configuracion global al administrador del sistema."""
    if not current_user or not current_user.is_authenticated:
        abort(403)
    if getattr(current_user, "classification", None) == "admin":
        return
    admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one_or_none()
    if (
        admin_role
        and database.session.execute(
            database.select(RolesUser).filter_by(user_id=current_user.id, role_id=admin_role.id)
        ).scalar_one_or_none()
    ):
        return
    abort(403)


def _decimal_form(name: str, default: str = "0") -> Decimal:
    value = request.form.get(name)
    decimal_text = value if value not in (None, "") else default
    return Decimal(str(decimal_text))


def _date_form(name: str) -> date | None:
    value = request.form.get(name)
    return date.fromisoformat(value) if value else None


@admin.route("/admin")
@admin.route("/ajustes")
@admin.route("/administracion")
@admin.route("/configuracion")
@admin.route("/settings")
@login_required
@modulo_activo("admin")
def admin_():
    """Definición del modulo administrativo."""
    return render_template("admin.html")


@admin.route("/settings/modules", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_modulos():
    """Administra los módulos instalados en el sistema."""
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


@admin.route("/settings/price-lists", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_precios():
    """Administra listas de precios."""
    _require_system_admin()
    if request.method == "POST":
        price_list = PriceList(
            name=request.form.get("name") or "",
            currency=request.form.get("currency") or None,
            company=request.form.get("company") or None,
            is_buying=bool(request.form.get("is_buying")),
            is_selling=bool(request.form.get("is_selling", "1")),
            is_active=bool(request.form.get("is_active", "1")),
        )
        database.session.add(price_list)
        database.session.commit()
        flash(_("Lista de precios creada correctamente."), "success")
        return redirect(url_for("admin.lista_precios"))
    price_lists = database.session.execute(database.select(PriceList).order_by(PriceList.name)).scalars().all()
    return render_template("admin/price_lists.html", price_lists=price_lists, titulo=_("Listas de Precios"))


@admin.route("/settings/item-prices", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def precios_item():
    """Administra precios por item."""
    _require_system_admin()
    if request.method == "POST":
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
    item_prices = database.session.execute(database.select(ItemPrice).order_by(ItemPrice.item_code)).scalars().all()
    price_lists = (
        database.session.execute(database.select(PriceList).filter_by(is_active=True).order_by(PriceList.name)).scalars().all()
    )
    return render_template(
        "admin/item_prices.html", item_prices=item_prices, price_lists=price_lists, titulo=_("Precios por Item")
    )


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
            flash(_("Debe seleccionar una compania."), "danger")
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
        database.session.commit()
        flash(_("Configuracion de conciliacion de compras guardada correctamente."), "success")
        return redirect(url_for("admin.config_conciliacion_compras"))

    configs = (
        database.session.execute(database.select(PurchaseMatchingConfig).order_by(PurchaseMatchingConfig.company))
        .scalars()
        .all()
    )

    return render_template(
        "admin/purchase_reconciliation_config.html",
        configs=configs,
        companies=companies,
        titulo=_("Configuracion de Conciliacion de Compras"),
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
            flash(_("Debe seleccionar una compania."), "danger")
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
            upsert_company_default_accounts(selected_company, values)
        except DefaultAccountError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
            return redirect(url_for(CUENTAS_PREDETERMINADAS, company=selected_company))
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


def _obtener_usuario(usuario_id: str) -> User | None:
    """Devuelve un usuario por su identificador."""
    return database.session.get(User, usuario_id)


def _obtener_roles_disponibles() -> list[Roles]:
    """Lista los roles disponibles en el sistema."""
    return list(database.session.execute(database.select(Roles).order_by(Roles.name)).scalars().all())


def _obtener_roles_por_usuario(usuario_id: str) -> list[Roles]:
    """Devuelve los roles asignados a un usuario."""
    return list(
        database.session.execute(
            database.select(Roles).join(RolesUser, Roles.id == RolesUser.role_id).filter(RolesUser.user_id == usuario_id)
        )
        .scalars()
        .all()
    )


def _obtener_rol(role_id: str) -> Roles | None:
    """Devuelve un rol por su identificador."""
    return database.session.get(Roles, role_id)


def _obtener_permisos_por_rol(role_id: str) -> list[RolesAccess]:
    """Devuelve permisos asignados a un rol."""
    return list(database.session.execute(database.select(RolesAccess).filter_by(rol_id=role_id)).scalars().all())


def _obtener_modulos_disponibles() -> list[Modules]:
    """Devuelve los modulos registrados en el sistema."""
    return list(database.session.execute(database.select(Modules).order_by(Modules.module)).scalars().all())


@admin.route("/settings/users", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def lista_usuarios():
    """Administra los usuarios del sistema."""
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
    )


@admin.route("/settings/users/new", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def crear_usuario():
    """Crea un nuevo usuario en el sistema."""
    form = UserCreateForm()
    if form.validate_on_submit():
        existen_usuario = database.session.execute(
            database.select(User).filter_by(user=form.usuario.data)
        ).scalar_one_or_none()
        existe_email = None
        if form.e_mail.data:
            existe_email = database.session.execute(
                database.select(User).filter_by(e_mail=form.e_mail.data)
            ).scalar_one_or_none()

        if existen_usuario is not None:
            form.usuario.errors.append("El nombre de usuario ya está en uso.")
        elif existe_email is not None:
            form.e_mail.errors.append("El correo electrónico ya está en uso.")
        elif not helpers.validar_clave_segura(form.password.data):
            form.password.errors.append(
                "Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos."
            )
        else:
            nuevo_usuario = User(
                user=form.usuario.data,
                name=form.name.data or None,
                name2=form.name2.data or None,
                last_name=form.last_name.data or None,
                last_name2=form.last_name2.data or None,
                e_mail=form.e_mail.data or None,
                phone=form.phone.data or None,
                classification=form.classification.data or None,
                active=bool(form.active.data),
                password=helpers.proteger_passwd(form.password.data),
            )
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
    usuario = _obtener_usuario(user_id)
    if usuario is None:
        flash(USUARIO_NO_ENCONTRADO, "danger")
        return redirect(url_for(LISTA_USUARIOS))

    form = UserEditForm(obj=usuario)
    if form.validate_on_submit():
        existe_usuario = database.session.execute(
            database.select(User).filter(User.user == form.usuario.data).filter(User.id != usuario.id)
        ).scalar_one_or_none()
        existe_email = None
        if form.e_mail.data:
            existe_email = database.session.execute(
                database.select(User).filter(User.e_mail == form.e_mail.data).filter(User.id != usuario.id)
            ).scalar_one_or_none()

        if existe_usuario is not None:
            form.usuario.errors.append("El nombre de usuario ya está en uso.")
        elif existe_email is not None:
            form.e_mail.errors.append("El correo electrónico ya está en uso.")
        else:
            usuario.user = form.usuario.data
            usuario.name = form.name.data or None
            usuario.name2 = form.name2.data or None
            usuario.last_name = form.last_name.data or None
            usuario.last_name2 = form.last_name2.data or None
            usuario.e_mail = form.e_mail.data or None
            usuario.phone = form.phone.data or None
            usuario.classification = form.classification.data or None
            usuario.active = bool(form.active.data)
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
    usuario = _obtener_usuario(user_id)
    if usuario is None:
        flash(USUARIO_NO_ENCONTRADO, "danger")
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


@admin.route("/settings/users/<string:user_id>/password", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def usuario_password(user_id: str):
    """Cambia la contraseña de un usuario."""
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
    roles = database.session.execute(database.select(Roles).order_by(Roles.name)).scalars().all()
    return render_template("admin/roles.html", roles=roles)


@admin.route("/settings/roles/new", methods=["GET", "POST"])
@login_required
@modulo_activo("admin")
def crear_rol():
    """Crea un nuevo rol."""
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
