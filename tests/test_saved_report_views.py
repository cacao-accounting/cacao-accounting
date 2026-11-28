# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1938: vistas guardadas de reportes con RBAC y aislamiento por compañía."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Accounts,
    Book,
    GLEntry,
    SalesInvoice,
    SavedReportView,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.reportes.saved_views_service import (
    SavedReportViewError,
    create_saved_view,
    delete_saved_view,
    get_saved_view,
    list_saved_views,
    restore_filters,
    view_display,
)
from cacao_accounting.reportes.services import FinancialReportFilters


def _filters(**overrides) -> FinancialReportFilters:
    """Construye filtros representativos del reporte de movimientos."""
    values = {
        "company": "cacao",
        "ledger": "DEFAULT_BOOK",
        "account_code": "1101",
        "page_size": 25,
        "sort_by": "posting_date",
        "sort_dir": "desc",
        "include_cancellations": True,
    }
    values.update(overrides)
    return FinancialReportFilters(**values)


def _admin_id() -> str:
    """Devuelve el usuario administrador de las pruebas."""
    return str(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one().id)


def test_guarda_recupera_y_aplica_filtros_y_preferencias(app, entorno_contable):
    """La vista conserva filtros y columnas y los restaura sobre el reporte."""
    with app.app_context():
        admin = _admin_id()
        view = create_saved_view(
            "account-movement",
            "cacao",
            admin,
            f"Vista {uuid4().hex[:6]}",
            _filters(),
            {"visible_columns": ["debit", "credit"], "group_by": "account_code", "page_size": 25},
        )

        almacenadas = list_saved_views("account-movement", "cacao", admin)
        assert view in almacenadas
        restaurados = restore_filters(_filters(account_code=None, page_size=100), view)
        assert restaurados.account_code == "1101"
        assert restaurados.page_size == 25
        assert restaurados.include_cancellations is True
        assert view_display(view)["visible_columns"] == ["debit", "credit"]
        assert view_display(view)["group_by"] == "account_code"

        delete_saved_view(view.id, "account-movement", "cacao", admin)
        assert database.session.get(SavedReportView, view.id) is None


def test_vista_booleana_false_sobrescribe_true_de_request(app, entorno_contable):
    """#1938: un False guardado debe prevalecer sobre True en la URL/request."""
    with app.app_context():
        admin = _admin_id()
        view = create_saved_view(
            "account-movement",
            "cacao",
            admin,
            f"Sin canceladas {uuid4().hex[:6]}",
            _filters(include_cancellations=False),
        )
        restaurados = restore_filters(_filters(include_cancellations=True), view)
        assert restaurados.include_cancellations is False

        view_true = create_saved_view(
            "account-movement",
            "cacao",
            admin,
            f"Con canceladas {uuid4().hex[:6]}",
            _filters(include_cancellations=True),
        )
        restaurados_true = restore_filters(_filters(include_cancellations=False), view_true)
        assert restaurados_true.include_cancellations is True


def test_no_permite_nombres_duplicados(app, entorno_contable):
    """El nombre es único por usuario, compañía y reporte."""
    with app.app_context():
        admin = _admin_id()
        nombre = f"Duplicada {uuid4().hex[:6]}"
        create_saved_view("account-movement", "cacao", admin, nombre, _filters())
        with pytest.raises(SavedReportViewError, match="Ya existe"):
            create_saved_view("account-movement", "cacao", admin, nombre, _filters())


def test_colision_de_unicidad_al_confirmar_se_convierte_en_error_de_dominio(app, entorno_contable, monkeypatch):
    """Una carrera contra la clave única revierte la sesión y da error controlado."""
    with app.app_context():
        admin = _admin_id()
        monkeypatch.setattr(
            database.session,
            "commit",
            lambda: (_ for _ in ()).throw(
                IntegrityError(
                    "insert",
                    {},
                    Exception(
                        "UNIQUE constraint failed: saved_report_view.company, "
                        "saved_report_view.user_id, saved_report_view.report_code, saved_report_view.name"
                    ),
                )
            ),
        )

        with pytest.raises(SavedReportViewError, match="Ya existe"):
            create_saved_view("account-movement", "cacao", admin, f"Carrera {uuid4().hex[:6]}", _filters())

        assert not database.session.new
        assert database.session.is_active


def test_una_vista_ajena_no_es_visible(app, entorno_contable):
    """Otro usuario con acceso a la compañía no recupera la vista del propietario."""
    with app.app_context():
        admin = _admin_id()
        view = create_saved_view("account-movement", "cacao", admin, f"Privada {uuid4().hex[:6]}", _filters())
        ajeno = User(
            user=f"viewer-{uuid4().hex[:8]}",
            name="Viewer",
            password=proteger_passwd("ViewerPass!123"),
            classification="admin",
            active=True,
            company="cacao",
        )
        database.session.add(ajeno)
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=ajeno.id, company_code="cacao"))
        database.session.commit()

        assert list_saved_views("account-movement", "cacao", str(ajeno.id)) == []
        with pytest.raises(SavedReportViewError, match="no existe"):
            get_saved_view(view.id, "account-movement", "cacao", str(ajeno.id))
        with pytest.raises(SavedReportViewError):
            get_saved_view(view.id, "account-movement", "alpha", admin)


