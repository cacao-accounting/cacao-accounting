# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Datos de ejemplo."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
import json
from datetime import date

from cacao_accounting.auth.roles import asigna_rol_a_usuario
from cacao_accounting.database import database
from cacao_accounting.datos.dev.data import (
    BASE_USUARIOS,
    USUARIO_ROLES,
    _make_articulos,
    _make_bancos,
    _make_bodegas,
    _make_centros_de_costos,
    _make_comprobantes_contables,
    _make_cuentas,
    _make_documentos,
    _make_entidades,
    _make_items_entrega,
    _make_items_factura_compra,
    _make_items_factura_venta,
    _make_items_orden_compra,
    _make_items_orden_venta,
    _make_items_recepcion,
    _make_periodos,
    _make_proyectos,
    _make_recurring_templates,
    _make_series,
    _make_tasas_de_cambio,
    _make_terceros,
    _make_unidades,
    _make_unidades_medida,
)
from cacao_accounting.logs import log


def asignar_usuario_a_roles():
    """Asigna roles a usuarios."""
    for r in USUARIO_ROLES:
        asigna_rol_a_usuario(r[0], r[1])


def demo_usuarios():
    """Usuarios para demostracion."""
    from cacao_accounting.database import User

    for u in BASE_USUARIOS:
        exists = database.session.execute(database.select(User).filter_by(user=u.get("user"))).scalars().first()
        if exists:
            continue
        usuario = User(
            user=u.get("user"),
            e_mail=u.get("e_mail"),
            password=u.get("password"),
            created_by="system",
        )
        database.session.add(usuario)
    database.session.commit()


def demo_entidad():
    """Entidad de demostración."""
    from cacao_accounting.compras.purchase_reconciliation_service import seed_matching_config_for_company
    from cacao_accounting.setup.service import create_company

    fiscal_year_start = date(date.today().year, 1, 1)
    fiscal_year_end = date(date.today().year, 12, 31)

    for e in _make_entidades():
        company_data = {
            "id": e.code,
            "razon_social": e.company_name,
            "nombre_comercial": e.name,
            "id_fiscal": e.tax_id,
            "moneda": e.currency,
            "pais": e.country,
            "tipo_entidad": e.entity_type,
            "correo_electronico": e.e_mail,
            "web": e.web,
            "telefono1": e.phone1,
            "telefono2": e.phone2,
            "fax": e.fax,
            "inicio_anio_fiscal": fiscal_year_start,
            "fin_anio_fiscal": fiscal_year_end,
        }
        create_company(
            company_data,
            status=e.status or "active",
            default=bool(e.default),
        )
        seed_matching_config_for_company(e.code)
    database.session.commit()


def series_predeterminadas():
    """Crear series predeterminadas."""
    for s in _make_series():
        database.session.add(s)
    database.session.commit()


def demo_unidades():
    """Unidades de Negocio de Demostración."""
    for u in _make_unidades():
        database.session.add(u)
    database.session.commit()


def cargar_catalogo_de_cuentas():
    """Catalogo de cuentas de demostración."""
    from cacao_accounting.contabilidad.ctas import base, cargar_catalogos
    from cacao_accounting.contabilidad.default_accounts import apply_catalog_default_mapping

    log.debug("Cargando catalogos de cuentas.")
    for company in ("cacao", "dulce", "cafe"):
        cargar_catalogos(base, company)
        apply_catalog_default_mapping(company, base.file)

    for c in _make_cuentas():
        database.session.add(c)
    database.session.commit()


def cargar_centros_de_costos():
    """Centros de Costos de demostración."""
    for cc in _make_centros_de_costos():
        database.session.add(cc)
    database.session.commit()


def cargar_proyectos():
    """Proyectos de demostración."""
    for p in _make_proyectos():
        database.session.add(p)
    database.session.commit()


def demo_libros():
    """Libros contables adicionales para la empresa cacao."""
    from cacao_accounting.database import Book

    libros = [
        Book(code="FIN", name="Financiero", entity="cacao", currency="USD", is_primary=False, default=False, status="activo"),
        Book(code="MGMT", name="Gerencia", entity="cacao", currency="EUR", is_primary=False, default=False, status="activo"),
    ]
    for lib in libros:
        database.session.add(lib)
    database.session.commit()


def cargar_comprobantes():
    """Crea y contabiliza comprobantes de demostración."""
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal

    for c in _make_comprobantes_contables():
        journal = create_journal_draft(c, user_id="admin")
        submit_journal(journal.id)


def cargar_plantillas_recurrentes():
    """Crea plantillas recurrentes de demostración."""
    from cacao_accounting.contabilidad.recurring_journal_service import create_recurring_template

    for t in _make_recurring_templates():
        create_recurring_template(t["data"], t["items"], user_id="admin")


def tasas_de_cambio():
    """Tasa de Cambio de demostración."""
    for t in _make_tasas_de_cambio():
        database.session.add(t)
    database.session.commit()


