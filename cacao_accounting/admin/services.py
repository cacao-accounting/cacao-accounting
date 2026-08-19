"""Modulo administrativo."""

from decimal import Decimal

from datetime import date

from flask import Blueprint, abort, flash, redirect, request, url_for

from flask_login import current_user


from sqlalchemy.exc import SQLAlchemyError

from cacao_accounting.auth import helpers, proteger_passwd

from cacao_accounting.auth.forms import (
    UserCreateForm,
    UserEditForm,
)


from cacao_accounting.database import (
    ApprovalMatrix,
    Entity,
    Modules,
    Party,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    database,
)

from cacao_accounting.exceptions import flash_error


from cacao_accounting.document_flow.status import _


from cacao_accounting.runtime_mode import is_desktop_mode

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


def _send_email_test():
    """Send the SMTP test message and report its result to the administrator."""
    from cacao_accounting.messaging.email import EmailError, send_email

    test_recipient = request.form.get("test_recipient")
    if not test_recipient:
        flash(_("Debe especificar un correo destinatario para la prueba."), "danger")
        return
    try:
        send_email(
            to_email=test_recipient.strip(),
            subject=_("Correo de prueba de Cacao Accounting"),
            body=_("Este es un correo de prueba para verificar la configuración de SMTP en Cacao Accounting."),
            is_html=False,
        )
        flash(_("Correo de prueba enviado correctamente."), "success")
    except EmailError as exc:
        flash(_(str(exc)), "danger")


def _save_email_settings() -> None:
    """Persist the SMTP settings submitted by the administrator."""
    from cacao_accounting.messaging.email import set_smtp_setting

    settings = {
        "smtp_server": (request.form.get("smtp_server") or "").strip(),
        "smtp_port": (request.form.get("smtp_port") or "587").strip(),
        "smtp_user": (request.form.get("smtp_user") or "").strip(),
        "smtp_use_tls": "true" if request.form.get("smtp_use_tls") == "on" else "false",
        "smtp_from_email": (request.form.get("smtp_from_email") or "").strip(),
        "disable_transaction_emails": "true" if request.form.get("disable_transaction_emails") == "on" else "false",
    }
    for key, value in settings.items():
        set_smtp_setting(key, value)
    new_password = request.form.get("smtp_password")
    if new_password:
        set_smtp_setting("smtp_password", new_password.strip())
    database.session.commit()


def _email_settings_values() -> dict[str, str]:
    """Load SMTP settings with the UI defaults applied."""
    from cacao_accounting.messaging.email import get_smtp_setting

    return {
        "smtp_server": get_smtp_setting("smtp_server") or "",
        "smtp_port": get_smtp_setting("smtp_port") or "587",
        "smtp_user": get_smtp_setting("smtp_user") or "",
        "smtp_use_tls": get_smtp_setting("smtp_use_tls") or "true",
        "smtp_from_email": get_smtp_setting("smtp_from_email") or "",
        "disable_transaction_emails": get_smtp_setting("disable_transaction_emails") or "false",
    }


def _obtener_usuario(usuario_id: str) -> User | None:
    """Devuelve un usuario por su identificador."""
    return database.session.get(User, usuario_id)


def _populate_portal_choices(form: UserCreateForm | UserEditForm) -> None:
    """Populate company and party choices used by portal user forms."""
    companies = database.session.execute(database.select(Entity).where(Entity.enabled.is_(True))).scalars().all()
    form.company.choices = [(company.code, company.company_name) for company in companies]
    parties = database.session.execute(database.select(Party).where(Party.is_active.is_(True))).scalars().all()
    form.party_id.choices = [(party.id, party.name) for party in parties]


def _validate_portal_fields(form: UserCreateForm | UserEditForm) -> bool:
    """Validate party, company and party classification for portal identities."""
    if form.classification.data not in {"customer", "supplier"}:
        return True
    valid = True
    if not form.party_id.data:
        form.party_id.errors.append("Los usuarios de portal requieren un tercero asociado.")
        valid = False
    if not form.company.data:
        form.company.errors.append("Los usuarios de portal requieren una compañía asociada.")
        valid = False
    if not valid:
        return False
    party = database.session.get(Party, form.party_id.data)
    matches_type = party and (
        (form.classification.data == "customer" and party.is_customer)
        or (form.classification.data == "supplier" and party.is_supplier)
    )
    if not matches_type:
        form.party_id.errors.append("El tercero no corresponde a la clasificación del portal.")
        return False
    return True


def _user_count() -> int:
    """Return the number of users currently stored."""
    return int(database.session.execute(database.select(database.func.count(User.id))).scalar() or 0)


def _can_create_user() -> bool:
    """Return whether the current runtime allows creating another user."""
    return not (is_desktop_mode() and _user_count() >= 1)


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


def _crear_usuario_desde_form(form: UserCreateForm) -> User:
    """Construye una instancia de usuario a partir del formulario."""
    return User(
        user=form.usuario.data,
        name=form.name.data or None,
        name2=form.name2.data or None,
        last_name=form.last_name.data or None,
        last_name2=form.last_name2.data or None,
        e_mail=form.e_mail.data or None,
        phone=form.phone.data or None,
        classification=form.classification.data or None,
        party_id=form.party_id.data or None,
        company=form.company.data or None,
        active=bool(form.active.data),
        password=proteger_passwd(form.password.data),
    )


