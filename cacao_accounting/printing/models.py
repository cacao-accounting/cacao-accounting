# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Modelos para el servicio de impresión y validación de documentos."""

from cacao_accounting.database import database, ENTITY_CODE, USER_ID


class PrintTemplate(database.Model):  # type: ignore[name-defined]
    """Modelo principal para formatos de impresión."""

    __tablename__ = "print_templates"

    id = database.Column(database.Integer, primary_key=True)

    company_code = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=True)

    document_type = database.Column(database.String(80), nullable=False)
    code = database.Column(database.String(80), nullable=False, index=True)
    name = database.Column(database.String(150), nullable=False)
    description = database.Column(database.Text)

    template_body = database.Column(database.Text, nullable=False)
    stylesheet_body = database.Column(database.Text, nullable=True)

    paper_size = database.Column(database.String(20), default="letter", nullable=False)
    orientation = database.Column(database.String(20), default="portrait", nullable=False)

    status = database.Column(database.String(20), default="draft", nullable=False)
    is_system = database.Column(database.Boolean, default=False, nullable=False)
    is_default = database.Column(database.Boolean, default=False, nullable=False)

    version = database.Column(database.Integer, default=1, nullable=False)

    created_by = database.Column(database.String(26), database.ForeignKey(USER_ID))
    updated_by = database.Column(database.String(26), database.ForeignKey(USER_ID))

    created_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    updated_at = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=False,
    )

    __table_args__ = (
        database.UniqueConstraint(
            "company_code",
            "document_type",
            "code",
            name="uq_print_template_company_document_code",
        ),
    )


class PrintTemplateVersion(database.Model):  # type: ignore[name-defined]
    """Registro de versiones de plantillas de impresión."""

    __tablename__ = "print_template_versions"

    id = database.Column(database.Integer, primary_key=True)

    template_id = database.Column(
        database.Integer,
        database.ForeignKey("print_templates.id"),
        nullable=False,
    )

    version = database.Column(database.Integer, nullable=False)

    template_body = database.Column(database.Text, nullable=False)
    stylesheet_body = database.Column(database.Text, nullable=True)

    paper_size = database.Column(database.String(20), nullable=False)
    orientation = database.Column(database.String(20), nullable=False)
    status = database.Column(database.String(20), nullable=False)

    changed_by = database.Column(database.String(26), database.ForeignKey(USER_ID))
    changed_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)

    change_note = database.Column(database.String(255))


class PrintJobLog(database.Model):  # type: ignore[name-defined]
    """Registro de auditoría de trabajos de impresión."""

    __tablename__ = "print_job_logs"

    id = database.Column(database.Integer, primary_key=True)

    company_code = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE), nullable=False)
    user_id = database.Column(database.String(26), database.ForeignKey(USER_ID), nullable=False)

    document_type = database.Column(database.String(80), nullable=False)
    document_id = database.Column(database.String(26), nullable=False)

    template_id = database.Column(database.Integer, database.ForeignKey("print_templates.id"), nullable=True)
    template_version = database.Column(database.Integer, nullable=True)

    output_format = database.Column(database.String(20), nullable=False)

    rendered_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)

    success = database.Column(database.Boolean, default=True, nullable=False)
    error_message = database.Column(database.Text)


class PublicDocumentValidation(database.Model):  # type: ignore[name-defined]
    """Modelo para la validación pública de documentos mediante QR."""

    __tablename__ = "public_document_validations"

    id = database.Column(database.Integer, primary_key=True)

    public_token = database.Column(
        database.String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    company_code = database.Column(
        database.String(10),
        database.ForeignKey(ENTITY_CODE),
        nullable=False,
    )

    document_type = database.Column(database.String(80), nullable=False)
    document_id = database.Column(database.String(26), nullable=False)

    document_number = database.Column(database.String(80), nullable=False)
    document_date = database.Column(database.Date, nullable=True)
    document_status = database.Column(database.String(40), nullable=False)

    validation_hash = database.Column(
        database.String(128),
        nullable=False,
    )

    is_enabled = database.Column(
        database.Boolean,
        default=True,
        nullable=False,
    )

    created_at = database.Column(database.DateTime, default=database.func.now(), nullable=False)
    updated_at = database.Column(
        database.DateTime,
        default=database.func.now(),
        onupdate=database.func.now(),
        nullable=False,
    )
