"""Infraestructura moderna para pytest con SQLite en memoria y aislamiento transaccional."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from argon2 import PasswordHasher
from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    ExchangeRate,
    FiscalYear,
    Item,
    Modules,
    Party,
    Roles,
    RolesUser,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)

ph = PasswordHasher()


def pytest_addoption(parser):
    """Registrar banderas históricas del proyecto."""
    parser.addoption("--slow", action="store", default="False", help="Run all tests, even the slowest ones.")
    parser.addoption("--full", action="store_true", default=False, help="Run full end-to-end business-cycle tests.")


def _check_database_habilitado() -> bool:
    """Verifica si las pruebas de motor real están habilitadas."""
    return os.environ.get("CHECK_DATABASE", "").strip().lower() in {"1", "true", "yes"}


def pytest_collection_modifyitems(config, items):
    """Salta pruebas de motor real cuando no se habilita CHECK_DATABASE."""
    if _check_database_habilitado():
        return
    skip_database = pytest.mark.skip(reason="Habilita CHECK_DATABASE=true para validar contra un motor real")
    for item in items:
        if "database" in item.keywords:
            item.add_marker(skip_database)


def _seed_worker_base_data(app: Flask) -> None:
    """Crea únicamente los datos base necesarios para cada worker."""
    with app.app_context():
        database.create_all()

        for code, name in (("NIO", "Córdoba"), ("USD", "Dólar")):
            if database.session.execute(select(Currency).filter_by(code=code)).scalar_one_or_none() is None:
                database.session.add(Currency(code=code, name=name, decimals=2, active=True, default=code == "NIO"))

        if database.session.execute(select(Entity).filter_by(code="cacao")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )

        if database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one_or_none() is None:
            database.session.add(
                Book(
                    entity="cacao",
                    code="DEFAULT_BOOK",
                    name="Default",
                    status="activo",
                    is_primary=True,
                    currency="NIO",
                )
            )

        for module_name in ("accounting", "sales", "purchases", "cash", "inventory"):
            if database.session.execute(select(Modules).filter_by(module=module_name)).scalar_one_or_none() is None:
                database.session.add(Modules(module=module_name, default=module_name == "accounting", enabled=True))

        admin_user = database.session.execute(select(User).filter_by(user="admin")).scalar_one_or_none()
        if admin_user is None:
            database.session.add(
                User(
                    user="admin",
                    name="Admin",
                    password=ph.hash("AdminPass!123").encode(),
                    classification="admin",
                    active=True,
                    company="cacao",
                )
            )

        database.session.commit()


@pytest.fixture(scope="session")
def app():
    """App de prueba con SQLite en memoria creada una sola vez por worker."""
    settings = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        },
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "SECRET_KEY": "test-worker-secret",
    }
    application: Flask = create_app(settings)

    with application.app_context():
        _seed_worker_base_data(application)

    yield application

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def db_session(app):
    """Cada prueba recibe su propia sesión y transacción externa de aislamiento."""
    with app.app_context():
        connection = database.engine.connect()
        connection.connection.cursor().execute("PRAGMA foreign_keys=ON")
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        session.begin_nested()
        try:
            yield session
        finally:
            session.rollback()
            session.close()
            transaction.rollback()
            connection.close()


@pytest.fixture
def client(app):
    """Cliente HTTP independiente por prueba."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="session")
