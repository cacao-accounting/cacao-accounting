# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1938: vistas guardadas de reportes con RBAC y aislamiento por compañía."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import SavedReportView, User, UserCompanyAccess, database
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


def test_no_permite_nombres_duplicados(app, entorno_contable):
    """El nombre es único por usuario, compañía y reporte."""
    with app.app_context():
        admin = _admin_id()
        nombre = f"Duplicada {uuid4().hex[:6]}"
        create_saved_view("account-movement", "cacao", admin, nombre, _filters())
        with pytest.raises(SavedReportViewError, match="Ya existe"):
            create_saved_view("account-movement", "cacao", admin, nombre, _filters())


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
        with pytest.raises(SavedReportViewError, match="inválidas"):
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
