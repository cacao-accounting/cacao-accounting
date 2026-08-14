# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Blueprint de Confirmación de Saldos."""

import hashlib
import json
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, session
from flask_login import current_user, login_required
from sqlalchemy import select

from cacao_accounting.database import (
    database,
    BalanceConfirmation,
    BalanceConfirmationInvitation,
    Entity,
    Party,
    Contact,
    PartyContact,
)
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting.decorators import modulo_activo, exige_acceso_compania
from cacao_accounting.contabilidad.balance_confirmation import (
    create_balance_confirmation,
    prepare_invitation_token,
)
from cacao_accounting.messaging.email import send_email, EmailError
from cacao_accounting.audit_trail_service import (
    log_balance_confirmation_event,
    format_document_timeline,
)
from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

balance_confirmations_bp = Blueprint("balance_confirmations", __name__)


@balance_confirmations_bp.before_request
def check_desktop_mode():
    """Rechaza cualquier uso de esta funcionalidad en modo Desktop."""
    if is_desktop_mode():
        abort(403)


# --- INTERNAL VIEWS & ENDPOINTS (Require authentication and accounting module) ---


@balance_confirmations_bp.route("/accounting/balance-confirmations/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
def crear_confirmacion_form():
    """Formulario para solicitar una nueva confirmación de saldo."""
    party_id = request.args.get("party_id")
    party_type = request.args.get("party_type", "customer")  # customer | supplier

    party = database.session.get(Party, party_id) if party_id else None
    if not party:
        flash("Debe seleccionar un cliente o proveedor válido.", "warning")
        if party_type == "customer":
            return redirect(url_for("ventas.ventas_cliente_lista"))
        else:
            return redirect(url_for("compras.compras_proveedor_lista"))

    # Restringir la lista de compañías a aquellas para las que el usuario tenga acceso "crear"
    all_companies = obtener_lista_entidades_por_id_razonsocial()
    companies = []
    for code, name in all_companies:
        try:
            exige_acceso_compania("accounting", code, "crear")
            companies.append((code, name))
        except Exception:
            continue

    # Pre-cargar correos de contactos del cliente/proveedor
    contact_stmt = (
        select(Contact)
        .join(PartyContact, PartyContact.contact_id == Contact.id)
        .where(PartyContact.party_id == party_id, Contact.is_active.is_(True))
    )
    contacts = database.session.execute(contact_stmt).scalars().all()
    suggested_emails = [c.email for c in contacts if c.email]
    if party.primary_email and party.primary_email not in suggested_emails:
        suggested_emails.insert(0, party.primary_email)

    if request.method == "POST":
        company_id = request.form.get("company_id")
        cutoff_date_str = request.form.get("cutoff_date")
        emails_raw = request.form.getlist("emails") or request.form.get("emails_text", "").split(",")

        # Validar parámetros obligatorios
        if not company_id or not cutoff_date_str:
            flash("Debe seleccionar una compañía y fecha de corte.", "danger")
            return redirect(request.url)

        # Enforzar el acceso del usuario para la compañía seleccionada
        exige_acceso_compania("accounting", company_id, "crear")

        try:
            cutoff_date = date.fromisoformat(cutoff_date_str)
        except ValueError:
            flash("Fecha de corte no válida.", "danger")
            return redirect(request.url)

        if cutoff_date > date.today():
            flash("La fecha de corte no puede ser una fecha futura.", "danger")
            return redirect(request.url)

        # Filtrar y validar correos
        emails = []
        for e in emails_raw:
            clean_email = e.strip().lower()
            if clean_email and "@" in clean_email:
                if clean_email not in emails:
                    emails.append(clean_email)

        if not emails:
            flash("Debe indicar al menos una dirección de correo electrónico válida.", "danger")
            return redirect(request.url)

        try:
            confirmation = create_balance_confirmation(
                company_id=company_id,
                party_id=party_id,
                party_type=party_type,
                cutoff_date=cutoff_date,
                emails=emails,
                created_by_user_id=current_user.id,
            )
            database.session.commit()
            flash("Borrador de confirmación de saldo creado correctamente.", "success")
            return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation.id))
        except ValueError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
            return redirect(request.url)
        except Exception as exc:
            database.session.rollback()
            flash(str(exc), "danger")
            return redirect(request.url)

    return render_template(
        "admin/balance_confirmation_new.html",
        party=party,
        party_type=party_type,
        companies=companies,
        suggested_emails=suggested_emails,
        today=date.today().isoformat(),
    )


