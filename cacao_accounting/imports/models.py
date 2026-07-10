# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modelos para el servicio de importación."""

from cacao_accounting.database import database, BaseTabla, ENTITY_CODE, NAMING_SERIES_ID, BOOK_CODE, FK_RESTRICT, FK_CASCADE, FK_SET_NULL


class ImportBatch(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Lote de importación tabular."""

    __tablename__ = "import_batch"

    company_id = database.Column(database.String(10), database.ForeignKey(ENTITY_CODE, ondelete=FK_RESTRICT, onupdate=FK_CASCADE), nullable=False)
    company = database.relationship("Entity", lazy="joined")
    record_type = database.Column(database.String(50), nullable=False)
    sequence_id = database.Column(database.String(26), database.ForeignKey(NAMING_SERIES_ID, ondelete=FK_SET_NULL, onupdate=FK_CASCADE), nullable=True)
    accounting_book_id = database.Column(database.String(10), database.ForeignKey(BOOK_CODE, ondelete=FK_RESTRICT, onupdate=FK_CASCADE), nullable=True)
    book = database.relationship("Book", lazy="joined")
    source_format = database.Column(database.String(10))
    source_filename = database.Column(database.String(255))
    source_path = database.Column(database.String(500))
    total_rows = database.Column(database.Integer(), default=0)
    processed_rows = database.Column(database.Integer(), default=0)
    success_rows = database.Column(database.Integer(), default=0)
    error_rows = database.Column(database.Integer(), default=0)
    warning_rows = database.Column(database.Integer(), default=0)
    # Status:
    # 0=no iniciado, 1=archivo cargado, 2=validado, 3=listo, 4=procesando,
    # 5=completado, 6=completado con errores, 7=fallido, 8=cancelado
    import_status = database.Column(database.Integer(), default=0)
    cancel_requested = database.Column(database.Boolean(), default=False)
    started_at = database.Column(database.DateTime)
    completed_at = database.Column(database.DateTime)


class ImportBatchError(database.Model, BaseTabla):  # type: ignore[name-defined]
    """Errores encontrados durante la importación."""

    __tablename__ = "import_batch_error"

    batch_id = database.Column(database.String(26), database.ForeignKey("import_batch.id", ondelete=FK_CASCADE, onupdate=FK_CASCADE), nullable=False)
    row_number = database.Column(database.Integer())
    document_ref = database.Column(database.String(100))
    field_name = database.Column(database.String(100))
    error_type = database.Column(database.String(50))
    message = database.Column(database.Text())
