# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Public validation and operational print routes."""

from __future__ import annotations

from flask import Blueprint, Response, abort, current_app, render_template, request
from flask_login import current_user, login_required

from cacao_accounting.printing.exceptions import PrintingError
from cacao_accounting.printing.service import PrintService
from cacao_accounting.printing.settings import external_validation_enabled
from cacao_accounting.printing.validation import ValidationService

printing_public = Blueprint("printing_public", __name__)


@printing_public.route("/public/validate_doc/<token>")
def validate_document(token: str):
    """Validate a public document token without authentication."""
    if not external_validation_enabled():
        return "Validation unavailable", 403

    service = ValidationService()
    result = service.validate_token(token)
    if result["status"] == "unavailable":
        return "Document not found or validation unavailable", 404

    view = service.build_public_view(result)
    if view is None:
        return "Document not found or validation unavailable", 404
    return render_template("public/validation_result.html", validation=view)


@printing_public.route("/print/<document_type>/<document_id>/preview")
@login_required
def preview_document(document_type: str, document_id: str) -> str:
    """Render an operational document preview."""
    company = request.args.get("company") or _current_company()
    template_id = request.args.get("template_id")
    try:
        return PrintService().render_preview_html(
            document_type=document_type,
            document_id=document_id,
            user=current_user,
            company_code=company,
            template_id=template_id,
        )
    except PrintingError as exc:
        abort(404, str(exc))


@printing_public.route("/print/<document_type>/<document_id>/pdf")
@login_required
def document_pdf(document_type: str, document_id: str) -> Response:
    """Render an operational document as PDF."""
    company = request.args.get("company") or _current_company()
    template_id = request.args.get("template_id")
    try:
        pdf = PrintService().render_pdf(
            document_type=document_type,
            document_id=document_id,
            user=current_user,
            company_code=company,
            template_id=template_id,
        )
    except PrintingError as exc:
        abort(404, str(exc))
    return Response(pdf, mimetype="application/pdf")


def _current_company() -> str:
    return str(getattr(current_user, "company", None) or current_app.config.get("DEFAULT_COMPANY", "cacao"))
