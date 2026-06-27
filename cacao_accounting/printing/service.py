# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Central service for reusable document printing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import current_app, has_request_context, request
from flask_weasyprint import HTML
from jinja2 import BaseLoader, StrictUndefined, TemplateError, TemplateSyntaxError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select

from cacao_accounting.database import database
from cacao_accounting.printing.exceptions import (
    PrintPermissionError,
    PrintTemplateNotFoundError,
    TemplateValidationError,
)
from cacao_accounting.printing.models import (
    PrintJobLog,
    PrintTemplate,
    PrintTemplateVersion,
    PublicDocumentValidation,
)
from cacao_accounting.printing.registry import get_printable_document
from cacao_accounting.printing.settings import external_validation_base_url, external_validation_enabled
from cacao_accounting.printing.validation import ValidationService
from cacao_accounting.printing.validators import validate_css_safety, validate_template_security


@dataclass(frozen=True)
class TemplateValidationResult:
    """Result returned by template validation."""

    valid: bool
    message: str = ""


class PrintService:
    """Render registered documents with database-backed templates."""

    def __init__(self) -> None:
        """Create a sandboxed Jinja environment for print templates."""
        self.env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=True,
            undefined=StrictUndefined,
        )
        self._setup_filters()

    def render_preview_html(
        self,
        document_type: str,
        document_id: str | None,
        user: Any,
        company_code: str,
        template_id: str | int | None = None,
        sample: bool = False,
    ) -> str:
        """Render preview HTML for a sample or real document."""
        template: PrintTemplate | None = None
        try:
            context = self._build_context(document_type, document_id, user, company_code, sample)
            template = self.resolve_template(document_type, company_code, template_id, allow_draft=sample)
            rendered_body = self.env.from_string(template.template_body).render(**context)
            html = self.build_print_html(rendered_body, template.stylesheet_body)
            self.log_print_job(
                company_code=company_code,
                user_id=self._user_id(user),
                document_type=document_type,
                document_id=document_id or "sample",
                template=template,
                output_format="html_preview",
            )
            return html
        except (PrintPermissionError, PrintTemplateNotFoundError, TemplateError, ValueError) as exc:
            self.log_print_job(
                company_code=company_code,
                user_id=self._user_id(user),
                document_type=document_type,
                document_id=document_id or "sample",
                template=template,
                output_format="html_preview",
                success=False,
                error_message=str(exc),
            )
            raise

    def render_pdf(
        self,
        document_type: str,
        document_id: str,
        user: Any,
        company_code: str,
        template_id: str | int | None = None,
    ) -> bytes:
        """Render a registered document as PDF bytes."""
        template: PrintTemplate | None = None
        try:
            context = self._build_context(document_type, document_id, user, company_code, sample=False)
            template = self.resolve_template(document_type, company_code, template_id)
            rendered_body = self.env.from_string(template.template_body).render(**context)
            html_string = self.build_print_html(rendered_body, template.stylesheet_body)
            pdf = HTML(string=html_string, base_url=self._base_url()).write_pdf()
            self.log_print_job(
                company_code=company_code,
                user_id=self._user_id(user),
                document_type=document_type,
                document_id=document_id,
                template=template,
                output_format="pdf",
            )
            return bytes(pdf)
        except (PrintPermissionError, PrintTemplateNotFoundError, TemplateError, ValueError) as exc:
            self.log_print_job(
                company_code=company_code,
                user_id=self._user_id(user),
                document_type=document_type,
                document_id=document_id,
                template=template,
                output_format="pdf",
                success=False,
                error_message=str(exc),
            )
            raise

    def validate_template(
        self,
        template_body: str,
        stylesheet_body: str | None,
        document_type: str,
        validate_pdf: bool = False,
    ) -> bool:
        """Validate template safety, syntax and sample rendering."""
        validate_template_security(template_body)
        validate_css_safety(stylesheet_body)
        doc_def = get_printable_document(document_type)
        if doc_def is None:
            raise TemplateValidationError(f"Document type {document_type} is not registered.")

        try:
            context = doc_def["sample_context_builder"]()
            self._inject_validation_context(context, document_type, "sample", None)
            rendered = self.env.from_string(template_body).render(**context)
            if not rendered.strip():
                raise TemplateValidationError("La plantilla renderizada esta vacia.")
            if "validation.qr_data_uri" in template_body:
                ValidationService().get_qr_data_uri("https://cacaocontent.com/public/validate_doc/sample")
            if validate_pdf:
                HTML(string=self.build_print_html(rendered, stylesheet_body), base_url=self._base_url()).write_pdf()
        except RuntimeError as exc:
            raise TemplateValidationError(str(exc)) from exc
        except (TemplateSyntaxError, UndefinedError, TemplateError) as exc:
            raise TemplateValidationError(f"Error de renderizado Jinja2: {exc}") from exc

        return True

    def create_version(self, template: PrintTemplate, change_note: str | None = None) -> None:
        """Store the current template body and CSS as a historical version."""
        database.session.add(
            PrintTemplateVersion(
                template_id=template.id,
                version=template.version,
                template_body=template.template_body,
                stylesheet_body=template.stylesheet_body,
                paper_size=template.paper_size,
                orientation=template.orientation,
                status=template.status,
                change_note=change_note,
            )
        )

    def resolve_template(
        self,
        document_type: str,
        company_code: str,
        template_id: str | int | None = None,
        allow_draft: bool = False,
    ) -> PrintTemplate:
        """Resolve a published template by explicit id, company default or global default."""
        if get_printable_document(document_type) is None:
            raise PrintTemplateNotFoundError(f"Document type {document_type} is not registered.")
        if template_id:
            return self._resolve_template_by_id(document_type, company_code, template_id, allow_draft)

        company_default = self._default_template(document_type, company_code)
        if company_default is not None:
            return company_default
        global_default = self._default_template(document_type, None)
        if global_default is not None:
            return global_default
        raise PrintTemplateNotFoundError(f"No published template found for {document_type}.")

    def build_print_html(self, rendered_body: str, stylesheet_body: str | None) -> str:
        """Build the final standalone HTML document with embedded CSS."""
        css = stylesheet_body or ""
        return (
            "<!doctype html>\n"
            '<html lang="es">\n'
            "<head>\n"
            '    <meta charset="utf-8">\n'
            "    <style>\n"
            f"{css}\n"
            "    </style>\n"
            "</head>\n"
            "<body>\n"
            f"{rendered_body}\n"
            "</body>\n"
            "</html>\n"
        )

    def log_print_job(
        self,
        *,
        company_code: str,
        user_id: str,
        document_type: str,
        document_id: str,
        template: PrintTemplate | None,
        output_format: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Persist operational audit metadata for one print attempt."""
        database.session.add(
            PrintJobLog(
                company_code=company_code,
                user_id=user_id,
                document_type=document_type,
                document_id=document_id,
                template_id=template.id if template else None,
                template_version=template.version if template else None,
                output_format=output_format,
                success=success,
                error_message=error_message,
            )
        )
        database.session.commit()

    def _build_context(
        self,
        document_type: str,
        document_id: str | None,
        user: Any,
        company_code: str,
        sample: bool,
    ) -> dict[str, Any]:
        doc_def = get_printable_document(document_type)
        if doc_def is None:
            raise ValueError(f"Document type {document_type} not registered.")
        if sample:
            context = doc_def["sample_context_builder"](user=user, company=company_code)
            self._inject_validation_context(context, document_type, "sample", company_code)
            return context
        if not document_id:
            raise ValueError("document_id is required for non-sample rendering.")
        context = doc_def["context_builder"](document_id, user, company_code)
        self._inject_validation_context(context, document_type, document_id, company_code)
        return context

    def _resolve_template_by_id(
        self,
        document_type: str,
        company_code: str,
        template_id: str | int,
        allow_draft: bool,
    ) -> PrintTemplate:
        template = database.session.get(PrintTemplate, template_id)
        if template is None or template.document_type != document_type:
            raise PrintTemplateNotFoundError("Template not found for requested document type.")
        if template.company_code not in (None, company_code):
            raise PrintPermissionError("Template is not available for this company.")
        if template.status != "published" and not allow_draft:
            raise PrintTemplateNotFoundError("Template is not published.")
        return template

    def _default_template(self, document_type: str, company_code: str | None) -> PrintTemplate | None:
        return (
            database.session.execute(
                select(PrintTemplate)
                .filter_by(
                    company_code=company_code,
                    document_type=document_type,
                    status="published",
                    is_default=True,
                )
                .order_by(PrintTemplate.id)
            )
            .scalars()
            .first()
        )

    def _inject_validation_context(
        self,
        context: dict[str, Any],
        document_type: str,
        document_id: str | None,
        company_code: str | None,
    ) -> None:
        if not external_validation_enabled() or not document_id or document_id == "sample":
            context["validation"] = self._empty_validation_context()
            return

        query = select(PublicDocumentValidation).filter_by(document_type=document_type, document_id=str(document_id))
        if company_code:
            query = query.filter_by(company_code=company_code)
        val_record = database.session.execute(query).scalars().first()
        if val_record is None or not val_record.is_enabled:
            context["validation"] = self._empty_validation_context()
            return

        public_url = f"{external_validation_base_url()}/public/validate_doc/{val_record.public_token}"
        context["validation"] = {
            "enabled": True,
            "public_url": public_url,
            "qr_data_uri": ValidationService().get_qr_data_uri(public_url),
            "token": val_record.public_token,
        }

    def _setup_filters(self) -> None:
        from cacao_accounting import format_money_with_currency, format_quantity
        from flask_babel import format_date, format_datetime

        def percent_filter(value: Any) -> str:
            try:
                return f"{float(value or 0):.2f}%"
            except (ValueError, TypeError):
                return "0.00%"

        def default_text_filter(value: Any, default: str = "-") -> Any:
            return value if value not in (None, "") else default

        def status_label(value: Any) -> str:
            labels = {
                "draft": "Draft",
                "posted": "Posted",
                "submitted": "Submitted",
                "void": "Void",
                "cancelled": "Cancelled",
                "reverted": "Reverted",
            }
            return labels.get(str(value).lower(), str(value).title())

        self.env.filters.update(
            {
                "money": format_money_with_currency,
                "number": format_quantity,
                "date": format_date,
                "datetime": format_datetime,
                "percent": percent_filter,
                "default_text": default_text_filter,
                "status_label": status_label,
            }
        )

    def _base_url(self) -> str:
        if has_request_context():
            return request.url_root
        return current_app.config.get("SERVER_NAME") or "http://localhost/"

    def _empty_validation_context(self) -> dict[str, str | bool | None]:
        return {"enabled": False, "public_url": None, "qr_data_uri": None, "token": None}

    def _user_id(self, user: Any) -> str:
        return str(getattr(user, "id", None) or getattr(user, "user", None) or user)