def test_sin_permiso_de_reportes_no_administra_vistas(app, entorno_contable):
    """Un usuario sin acceso a la compañía no lista ni recupera vistas."""
    with app.app_context():
        sin_acceso = User(
            user=f"sin-acceso-{uuid4().hex[:8]}",
            name="Sin acceso",
            password=proteger_passwd("SinAcceso!123"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(sin_acceso)
        database.session.commit()
        with pytest.raises(SavedReportViewError, match="permisos"):
            list_saved_views("account-movement", "cacao", str(sin_acceso.id))


def test_una_vista_corrupta_se_rechaza(app, entorno_contable):
    """El JSON persistido no se interpreta de forma permisiva."""
    with app.app_context():
        admin = _admin_id()
        view = create_saved_view("account-movement", "cacao", admin, f"Corrupta {uuid4().hex[:6]}", _filters())
        view.filters_json = "{"
        database.session.commit()
        with pytest.raises(SavedReportViewError):
            view_display(view)


def test_guarda_aplica_y_elimina_por_http(app, entorno_contable, authenticated_client):
    """El flujo HTTP conserva la vista y la aplica al reporte."""
    client = authenticated_client()
    nombre = f"HTTP {uuid4().hex[:6]}"
    query = "company=cacao&apply_filters=1&account_code=1101&page_size=25&visible_columns=debit"
    response = client.post(
        f"/reports/views/save?{query}",
        data={
            "report_code": "account-movement",
            "company": "cacao",
            "name": nombre,
            "return_url": "/reports/account-movement",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        admin = _admin_id()
        view = database.session.execute(
            database.select(SavedReportView).filter_by(user_id=admin, report_code="account-movement", name=nombre)
        ).scalar_one()

    aplicada = client.get(f"/reports/account-movement?company=cacao&apply_filters=1&account_code=1101&saved_view={view.id}")
    assert aplicada.status_code == 200
    html = aplicada.get_data(as_text=True)
    assert nombre in html
    assert "saved-view-select" in html

    eliminada = client.post(
        f"/reports/views/{view.id}/delete?company=cacao&apply_filters=1",
        data={"report_code": "account-movement", "return_url": "/reports/account-movement"},
    )
    assert eliminada.status_code == 302
    with app.app_context():
        assert database.session.get(SavedReportView, view.id) is None


def test_vista_nueva_no_hereda_filtro_textual_ausente(app, entorno_contable):
    """#2338: aplicar una vista guardada sin account_code limpia el valor de la URL."""
    with app.app_context():
        admin = _admin_id()
        view = create_saved_view(
            "account-movement",
            "cacao",
            admin,
            f"Sin cuenta {uuid4().hex[:6]}",
            _filters(account_code=None, voucher_number=None),
        )
        try:
            restaurados = restore_filters(
                _filters(account_code="1101", voucher_number="AST-1"),
                view,
            )
            assert restaurados.account_code is None
            assert restaurados.voucher_number is None
            # Los filtros que sí estaban guardados se conservan.
            assert restaurados.ledger == "DEFAULT_BOOK"
            assert restaurados.page_size == 25
        finally:
            delete_saved_view(view.id, "account-movement", "cacao", admin)


def test_vista_nueva_con_filtro_textual_lo_aplica_sobre_url_vacia(app, entorno_contable):
    """El caso inverso: un filtro guardado se restaura aunque la URL no lo traiga."""
    with app.app_context():
        admin = _admin_id()
        view = create_saved_view(
            "account-movement",
            "cacao",
            admin,
            f"Con cuenta {uuid4().hex[:6]}",
            _filters(account_code="1101", voucher_number="AST-9"),
        )
        try:
            restaurados = restore_filters(_filters(account_code=None, voucher_number=None), view)
            assert restaurados.account_code == "1101"
            assert restaurados.voucher_number == "AST-9"
        finally:
            delete_saved_view(view.id, "account-movement", "cacao", admin)


def test_vista_heredada_conserva_filtro_de_la_url(app, entorno_contable):
    """Una vista previa sin marca explícita no borra filtros que nunca guardó."""
    with app.app_context():
        admin = _admin_id()
        view = SavedReportView(
            report_code="account-movement",
            company="cacao",
            user_id=admin,
            name=f"Heredada {uuid4().hex[:6]}",
            filters_json='{"ledger": "DEFAULT_BOOK"}',
            display_json="{}",
            created_by=admin,
            modified_by=admin,
        )
        database.session.add(view)
        database.session.commit()
        try:
            restaurados = restore_filters(_filters(account_code="1101"), view)
            assert restaurados.account_code == "1101"
            assert restaurados.ledger == "DEFAULT_BOOK"
        finally:
            delete_saved_view(view.id, "account-movement", "cacao", admin)


def test_http_vista_sin_filtro_textual_descarta_parametro_de_la_url(app, entorno_contable, authenticated_client):
    """#2338: la pantalla aplicada no muestra el account_code de la URL actual."""
    client = authenticated_client()
    nombre = f"HTTP vacia {uuid4().hex[:6]}"
    response = client.post(
        "/reports/views/save?company=cacao&apply_filters=1&page_size=25",
        data={
            "report_code": "account-movement",
            "company": "cacao",
            "name": nombre,
            "return_url": "/reports/account-movement",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        admin = _admin_id()
        view = database.session.execute(
            database.select(SavedReportView).filter_by(user_id=admin, report_code="account-movement", name=nombre)
        ).scalar_one()
        view_id = view.id
    try:
        aplicada = client.get(
            f"/reports/account-movement?company=cacao&apply_filters=1&account_code=1101&saved_view={view_id}"
        )
        assert aplicada.status_code == 200
        html = aplicada.get_data(as_text=True)
        assert nombre in html
        assert 'initialValue: "1101"' not in html
    finally:
        with app.app_context():
            admin = _admin_id()
            delete_saved_view(view_id, "account-movement", "cacao", admin)


def test_http_vista_con_filtro_textual_lo_muestra_sin_parametro_en_la_url(app, entorno_contable, authenticated_client):
    """El filtro guardado se pinta aunque la URL aplicada no lo incluya."""
    client = authenticated_client()
    with app.app_context():
        view = create_saved_view(
            "account-movement",
            "cacao",
            _admin_id(),
            f"HTTP con cuenta {uuid4().hex[:6]}",
            _filters(account_code="1101"),
        )
        view_id = view.id
    try:
        aplicada = client.get(f"/reports/account-movement?company=cacao&apply_filters=1&saved_view={view_id}")
        assert aplicada.status_code == 200
        assert 'initialValue: "1101"' in aplicada.get_data(as_text=True)
    finally:
        with app.app_context():
            delete_saved_view(view_id, "account-movement", "cacao", _admin_id())


def test_vista_restaura_usuarios_y_filtros_avanzados(app, entorno_contable, authenticated_client):
    """Aplicar una vista restaura autoría y panel avanzado sin query params."""
    client = authenticated_client()
    with app.app_context():
        view = create_saved_view(
            "account-movement",
            "cacao",
            _admin_id(),
            f"Indicadores {uuid4().hex[:6]}",
            _filters(),
            {"show_users": True, "advanced": True},
        )
        view_id = view.id

    original = app.jinja_env.globals.get("is_cloud_mode")
    app.jinja_env.globals["is_cloud_mode"] = lambda: True
    try:
        response = client.get(f"/reports/account-movement?company=cacao&apply_filters=1&saved_view={view_id}")
    finally:
        app.jinja_env.globals["is_cloud_mode"] = original

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="advanced" value="1"' in html
    assert 'name="show_users" value="1" checked' in html
    assert 'id="financial-advanced-filters"' in html
    assert 'is-hidden" id="financial-advanced-filters"' not in html


def test_vista_show_users_restaura_columnas_y_datos_de_autoria(entorno_contable_aislado, monkeypatch):
    """Aplicar la vista agrega columnas de autoría y el nombre del creador."""
    import cacao_accounting.document_authorship as authorship

    app = entorno_contable_aislado.app
    admin_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    with app.app_context():
        admin = database.session.get(User, admin_id)
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        libro = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"AU-{uuid4().hex[:8]}",
            created_by=admin.id,
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            GLEntry(
                company="cacao",
                posting_date=date(2026, 5, 15),
                ledger_id=libro.id,
                account_id=cuenta.id,
                account_code=cuenta.code,
                debit=Decimal("125"),
                credit=Decimal("0"),
                voucher_type="sales_invoice",
                voucher_id=factura.id,
                created_by=admin.id,
            )
        )
        database.session.commit()
        view = create_saved_view(
            "account-movement",
            "cacao",
            admin.id,
            f"Autoria {uuid4().hex[:6]}",
            _filters(account_code="1101"),
            {"show_users": True},
        )
        view_id = view.id

    monkeypatch.setattr(authorship, "is_cloud_mode", lambda: True)
    original = app.jinja_env.globals.get("is_cloud_mode")
    app.jinja_env.globals["is_cloud_mode"] = lambda: True
    try:
        respuesta_con_vista = client.get(
            f"/reports/account-movement?company=cacao&apply_filters=1&account_code=1101&page_size=100&saved_view={view_id}"
        )
        respuesta_sin_vista = client.get(
            "/reports/account-movement?company=cacao&apply_filters=1&account_code=1101&page_size=100"
        )
    finally:
        app.jinja_env.globals["is_cloud_mode"] = original

    assert respuesta_con_vista.status_code == 200
    assert respuesta_sin_vista.status_code == 200
    con_vista = respuesta_con_vista.get_data(as_text=True)
    sin_vista = respuesta_sin_vista.get_data(as_text=True)
    assert "Creado por" in con_vista
    assert "Admin" in con_vista
    assert "Creado por" not in sin_vista