@balance_confirmations_bp.route("/accounting/balance-confirmations/<confirmation_id>")
@login_required
@modulo_activo("accounting")
def ver_confirmacion(confirmation_id: str):
    """Muestra el detalle interno y snapshot de una confirmación de saldo."""
    confirmation = database.session.get(BalanceConfirmation, confirmation_id)
    if not confirmation:
        abort(404)

    # Validar acceso de lectura de la compañía de la confirmación
    exige_acceso_compania("accounting", confirmation.company, "consultar")

    party = database.session.get(Party, confirmation.party_id)
    company = database.session.execute(select(Entity).where(Entity.code == confirmation.company)).scalar_one_or_none()

    snapshot = {}
    if confirmation.snapshot_json:
        snapshot = json.loads(confirmation.snapshot_json)

    invitations = (
        database.session.execute(
            select(BalanceConfirmationInvitation).where(
                BalanceConfirmationInvitation.balance_confirmation_id == confirmation.id
            )
        )
        .scalars()
        .all()
    )

    audit_timeline = format_document_timeline("balance_confirmation", confirmation.id)

    return render_template(
        "admin/balance_confirmation_detail.html",
        confirmation=confirmation,
        party=party,
        company=company,
        snapshot=snapshot,
        invitations=invitations,
        audit_timeline=audit_timeline,
    )


@balance_confirmations_bp.route("/accounting/balance-confirmations/<confirmation_id>/send", methods=["POST"])
@login_required
@modulo_activo("accounting")
def enviar_confirmacion(confirmation_id: str):
    """Envía la solicitud de confirmación de saldo a todos los destinatarios autorizados."""
    confirmation = database.session.get(BalanceConfirmation, confirmation_id)
    if not confirmation:
        abort(404)

    # Validar acceso de autorización para la compañía de la confirmación
    exige_acceso_compania("accounting", confirmation.company, "autorizar")

    if confirmation.status not in ("draft", "sent"):
        flash("La confirmación de saldo no se encuentra en un estado válido para envío.", "danger")
        return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation_id))

    invitations = (
        database.session.execute(
            select(BalanceConfirmationInvitation).where(
                BalanceConfirmationInvitation.balance_confirmation_id == confirmation.id
            )
        )
        .scalars()
        .all()
    )

    snapshot = json.loads(confirmation.snapshot_json) if confirmation.snapshot_json else {}
    company_name = snapshot.get("company_name", confirmation.company)
    party_name = snapshot.get("party_name", "")
    cutoff_date_str = confirmation.cutoff_date.strftime("%d/%m/%Y")

    any_sent = False
    for inv in invitations:
        # Dynamically generate token and code during the send request so we never lose them on redirects!
        import secrets

        raw_token = secrets.token_urlsafe(32)
        raw_code = "".join(secrets.choice("0123456789") for _ in range(6))

        inv.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        inv.verification_code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        inv.status = "pending"

        link = url_for("balance_confirmations.public_confirm_balance", token=raw_token, _external=True)

        body = f"""Estimado cliente/proveedor,

La empresa {company_name} le solicita la confirmación externa del saldo de su cuenta al {cutoff_date_str}.

Relación: {party_name}
Código de verificación: {raw_code}

Para ver el detalle de los documentos y responder a esta solicitud, ingrese al siguiente enlace seguro:
{link}

Atentamente,
{company_name}
"""
        try:
            send_email(
                to_email=inv.email,
                subject=f"Solicitud de Confirmación de Saldo - {company_name}",
                body=body,
            )
            inv.sent_at = datetime.utcnow()
            any_sent = True
        except EmailError as exc:
            flash(f"Error al enviar correo a {inv.email}: {exc}", "danger")

    if any_sent:
        confirmation.status = "sent"
        confirmation.sent_at = datetime.utcnow()
        log_balance_confirmation_event(
            confirmation,
            "balance_confirmation_sent",
            after=snapshot,
            comment="Solicitud de confirmación de saldo enviada por correo electrónico.",
        )
        database.session.commit()
        flash("Solicitud de confirmación enviada correctamente.", "success")

    return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation_id))