def cargar_bancos():
    """Bancos, cuentas bancarias y chequeras de demostración."""
    from cacao_accounting.database import (
        Bank,
        BankAccount,
        ExternalCounter,
        NamingSeries,
        SeriesExternalCounterMap,
    )
    from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

    for b in _make_bancos():
        database.session.add(b)
    database.session.flush()

    ensure_default_naming_series_for_company("cacao", ["payment_entry"])
    payment_series = (
        database.session.execute(
            database.select(NamingSeries)
            .filter_by(company="cacao", entity_type="payment_entry", is_active=True)
            .order_by(NamingSeries.is_default.desc(), NamingSeries.name)
        )
        .scalars()
        .first()
    )
    if payment_series is None:
        raise RuntimeError("No se pudo preparar la serie compartida de pagos para el seed.")

    bank_by_name = {
        bank.name: bank for bank in database.session.execute(database.select(Bank).order_by(Bank.name)).scalars().all()
    }
    bank_accounts_data = [
        {
            "bank": bank_by_name["Banco Nacional de Desarrollo"],
            "account_name": "Cuenta Corriente Cacao NIO",
            "account_no": "CTA-DEMO-NIO",
            "currency": "NIO",
            "counter_name": "Chequera Cacao NIO",
            "counter_prefix": "NIO-CHK-",
        },
        {
            "bank": bank_by_name["Banco de América Central"],
            "account_name": "Cuenta Corriente Cacao USD",
            "account_no": "CTA-DEMO-USD",
            "currency": "USD",
            "counter_name": "Chequera Cacao USD",
            "counter_prefix": "USD-CHK-",
        },
    ]
    for data in bank_accounts_data:
        counter = ExternalCounter(
            company="cacao",
            name=data["counter_name"],
            counter_type="checkbook",
            prefix=data["counter_prefix"],
            last_used=0,
            padding=5,
            is_active=True,
            naming_series_id=payment_series.id,
        )
        database.session.add(counter)
        database.session.flush()
        bank_account = BankAccount(
            bank_id=data["bank"].id,
            company="cacao",
            account_name=data["account_name"],
            account_no=data["account_no"],
            currency=data["currency"],
            default_naming_series_id=payment_series.id,
            default_external_counter_id=counter.id,
            is_active=True,
        )
        database.session.add(bank_account)
        database.session.flush()
        database.session.add(
            SeriesExternalCounterMap(
                naming_series_id=payment_series.id,
                external_counter_id=counter.id,
                priority=0,
                condition_json=json.dumps({"bank_account_id": bank_account.id}, sort_keys=True),
            )
        )
    database.session.commit()


def cargar_terceros():
    """Terceros de demostración."""
    for t in _make_terceros():
        database.session.add(t)
    database.session.commit()


def cargar_unidades_medida():
    """Unidades de medida de demostración."""
    for u in _make_unidades_medida():
        database.session.add(u)
    database.session.commit()


def cargar_articulos():
    """Articulos de demostración."""
    for a in _make_articulos():
        database.session.add(a)
    database.session.commit()


def cargar_bodegas():
    """Bodegas de demostración."""
    for b in _make_bodegas():
        database.session.add(b)
    database.session.commit()


def master_data():
    """Carga datos maestros de desarrollo a la base de datos."""
    log.info("Iniciando carga de master data de pruebas.")

    demo_usuarios()
    asignar_usuario_a_roles()
    demo_entidad()
    demo_libros()
    demo_unidades()
    cargar_centros_de_costos()
    cargar_proyectos()
    tasas_de_cambio()
    cargar_catalogo_de_cuentas()
    cargar_bancos()
    cargar_terceros()
    cargar_unidades_medida()
    cargar_articulos()
    cargar_bodegas()

    log.debug("Master data de prueba creada correctamente.")


def periodo_contable():
    """Crea periodos contables para desarrollo."""
    for p in _make_periodos():
        database.session.add(p)
    database.session.commit()


def transacciones():
    """Crea transacciones de desarrollo en la base de datos."""
    periodo_contable()
    _cargar_documentos_demo()
    cargar_comprobantes()
    cargar_plantillas_recurrentes()
    log.debug("Transacciones de Pruebas Creadas correctamente.")


def _cargar_documentos_demo():
    """Crea documentos transaccionales de demostración."""
    for d in _make_documentos():
        database.session.add(d)
    database.session.commit()
    for i in _make_items_orden_compra():
        database.session.add(i)
    for i in _make_items_orden_venta():
        database.session.add(i)
    for i in _make_items_recepcion():
        database.session.add(i)
    for i in _make_items_factura_compra():
        database.session.add(i)
    for i in _make_items_entrega():
        database.session.add(i)
    for i in _make_items_factura_venta():
        database.session.add(i)
    database.session.commit()


def dev_data():
    """Carga datos de desarrollo a la base de datos."""
    log.trace("Iniciando carga de datos de prueba.")
    master_data()
    transacciones()