def _validar_creacion_usuario(form: UserCreateForm) -> bool:
    """Valida la creación de un usuario nuevo y registra errores en el formulario."""
    existen_usuario = database.session.execute(database.select(User).filter_by(user=form.usuario.data)).scalar_one_or_none()
    existe_email = None
    if form.e_mail.data:
        existe_email = database.session.execute(database.select(User).filter_by(e_mail=form.e_mail.data)).scalar_one_or_none()

    valid_password = helpers.validar_clave_segura(form.password.data)
    match (existen_usuario, existe_email, valid_password):
        case (usuario, _, _) if usuario is not None:
            form.usuario.errors.append("El nombre de usuario ya está en uso.")
        case (_, correo, _) if correo is not None:
            form.e_mail.errors.append("El correo electrónico ya está en uso.")
        case (_, _, False):
            form.password.errors.append(
                "Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos."
            )
        case _:
            return True
    return False


def _apply_user_edit(form, usuario) -> bool:
    """Validate uniqueness and apply editable user fields."""
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
        return False
    if existe_email is not None:
        form.e_mail.errors.append("El correo electrónico ya está en uso.")
        return False

    usuario.user = form.usuario.data
    usuario.name = form.name.data or None
    usuario.name2 = form.name2.data or None
    usuario.last_name = form.last_name.data or None
    usuario.last_name2 = form.last_name2.data or None
    usuario.e_mail = form.e_mail.data or None
    usuario.phone = form.phone.data or None
    new_classification = form.classification.data or None
    if new_classification in {"customer", "supplier"} and not form.party_id.data:
        form.party_id.errors.append("Los usuarios de portal requieren un tercero asociado.")
        return False
    if new_classification in {"customer", "supplier"} and not form.company.data:
        form.company.errors.append("Los usuarios de portal requieren una compañía asociada.")
        return False
    if (
        new_classification in {"customer", "supplier"}
        and database.session.execute(database.select(RolesUser).filter_by(user_id=usuario.id)).first()
    ):
        form.classification.errors.append("Retire los roles antes de convertir el usuario en portal.")
        return False
    usuario.classification = new_classification
    usuario.party_id = form.party_id.data or None
    usuario.company = form.company.data or None
    usuario.active = bool(form.active.data)
    return True


def _handle_approval_matrix_post(set_setup_value, selected_company: str):
    """Procesa las acciones POST de la matriz de aprobaciones."""
    action = request.form.get("action")
    company = request.form.get("company") or selected_company
    if request.method != "POST":
        return None
    if action == "save_global":
        set_setup_value(f"approval_engine_enabled_{company}", "1" if request.form.get("enabled") == "on" else "0")
        database.session.commit()
        flash(_("Configuración global de aprobación guardada correctamente."), "success")
    elif action == "add_rule":
        database.session.add(_approval_rule_from_form(company))
        database.session.commit()
        flash(_("Regla de aprobación creada correctamente."), "success")
    elif action == "delete_rule":
        rule = database.session.get(ApprovalMatrix, request.form.get("rule_id"))
        if rule:
            database.session.delete(rule)
            database.session.commit()
            flash(_("Regla de aprobación eliminada."), "success")
    else:
        return None
    return redirect(url_for(ADMIN_APPROVAL_MATRIX_ENDPOINT, company=company))


def _approval_rule_from_form(company: str) -> ApprovalMatrix:
    """Construye una regla de aprobación desde el formulario administrativo."""
    max_amount = request.form.get("max_amount")
    return ApprovalMatrix(
        company_id=company,
        document_type=request.form.get("document_type") or "",
        role_id=request.form.get("role_id") or None,
        user_id=request.form.get("user_id") or None,
        min_amount=Decimal(request.form.get("min_amount") or "0"),
        max_amount=Decimal(max_amount) if max_amount and max_amount.strip() else None,
        approval_level=int(request.form.get("approval_level") or "1"),
        enabled=True,
    )


def _process_approval_action(action, document, comments):
    """Procesar acción de aprobación o rechazo de un documento."""
    from cacao_accounting.approval_engine import ApprovalEngine

    if action == "approve":
        try:
            ApprovalEngine.approve(document, current_user, comments)
            database.session.commit()
            flash(_("Documento aprobado con éxito."), "success")
        except (SQLAlchemyError, ValueError) as exc:
            database.session.rollback()
            flash_error(exc)
    elif action == "reject":
        try:
            ApprovalEngine.reject(document, current_user, comments)
            database.session.commit()
            flash(_("Documento rechazado con éxito."), "warning")
        except (SQLAlchemyError, ValueError) as exc:
            database.session.rollback()
            flash_error(exc)


def _process_pending_approval_post(approval_request, get_model_class) -> None:
    """Procesa la acción enviada desde el listado de aprobaciones."""
    req = database.session.get(approval_request, request.form.get("request_id"))
    if not req:
        return
    document = database.session.get(get_model_class(req.document_type), req.document_id)
    if document:
        _process_approval_action(request.form.get("action"), document, request.form.get("comments") or None)


def _pending_approval_info(req, get_model_class, approval_engine, user_model, document_types):
    """Construye la información visible de una solicitud aprobable."""
    try:
        document = database.session.get(get_model_class(req.document_type), req.document_id)
        if not document or not approval_engine.can_approve(document, current_user):
            return None
        doc_info = document_types.get(req.document_type)
        detail_url = (
            url_for(doc_info.detail_endpoint, **{doc_info.detail_arg: req.document_id})
            if doc_info and doc_info.detail_endpoint
            else "#"
        )
        requester = database.session.get(user_model, req.requested_by)
        return {
            "request": req,
            "document": document,
            "label": doc_info.label if doc_info else req.document_type,
            "detail_url": detail_url,
            "requester_name": (requester.name or requester.user) if requester else req.requested_by,
            "amount": approval_engine.get_document_amount(document),
            "doc_no": getattr(document, "document_no", None) or getattr(document, "id", None) or req.document_id,
        }
    except (SQLAlchemyError, AttributeError, KeyError):
        return None