def reference_users(app):
    """Usuarios base reutilizados por perfil para la autenticación de pruebas."""
    with app.app_context():
        session = database.session()
        if session.execute(select(Entity).filter_by(code="alpha")).scalar_one_or_none() is None:
            session.add(
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha Company",
                    tax_id="J0002",
                    currency="USD",
                    enabled=True,
                    status="default",
                )
            )

        users: dict[str, User] = {}
        for username, classification, company_code, password in (
            ("admin", "admin", "cacao", "AdminPass!123"),
            ("reader", "reader", "cacao", "ReaderPass!123"),
            ("writer", "writer", "cacao", "WriterPass!123"),
            ("no_access", "user", "cacao", "NoAccessPass!123"),
            ("other_company", "user", "alpha", "OtherCompanyPass!123"),
            ("limited_company", "user", "cacao", "LimitedPass!123"),
        ):
            user = session.execute(select(User).filter_by(user=username)).scalar_one_or_none()
            if user is None:
                user = User(
                    user=username,
                    name=username.title(),
                    password=ph.hash(password).encode(),
                    classification=classification,
                    active=True,
                    company=company_code,
                )
                session.add(user)
            users[username] = user

        session.flush()

        for username, company_code in (
            ("admin", "cacao"),
            ("reader", "cacao"),
            ("writer", "cacao"),
            ("limited_company", "cacao"),
            ("other_company", "alpha"),
        ):
            access = session.execute(
                select(UserCompanyAccess).filter_by(user_id=users[username].id, company_code=company_code)
            ).scalar_one_or_none()
            if access is None:
                session.add(UserCompanyAccess(user_id=users[username].id, company_code=company_code))

        for role_name in ("admin", "reader", "writer", "auditor"):
            role = session.execute(select(Roles).filter_by(name=role_name)).scalar_one_or_none()
            if role is None:
                role = Roles(name=role_name, note=f"{role_name} role")
                session.add(role)
            session.flush()
            if role_name == "admin":
                assignment = session.execute(
                    select(RolesUser).filter_by(user_id=users["admin"].id, role_id=role.id)
                ).scalar_one_or_none()
                if assignment is None:
                    session.add(RolesUser(user_id=users["admin"].id, role_id=role.id, active=True))

        session.commit()
        yield users
        session.close()


@pytest.fixture
def authenticated_client(app, reference_users):
    """Cliente HTTP autenticado por perfil sin repetir el hash de password."""

    def _factory(username: str = "admin"):
        user = reference_users[username]
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    return _factory


@dataclass(frozen=True)
class EntornoContable:
    """Escenario mínimo para pruebas contables y operativas."""

    app: Any
    company: Any
    book_primary: Any
    book_secondary: Any
    fiscal_year: Any
    period: Any
    currency_nio: Any
    currency_usd: Any
    caja: Any
    banco: Any
    cxc: Any
    inv_account: Any
    cxp: Any
    iva_por_pagar: Any
    ventas: Any
    cogs: Any
    gastos: Any
    defaults: Any
    customer: Any
    supplier: Any
    uom: Any
    item: Any
    warehouse: Any
    admin_user: Any


