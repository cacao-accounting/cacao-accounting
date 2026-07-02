# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Administrative routes for print templates."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from cacao_accounting.database import Entity, Roles, RolesUser, database
from cacao_accounting.printing.exceptions import PrintingError, TemplateValidationError
from cacao_accounting.printing.models import PrintTemplate, PrintTemplateVersion
from cacao_accounting.printing.registry import get_printable_document, list_printable_documents
from cacao_accounting.printing.service import PrintService
from cacao_accounting.printing.settings import (
    DEFAULT_VALIDATION_BASE_URL,
    external_validation_base_url,
    external_validation_enabled,
    save_external_validation_settings,
)

printing_admin = Blueprint("printing_admin", __name__, template_folder="templates")

_ENDPOINT_LIST_TEMPLATES = "printing_admin.list_templates"


@printing_admin.route("/admin/print-templates")
@login_required
def list_templates():
    """List print templates for administrators."""
    _require_print_admin()
    templates = (
        database.session.execute(select(PrintTemplate).order_by(PrintTemplate.document_type, PrintTemplate.code))
        .scalars()
        .all()
    )
    return render_template("admin/print_template_list.html", templates=templates)


@printing_admin.route("/admin/print-templates/settings", methods=["GET", "POST"])
@login_required
def validation_settings():
    """Manage global settings for public document validation."""
    _require_print_admin()
    if request.method == "POST":
        enabled = request.form.get("external_document_validation_enabled") == "on"
        base_url = request.form.get("external_document_validation_base_url")
        save_external_validation_settings(enabled, base_url)
        flash("Configuración de validación externa actualizada.", "success")
        return redirect(url_for("printing_admin.validation_settings"))

    return render_template(
        "admin/print_validation_settings.html",
        validation_enabled=external_validation_enabled(),
        validation_base_url=external_validation_base_url(),
        default_validation_base_url=DEFAULT_VALIDATION_BASE_URL,
    )


@printing_admin.route("/admin/print-templates/new", methods=["GET", "POST"])
@login_required
def create_template():
    """Create a draft print template."""
    _require_print_admin()
    if request.method == "POST":
        template = PrintTemplate(
            company_code=request.form.get("company_code") or None,
            document_type=request.form.get("document_type") or "",
            code=request.form.get("code") or "",
            name=request.form.get("name") or "",
            description=request.form.get("description"),
            template_body=request.form.get("template_body") or "",
            stylesheet_body=request.form.get("stylesheet_body"),
            paper_size=request.form.get("paper_size") or "letter",
            orientation=request.form.get("orientation") or "portrait",
            status="draft",
            created_by=_current_user_id(),
        )
        database.session.add(template)
        database.session.commit()
        flash("Plantilla creada exitosamente.", "success")
        return redirect(url_for("printing_admin.edit_template", template_id=template.id))
    return _render_form(None)