@balance_confirmations_bp.route("/accounting/balance-confirmations/<confirmation_id>/resend", methods=["POST"])
@login_required
@modulo_activo("accounting")
def reenviar_confirmacion(confirmation_id: str):
    """Invalida códigos anteriores, genera nuevos códigos y reenvía por correo."""
    confirmation = database.session.get(BalanceConfirmation, confirmation_id)
    if not confirmation:
        abort(404)

    # Validar acceso de autorización para la compañía de la confirmación
    exige_acceso_compania("accounting", confirmation.company, "autorizar")

    if confirmation.status not in ("sent", "viewed"):
        flash("Solo se pueden reenviar solicitudes ya enviadas o visualizadas.", "danger")
        return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation_id))

    invitations = (
        database.session.execute(
            select(BalanceConfirmationInvitation).where(
                BalanceConfirmationInvitation.balance_confirmation_id == confirmation.id
            )
        )
        .scalars()
        .all()
    )

    snapshot = json.loads(confirmation.snapshot_json) if confirmation.snapshot_json else {}
    company_name = snapshot.get("company_name", confirmation.company)
    party_name = snapshot.get("party_name", "")
    cutoff_date_str = confirmation.cutoff_date.strftime("%d/%m/%Y")

    any_sent = False
    for inv in invitations:
        # Generar nuevos tokens y códigos de verificación
        import secrets

        raw_token = secrets.token_urlsafe(32)
        raw_code = "".join(secrets.choice("0123456789") for _ in range(6))

        inv.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        inv.verification_code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        inv.failed_attempts = 0
        inv.status = "pending"

        link = url_for("balance_confirmations.public_confirm_balance", token=raw_token, _external=True)

        body = f"""Estimado cliente/proveedor,

Le reenviamos la solicitud de confirmación de saldo de {company_name} al {cutoff_date_str}.

Relación: {party_name}
Nuevo código de verificación: {raw_code}

Para ver el detalle de los documentos y responder a esta solicitud, ingrese al siguiente enlace seguro:
{link}

Atentamente,
{company_name}
"""
        try:
            send_email(
                to_email=inv.email,
                subject=f"Reenvío de Solicitud de Confirmación de Saldo - {company_name}",
                body=body,
            )
            inv.sent_at = datetime.utcnow()
            any_sent = True
        except EmailError as exc:
            flash(f"Error al enviar correo a {inv.email}: {exc}", "danger")

    if any_sent:
        confirmation.status = "sent"
        log_balance_confirmation_event(
            confirmation,
            "balance_confirmation_resent",
            after=snapshot,
            comment="Solicitud de confirmación de saldo reenviada con nuevos tokens y códigos.",
        )
        database.session.commit()
        flash("Solicitud de confirmación reenviada correctamente con nuevos códigos de acceso.", "success")

    return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation_id))


@balance_confirmations_bp.route("/accounting/balance-confirmations/<confirmation_id>/cancel", methods=["POST"])
@login_required
@modulo_activo("accounting")
def cancelar_confirmacion(confirmation_id: str):
    """Cancela la solicitud de confirmación de saldo (impide respuestas)."""
    confirmation = database.session.get(BalanceConfirmation, confirmation_id)
    if not confirmation:
        abort(404)

    # Validar acceso de anulación para la compañía de la confirmación
    exige_acceso_compania("accounting", confirmation.company, "anular")

    if confirmation.status in ("confirmed", "disputed", "cancelled", "expired"):
        flash("No se puede cancelar una solicitud que ya está cerrada, cancelada o expirada.", "danger")
        return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation_id))

    confirmation.status = "cancelled"
    confirmation.cancelled_at = datetime.utcnow()

    invitations = (
        database.session.execute(
            select(BalanceConfirmationInvitation).where(
                BalanceConfirmationInvitation.balance_confirmation_id == confirmation.id
            )
        )
        .scalars()
        .all()
    )
    for inv in invitations:
        inv.status = "cancelled"

    log_balance_confirmation_event(
        confirmation,
        "balance_confirmation_cancelled",
        comment="Solicitud de confirmación de saldo cancelada manualmente por el usuario.",
    )
    database.session.commit()
    flash("Solicitud de confirmación cancelada correctamente.", "warning")
    return redirect(url_for("balance_confirmations.ver_confirmacion", confirmation_id=confirmation_id))