@pytest.fixture
def entorno_contable(app) -> EntornoContable:
    """Semilla mínima para escenarios contables y operativos."""
    with app.app_context():
        company = database.session.execute(select(Entity).filter_by(code="cacao")).scalar_one()
        admin_user = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        book_primary = database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()

        book_secondary = database.session.execute(select(Book).filter_by(code="NIIF")).scalar_one_or_none()
        if book_secondary is None:
            book_secondary = Book(
                entity="cacao",
                code="NIIF",
                name="Libro NIIF",
                status="activo",
                is_primary=False,
                currency="NIO",
            )
            database.session.add(book_secondary)

        for code, name in (("NIO", "Córdoba"), ("USD", "Dólar")):
            if database.session.execute(select(Currency).filter_by(code=code)).scalar_one_or_none() is None:
                database.session.add(Currency(code=code, name=name, decimals=2, active=True, default=code == "NIO"))

        fy = database.session.execute(select(FiscalYear).filter_by(entity="cacao")).scalar_one_or_none()
        if fy is None:
            fy = FiscalYear(
                id="FY2026",
                entity="cacao",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
            database.session.add(fy)

        period = database.session.execute(select(AccountingPeriod).filter_by(entity="cacao")).scalar_one_or_none()
        if period is None:
            period = AccountingPeriod(
                id="P2026-05",
                entity="cacao",
                fiscal_year_id="FY2026",
                name="Mayo 2026",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                enabled=True,
                is_closed=False,
            )
            database.session.add(period)

        for code, name, classification, account_type in (
            ("1101", "Caja General", "asset", "cash"),
            ("1102", "Bancos", "asset", "bank"),
            ("1105", "Cuentas por Cobrar", "asset", "receivable"),
            ("1109", "Inventarios", "asset", "stock"),
            ("2101", "Cuentas por Pagar", "liability", "payable"),
            ("2105", "IVA por Pagar", "liability", "tax"),
            ("4101", "Ventas", "revenue", "income"),
            ("5101", "Costo de Ventas", "expense", "expense"),
            ("5201", "Gastos Operativos", "expense", "expense"),
        ):
            account = database.session.execute(select(Accounts).filter_by(entity="cacao", code=code)).scalar_one_or_none()
            if account is None:
                database.session.add(
                    Accounts(
                        entity="cacao",
                        code=code,
                        name=name,
                        classification=classification,
                        account_type=account_type,
                    )
                )

        database.session.flush()

        caja = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        banco = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1102")).scalar_one()
        cxc = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1105")).scalar_one()
        inv_account = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        cxp = database.session.execute(select(Accounts).filter_by(entity="cacao", code="2101")).scalar_one()
        iva_por_pagar = database.session.execute(select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
        ventas = database.session.execute(select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        cogs = database.session.execute(select(Accounts).filter_by(entity="cacao", code="5101")).scalar_one()
        gastos = database.session.execute(select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()

        defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one_or_none()
        if defaults is None:
            defaults = CompanyDefaultAccount(
                company="cacao",
                default_receivable=cxc.id,
                default_payable=cxp.id,
                default_cash=caja.id,
                default_bank=banco.id,
                default_income=ventas.id,
                default_expense=gastos.id,
            )
            database.session.add(defaults)

        if database.session.execute(select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad"))

        customer = database.session.execute(select(Party).filter_by(code="CLI001")).scalar_one_or_none()
        if customer is None:
            customer = Party(code="CLI001", name="Cliente Principal SA", is_customer=True, tax_id="J0002")
            database.session.add(customer)

        supplier = database.session.execute(select(Party).filter_by(code="PRV001")).scalar_one_or_none()
        if supplier is None:
            supplier = Party(code="PRV001", name="Proveedor Principal SA", is_supplier=True, tax_id="J0003")
            database.session.add(supplier)

        warehouse = database.session.execute(select(Warehouse).filter_by(code="BOD01")).scalar_one_or_none()
        if warehouse is None:
            warehouse = Warehouse(code="BOD01", name="Bodega Central", company="cacao")
            database.session.add(warehouse)

        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one_or_none()
        if item is None:
            item = Item(code="ART01", name="Articulo Comercial", item_type="goods", is_stock_item=True, default_uom="UND")
            database.session.add(item)

        exchange_rate = database.session.execute(
            select(ExchangeRate).filter_by(origin="USD", destination="NIO", date=date(2026, 5, 1))
        ).scalar_one_or_none()
        if exchange_rate is None:
            database.session.add(
                ExchangeRate(
                    origin="USD",
                    destination="NIO",
                    rate=Decimal("36.50"),
                    date=date(2026, 5, 1),
                )
            )
            database.session.add(
                ExchangeRate(
                    origin="NIO",
                    destination="USD",
                    rate=Decimal("1") / Decimal("36.50"),
                    date=date(2026, 5, 1),
                )
            )

        database.session.commit()

        return EntornoContable(
            app=app,
            company=company,
            book_primary=book_primary,
            book_secondary=book_secondary,
            fiscal_year=fy,
            period=period,
            currency_nio=database.session.execute(select(Currency).filter_by(code="NIO")).scalar_one(),
            currency_usd=database.session.execute(select(Currency).filter_by(code="USD")).scalar_one(),
            caja=caja,
            banco=banco,
            cxc=cxc,
            inv_account=inv_account,
            cxp=cxp,
            iva_por_pagar=iva_por_pagar,
            ventas=ventas,
            cogs=cogs,
            gastos=gastos,
            defaults=defaults,
            customer=customer,
            supplier=supplier,
            uom=database.session.execute(select(UOM).filter_by(code="UND")).scalar_one(),
            item=item,
            warehouse=warehouse,
            admin_user=admin_user,
        )