@printing_admin.route("/admin/print-templates/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
def edit_template(template_id: int):
    """Edit a non-system print template."""
    _require_print_admin()
    template = _get_template(template_id)
    if template.is_system:
        flash("Las plantillas de sistema no pueden editarse directamente.", "warning")
        return redirect(url_for(_ENDPOINT_LIST_TEMPLATES))
    if request.method == "POST":
        _update_template_from_form(template)
    return _render_form(template)


@printing_admin.route("/admin/print-templates/<int:template_id>/duplicate", methods=["POST"])
@login_required
def duplicate_template(template_id: int):
    """Duplicate a template as editable draft."""
    _require_print_admin()
    source = _get_template(template_id)
    copy = PrintTemplate(
        company_code=source.company_code,
        document_type=source.document_type,
        code=_copy_code(source.code),
        name=f"Copia de {source.name}",
        description=source.description,
        template_body=source.template_body,
        stylesheet_body=source.stylesheet_body,
        paper_size=source.paper_size,
        orientation=source.orientation,
        status="draft",
        is_system=False,
        is_default=False,
        created_by=_current_user_id(),
    )
    database.session.add(copy)
    database.session.commit()
    flash("Plantilla duplicada exitosamente.", "success")
    return redirect(url_for("printing_admin.edit_template", template_id=copy.id))


@printing_admin.route("/admin/print-templates/<int:template_id>/publish", methods=["POST"])
@login_required
def publish_template(template_id: int):
    """Validate and publish a print template."""
    _require_print_admin()
    template = _get_template(template_id)
    try:
        PrintService().validate_template(
            template.template_body,
            template.stylesheet_body,
            template.document_type,
            validate_pdf=True,
        )
        template.status = "published"
        template.updated_by = _current_user_id()
        database.session.commit()
        flash("Plantilla publicada.", "success")
    except (TemplateValidationError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash(f"Error al publicar: {exc}", "danger")
    return redirect(url_for(_ENDPOINT_LIST_TEMPLATES))


@printing_admin.route("/admin/print-templates/<int:template_id>/archive", methods=["POST"])
@login_required
def archive_template(template_id: int):
    """Archive a non-system print template."""
    _require_print_admin()
    template = _get_template(template_id)
    if template.is_system:
        flash("Las plantillas de sistema no pueden archivarse.", "warning")
    else:
        template.status = "archived"
        template.is_default = False
        template.updated_by = _current_user_id()
        database.session.commit()
        flash("Plantilla archivada.", "success")
    return redirect(url_for(_ENDPOINT_LIST_TEMPLATES))


@printing_admin.route("/admin/print-templates/<int:template_id>/set-default", methods=["POST"])
@login_required
def set_default_template(template_id: int):
    """Set one published template as default for its company and document type."""
    _require_print_admin()
    template = _get_template(template_id)
    if template.status != "published":
        flash("Solo las plantillas publicadas pueden ser predeterminadas.", "warning")
        return redirect(url_for(_ENDPOINT_LIST_TEMPLATES))
    _clear_default(template)
    template.is_default = True
    template.updated_by = _current_user_id()
    database.session.commit()
    flash("Plantilla marcada como predeterminada.", "success")
    return redirect(url_for(_ENDPOINT_LIST_TEMPLATES))


@printing_admin.route("/admin/print-templates/<int:template_id>/preview")
@login_required
def preview_template(template_id: int):
    """Preview a template with sample data inside an iframe."""
    _require_print_admin()
    template = _get_template(template_id)
    try:
        return PrintService().render_preview_html(
            document_type=template.document_type,
            document_id=None,
            user=current_user,
            company_code=template.company_code or "cacao",
            template_id=template.id,
            sample=True,
        )
    except PrintingError as exc:
        return f"Error rendering preview: {exc}", 500


@printing_admin.route("/admin/print-templates/<int:template_id>/versions")
@login_required
def template_versions(template_id: int):
    """Show template version history."""
    _require_print_admin()
    template = _get_template(template_id)
    versions = (
        database.session.execute(
            select(PrintTemplateVersion).filter_by(template_id=template.id).order_by(PrintTemplateVersion.version.desc())
        )
        .scalars()
        .all()
    )
    return render_template("admin/print_template_list.html", templates=[template], versions=versions)


def _update_template_from_form(template: PrintTemplate) -> None:
    service = PrintService()
    try:
        body = request.form.get("template_body") or ""
        css = request.form.get("stylesheet_body")
        service.validate_template(body, css, template.document_type)
        service.create_version(template, change_note=request.form.get("change_note"))
        template.name = request.form.get("name") or template.name
        template.description = request.form.get("description")
        template.template_body = body
        template.stylesheet_body = css
        template.paper_size = request.form.get("paper_size") or "letter"
        template.orientation = request.form.get("orientation") or "portrait"
        template.version += 1
        template.updated_by = _current_user_id()
        database.session.commit()
        flash("Plantilla actualizada exitosamente.", "success")
    except (TemplateValidationError, SQLAlchemyError) as exc:
        database.session.rollback()
        flash(f"Error al actualizar plantilla: {exc}", "danger")


def _render_form(template: PrintTemplate | None):
    doc_types = list_printable_documents()
    companies = database.session.execute(select(Entity).filter_by(enabled=True)).scalars().all()
    definition = get_printable_document(template.document_type) if template else None
    return render_template(
        "admin/print_template_form.html",
        doc_types=doc_types,
        companies=companies,
        template=template,
        schema=definition["schema"] if definition else {},
        snippets=definition["snippets"] if definition else [],
    )


def _get_template(template_id: int) -> PrintTemplate:
    template = database.session.get(PrintTemplate, template_id)
    if template is None:
        abort(404)
    return template


def _clear_default(template: PrintTemplate) -> None:
    database.session.execute(
        database.update(PrintTemplate)
        .where(
            PrintTemplate.company_code == template.company_code,
            PrintTemplate.document_type == template.document_type,
        )
        .values(is_default=False)
    )


def _copy_code(code: str) -> str:
    return f"{code}_copy"


def _current_user_id() -> str:
    return str(getattr(current_user, "id", ""))


def _require_print_admin() -> None:
    if not _is_print_admin():
        abort(403)


def _is_print_admin() -> bool:
    user_id = _current_user_id()
    admin_role = database.session.execute(select(Roles).filter_by(name="admin")).scalars().first()
    if admin_role is None:
        return True
    return (
        database.session.execute(select(RolesUser).filter_by(user_id=user_id, role_id=admin_role.id)).scalars().first()
        is not None
    )