# --- PUBLIC VIEWS & ENDPOINTS (No login required, external third-party actions) ---


@balance_confirmations_bp.route("/confirm-balance/<token>", methods=["GET"])
def public_confirm_balance(token: str):
    """Página segura de acceso externo para ver e interactuar con la confirmación."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = database.session.execute(
        select(BalanceConfirmationInvitation).where(BalanceConfirmationInvitation.token_hash == token_hash)
    ).scalar_one_or_none()

    if not invitation:
        return render_template("404.html"), 404

    confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
    if not confirmation:
        return render_template("404.html"), 404

    # Verificar estado de la confirmación
    if confirmation.status == "cancelled":
        return render_template(
            "public/confirm_balance_status.html",
            title="Cancelada",
            message="Esta solicitud de confirmación de saldo ha sido cancelada por el solicitante.",
        )

    # Verificar fecha de expiración
    if confirmation.expires_at and datetime.utcnow() > confirmation.expires_at:
        confirmation.status = "expired"
        database.session.commit()
        return render_template(
            "public/confirm_balance_status.html",
            title="Expirada",
            message="Esta solicitud de confirmación de saldo ha expirado y ya no se permiten respuestas.",
        )

    if confirmation.status in ("confirmed", "disputed"):
        msg = (
            f"Esta solicitud ya fue respondida el "
            f"{confirmation.responded_at.strftime('%d/%m/%Y %H:%M UTC')} por "
            f"{confirmation.respondent_first_name} {confirmation.respondent_last_name} "
            f"({confirmation.respondent_email}) y se encuentra cerrada."
        )
        return render_template(
            "public/confirm_balance_status.html",
            title="Cerrada",
            message=msg,
        )

    # Verificar si el usuario actual en sesión ya superó el paso de verificación
    session_key = f"verified_confirmation_{confirmation.id}"
    if session.get(session_key) != invitation.id:
        # Mostrar pantalla de verificación
        return render_template(
            "public/confirm_balance_verify.html",
            confirmation=confirmation,
            invitation=invitation,
            token=token,
        )

    # Mostrar partidas y formulario de respuesta
    snapshot = json.loads(confirmation.snapshot_json) if confirmation.snapshot_json else {}
    return render_template(
        "public/confirm_balance_view.html",
        confirmation=confirmation,
        invitation=invitation,
        snapshot=snapshot,
        token=token,
    )


@balance_confirmations_bp.route("/confirm-balance/<token>/verify", methods=["POST"])
def public_confirm_balance_verify(token: str):
    """Procesa el formulario de verificación de identidad externa."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = database.session.execute(
        select(BalanceConfirmationInvitation).where(BalanceConfirmationInvitation.token_hash == token_hash)
    ).scalar_one_or_none()

    if not invitation:
        return render_template("404.html"), 404

    confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
    if not confirmation or confirmation.status in ("confirmed", "disputed", "cancelled"):
        flash("La confirmación no se encuentra disponible.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email_input = request.form.get("email", "").strip().lower()
    code_input = request.form.get("code", "").strip()
    authorized_checkbox = request.form.get("authorized") == "on"

    if not first_name or not last_name or not email_input or not code_input:
        flash("Todos los campos de verificación son requeridos.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    if not authorized_checkbox:
        flash("Debe declarar bajo juramento que se encuentra autorizado para continuar.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    # Rate limiting / failed attempts check
    if invitation.failed_attempts >= 5:
        flash(
            "Se ha excedido el número de intentos permitidos para este enlace. Por favor contacte al administrador.", "danger"
        )
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    # Validar correspondencia exacta de correo
    if email_input != invitation.email:
        invitation.failed_attempts += 1
        database.session.commit()
        flash("La dirección de correo electrónico o el código ingresado son incorrectos.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    # Validar correspondencia del código de verificación
    hashed_code = hashlib.sha256(code_input.encode("utf-8")).hexdigest()
    if hashed_code != invitation.verification_code_hash:
        invitation.failed_attempts += 1
        database.session.commit()
        flash("La dirección de correo electrónico o el código ingresado son incorrectos.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    # Verificación exitosa
    invitation.verified_at = datetime.utcnow()
    invitation.last_access_at = datetime.utcnow()
    invitation.failed_attempts = 0
    invitation.status = "viewed"

    if confirmation.status == "sent":
        confirmation.status = "viewed"
        confirmation.viewed_at = datetime.utcnow()

    # Log audit event
    log_balance_confirmation_event(
        confirmation,
        "balance_confirmation_verified",
        comment=f"Identidad verificada exitosamente para {invitation.email}.",
    )
    log_balance_confirmation_event(
        confirmation,
        "balance_confirmation_viewed",
        comment=f"Partidas abiertas consultadas por el tercero {first_name} {last_name}.",
    )

    database.session.commit()

    # Almacenar en sesión la verificación exitosa
    session[f"verified_confirmation_{confirmation.id}"] = invitation.id
    # También podemos almacenar el nombre/apellido en sesión para el respondiente
    session[f"verified_confirmation_name_{confirmation.id}"] = (first_name, last_name)

    return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))


@balance_confirmations_bp.route("/confirm-balance/<token>/respond", methods=["POST"])
def public_confirm_balance_respond(token: str):
    """Procesa el formulario definitivo de respuesta (convalidación o discrepancia)."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = database.session.execute(
        select(BalanceConfirmationInvitation).where(BalanceConfirmationInvitation.token_hash == token_hash)
    ).scalar_one_or_none()

    if not invitation:
        return render_template("404.html"), 404

    confirmation = database.session.get(BalanceConfirmation, invitation.balance_confirmation_id)
    if not confirmation or confirmation.status in ("confirmed", "disputed", "cancelled"):
        flash("La confirmación no se encuentra disponible para responder.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    # Verificar sesión de verificación
    session_key = f"verified_confirmation_{confirmation.id}"
    if session.get(session_key) != invitation.id:
        flash("Debe completar el paso de verificación primero.", "warning")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    response_type = request.form.get("response_type")  # confirmed | disputed
    response_comment = request.form.get("response_comment", "").strip()

    if response_type not in ("confirmed", "disputed"):
        flash("Tipo de respuesta no válido.", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    if response_type == "disputed" and (not response_comment or len(response_comment) < 10):
        flash("Debe proporcionar una explicación detallada de las diferencias encontradas (mínimo 10 caracteres).", "danger")
        return redirect(url_for("balance_confirmations.public_confirm_balance", token=token))

    first_name, last_name = session.get(f"verified_confirmation_name_{confirmation.id}", ("", ""))

    # Actualizar estado de la confirmación
    confirmation.status = "confirmed" if response_type == "confirmed" else "disputed"
    confirmation.responded_at = datetime.utcnow()
    confirmation.response_type = response_type
    confirmation.response_comment = response_comment

    confirmation.respondent_first_name = first_name
    confirmation.respondent_last_name = last_name
    confirmation.respondent_email = invitation.email
    confirmation.respondent_ip = request.remote_addr
    confirmation.respondent_user_agent = request.user_agent.string if request.user_agent else None

    # Cerrar la invitación actual y todas las demás asociadas a la misma confirmación
    invitation.status = "responded"
    other_invitations = (
        database.session.execute(
            select(BalanceConfirmationInvitation).where(
                BalanceConfirmationInvitation.balance_confirmation_id == confirmation.id,
                BalanceConfirmationInvitation.id != invitation.id,
            )
        )
        .scalars()
        .all()
    )
    for o_inv in other_invitations:
        o_inv.status = "cancelled"  # closed because another person responded first

    action_event = "balance_confirmation_confirmed" if response_type == "confirmed" else "balance_confirmation_disputed"
    log_balance_confirmation_event(
        confirmation,
        action_event,
        comment=f"Confirmación respondida como {response_type.upper()}. Comentario: {response_comment or 'Sin comentario'}.",
    )

    database.session.commit()

    # Limpiar sesión de verificación
    session.pop(session_key, None)
    session.pop(f"verified_confirmation_name_{confirmation.id}", None)

    return render_template(
        "public/confirm_balance_success.html",
        confirmation=confirmation,
        company_name=(
            json.loads(confirmation.snapshot_json).get("company_name", confirmation.company)
            if confirmation.snapshot_json
            else confirmation.company
        ),
    )
