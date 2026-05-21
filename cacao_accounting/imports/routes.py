# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Rutas para el servicio de importación."""

import os
import openpyxl
from odf import opendocument, table as odf_table
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    abort,
    send_file,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from cacao_accounting.database import database, Entity, NamingSeries, Book
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.imports.models import ImportBatch
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.decorators import modulo_activo

imports = Blueprint("imports", __name__, template_folder="templates")


def check_desktop_mode():
    """Abortar con 403 si el sistema está en modo escritorio."""
    if current_app.config.get("MODO_ESCRITORIO"):
        abort(403)


def check_permission(action):
    """Verifica permisos para el módulo de importación."""
    p = Permisos(modulo=obtener_id_modulo_por_nombre("imports"), usuario=current_user.id)
    if not getattr(p, action, False):
        abort(403)


@imports.before_request
def before_request():
    """Ejecutar verificaciones previas a cada solicitud."""
    check_desktop_mode()


@imports.route("/")
@modulo_activo("imports")
@login_required
def index():
    """Listado de lotes de importación."""
    check_permission("consultar")
    batches = ImportBatch.query.order_by(ImportBatch.created.desc()).all()
    return render_template("imports/index.html", batches=batches)


@imports.route("/new", methods=["GET", "POST"])
@modulo_activo("imports")
@login_required
def new():
    """Crear un nuevo lote de importación."""
    check_permission("crear")
    if request.method == "POST":
        record_type = request.form.get("record_type")
        accounting_book_id = request.form.get("accounting_book_id") or None

        if record_type != "journal_entry" and accounting_book_id:
            flash("El libro contable solo se permite para comprobantes contables.", "danger")
            return redirect(url_for("imports.new"))

        batch = ImportBatch(
            company_id=request.form.get("company_id"),
            record_type=record_type,
            sequence_id=request.form.get("sequence_id") or None,
            accounting_book_id=accounting_book_id,
            import_status=0,
            created_by=current_user.id,
        )
        database.session.add(batch)
        database.session.commit()
        return redirect(url_for("imports.detail", batch_id=batch.id))

    companies = Entity.query.filter_by(enabled=True).all()
    # Simplified list of record types for now
    record_types = [
        {"value": "journal_entry", "label": "Comprobantes Contables"},
        {"value": "purchase_order", "label": "Órdenes de Compra"},
        {"value": "customer", "label": "Clientes"},
        {"value": "vendor", "label": "Proveedores"},
        {"value": "chart_of_accounts", "label": "Catálogo de Cuentas"},
    ]
    sequences = NamingSeries.query.all()
    books = Book.query.all()

    return render_template(
        "imports/new.html",
        companies=companies,
        record_types=record_types,
        sequences=sequences,
        books=books,
    )


@imports.route("/<batch_id>")
@modulo_activo("imports")
@login_required
def detail(batch_id):
    """Detalle y vista previa de un lote de importación."""
    check_permission("consultar")
    batch = ImportBatch.query.get_or_404(batch_id)
    service = ImportService()
    preview_data = {}
    if batch.import_status >= 1:  # Archivo cargado
        preview_data = service.preview(batch_id)

    return render_template("imports/detail.html", batch=batch, preview=preview_data)


@imports.route("/<batch_id>/upload", methods=["POST"])
@modulo_activo("imports")
@login_required
def upload(batch_id):
    """Subir un archivo a un lote de importación."""
    check_permission("actualizar")
    batch = ImportBatch.query.get_or_404(batch_id)
    file = request.files.get("file")
    if file and file.filename:
        filename = secure_filename(file.filename)
        extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        if extension not in ["csv", "xls", "xlsx", "ods"]:
            flash("Formato de archivo no soportado", "danger")
            return redirect(url_for("imports.detail", batch_id=batch_id))

        import_dir = os.path.join(current_app.instance_path, "imports", batch_id)
        os.makedirs(import_dir, exist_ok=True)
        file_path = os.path.join(import_dir, filename)
        file.save(file_path)

        batch.source_filename = filename
        batch.source_format = extension
        batch.source_path = file_path
        batch.import_status = 1  # Archivo cargado
        database.session.commit()

        flash("Archivo cargado correctamente", "success")
    return redirect(url_for("imports.detail", batch_id=batch_id))


@imports.route("/<batch_id>/validate", methods=["POST"])
@modulo_activo("imports")
@login_required
def validate(batch_id):
    """Ejecutar la validación del archivo subido."""
    check_permission("validar")
    service = ImportService()
    service.validate(batch_id)
    return redirect(url_for("imports.detail", batch_id=batch_id))


@imports.route("/<batch_id>/execute", methods=["POST"])
@modulo_activo("imports")
@login_required
def execute(batch_id):
    """Ejecutar el proceso de importación."""
    check_permission("autorizar")
    service = ImportService()
    service.execute(batch_id)
    flash("Importación iniciada", "info")
    return redirect(url_for("imports.detail", batch_id=batch_id))


@imports.route("/<batch_id>/cancel", methods=["POST"])
@modulo_activo("imports")
@login_required
def cancel(batch_id):
    """Solicitar la cancelación de un lote en proceso."""
    check_permission("anular")
    service = ImportService()
    service.cancel(batch_id)
    flash("Cancelación solicitada", "warning")
    return redirect(url_for("imports.detail", batch_id=batch_id))


@imports.route("/template/<record_type>")
@modulo_activo("imports")
@login_required
def download_template(record_type):
    """Generar y descargar plantilla de importación."""
    check_permission("consultar")
    fmt = request.args.get("format", "csv").lower()
    service = ImportService()
    try:
        adapter = service._get_adapter(record_type)
        template_dir = os.path.join(current_app.instance_path, "templates")
        os.makedirs(template_dir, exist_ok=True)

        if fmt == "xlsx":
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(adapter.columns)
            template_path = os.path.join(template_dir, f"template_{record_type}.xlsx")
            wb.save(template_path)
            return send_file(template_path, as_attachment=True, download_name=f"template_{record_type}.xlsx")

        elif fmt == "ods":
            doc = opendocument.OpenDocumentSpreadsheet()
            spreadsheet = odf_table.Table(name="Template")
            doc.spreadsheet.addElement(spreadsheet)
            tr = odf_table.TableRow()
            spreadsheet.addElement(tr)
            for col in adapter.columns:
                tc = odf_table.TableCell(valuetype="string")
                tc.addElement(opendocument.teletype.Text(col))
                spreadsheet.addElement(tc)
            template_path = os.path.join(template_dir, f"template_{record_type}.ods")
            doc.save(template_path)
            return send_file(template_path, as_attachment=True, download_name=f"template_{record_type}.ods")

        else:
            # Default to CSV
            content = ",".join(adapter.columns)
            template_path = os.path.join(template_dir, f"template_{record_type}.csv")
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(content)
            return send_file(template_path, as_attachment=True, download_name=f"template_{record_type}.csv")

    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("imports.index"))
