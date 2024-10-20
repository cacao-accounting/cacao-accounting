# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Data para el desarrollo."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date, datetime

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import proteger_passwd as _pg
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    CostCenter,
    Entity,
    ExchangeRate,
    Project,
    Serie,
    Unit,
)

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------


BASE_USUARIOS = [
    {
        "user": "admin",
        "e_mail": "a@dm.com",
        "password": _pg("admin"),
    },
    {
        "user": "audit",
        "e_mail": "au@dm.com",
        "password": _pg("audit"),
    },
    {
        "user": "analist",
        "e_mail": "an@dm.com",
        "password": _pg("analist"),
    },
    {
        "user": "conta",
        "e_mail": "con@dm.com",
        "password": _pg("conta"),
    },
    {
        "user": "contaj",
        "e_mail": "conj@dm.com",
        "password": _pg("contaj"),
    },
    {
        "user": "compras",
        "e_mail": "compras@dm.com",
        "password": _pg("compras"),
    },
    {
        "user": "comprasj",
        "e_mail": "comprasj@dm.com",
        "password": _pg("comprasj"),
    },
    {
        "user": "ventas",
        "e_mail": "ventas@dm.com",
        "password": _pg("ventas"),
    },
    {
        "user": "ventasj",
        "e_mail": "ventasj@dm.com",
        "password": _pg("ventasj"),
    },
    {
        "user": "inventario",
        "e_mail": "in@dm.com",
        "password": _pg("inventario"),
    },
    {
        "user": "inventarioj",
        "e_mail": "inj@dm.com",
        "password": _pg("inventarioj"),
    },
    {
        "user": "tesoreria",
        "e_mail": "t@dm.com",
        "password": _pg("tesoreria"),
    },
    {
        "user": "tesoreriaj",
        "e_mail": "tj@dm.com",
        "password": _pg("tesoreriaj"),
    },
    {
        "user": "pasante",
        "e_mail": "p@dm.com",
        "password": _pg("pasante"),
    },
    {
        "user": "usuario",
        "e_mail": "u@dm.com",
        "password": _pg("usuario"),
    },
]

USUARIO_ROLES = [
    ("admin", "admin"),
    ("audit", "comptroller"),
    ("analist", "business_analyst"),
    ("conta", "accounting_manager"),
    ("contaj", "accounting_auxiliar"),
    ("compras", "purchasing_manager"),
    ("comprasj", "purchasing_auxiliar"),
    ("ventas", "sales_manager"),
    ("ventasj", "sales_auxiliar"),
    ("inventario", "inventory_manager"),
    ("inventarioj", "inventory_auxiliar"),
    ("tesoreria", "head_of_treasury"),
    ("tesoreriaj", "auxiliar_of_treasury"),
    ("pasante", "purchasing_auxiliar"),
    ("pasante", "accounting_auxiliar"),
    ("pasante", "auxiliar_of_treasury"),
    ("pasante", "inventory_auxiliar"),
    ("pasante", "sales_auxiliar"),
    ("usuario", "purchasing_user"),
    ("usuario", "accounting_user"),
    ("usuario", "inventory_user"),
    ("usuario", "user_of_treasury"),
    ("usuario", "sales_user"),
]

UNIDADES = (
    Unit(
        name="Casa Matriz",
        entity="cacao",
        code="matriz",
        status="active",
    ),
    Unit(
        name="Movil",
        entity="cacao",
        code="movil",
        status="active",
    ),
    Unit(
        name="Masaya",
        entity="cacao",
        code="masaya",
        status="inactive",
    ),
)


ENTIDADES = (
    Entity(
        id="01J092PXHEBF4M129A7GZZ48E2",
        code="cacao",
        company_name="Choco Sonrisas Sociedad Anonima",
        name="Choco Sonrisas",
        tax_id="J0310000000000",
        currency="NIO",
        entity_type="Sociedad",
        e_mail="info@chocoworld.com",
        web="chocoworld.com",
        phone1="+505 8456 6543",
        phone2="+505 8456 7543",
        fax="+505 8456 7545",
        enabled=True,
        default=True,
        status="default",
    ),
    Entity(
        id="01J092PXHEBF4M129A7GZZ48I2",
        code="cafe",
        company_name="Mundo Cafe Sociedad Anonima",
        name="Mundo Cafe",
        tax_id="J0310000000001",
        currency="USD",
        entity_type="Sociedad",
        e_mail="info@mundocafe.com",
        web="mundocafe.com",
        phone1="+505 8456 6542",
        phone2="+505 8456 7542",
        fax="+505 8456 7546",
        enabled=True,
        default=False,
        status="active",
    ),
    Entity(
        id="01J092PXHEBF4M129A7GZZ48A2",
        code="dulce",
        company_name="Mundo Sabor Sociedad Anonima",
        name="Dulce Sabor",
        tax_id="J0310000000002",
        currency="NIO",
        entity_type="Sociedad",
        e_mail="info@chocoworld.com",
        web="chocoworld.com",
        phone1="+505 8456 6543",
        phone2="+505 8456 7543",
        fax="+505 8456 7545",
        enabled=False,
        default=False,
        status="inactive",
    ),
)

SERIES = (
    Serie(
        entity="cacao",
        doc="journal",
        enabled=True,
        default=True,
        serie="CD-CACAO",
    ),
    Serie(
        entity="cafe",
        doc="journal",
        enabled=True,
        default=True,
        serie="CD-CAFE",
    ),
    Serie(
        entity="dulce",
        doc="journal",
        enabled=True,
        default=True,
        serie="CD-DULCE",
    ),
)


CUENTAS = (
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6",
        name="Cuenta Prueba Nivel 0",
        group=True,
        parent=None,
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1",
        name="Cuenta Prueba Nivel 1",
        group=True,
        parent="6",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1",
        name="Cuenta Prueba Nivel 2",
        group=True,
        parent="6.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1",
        name="Cuenta Prueba Nivel 3",
        group=True,
        parent="6.1.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1.1",
        name="Cuenta Prueba Nivel 4",
        group=True,
        parent="6.1.1.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1.1.1",
        name="Cuenta Prueba Nivel 5",
        group=True,
        parent="6.1.1.1.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1.1.1.1",
        name="Cuenta Prueba Nivel 6",
        group=True,
        parent="6.1.1.1.1.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1.1.1.1.1",
        name="Cuenta Prueba Nivel 7",
        group=True,
        parent="6.1.1.1.1.1.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1.1.1.1.1.1",
        name="Cuenta Prueba Nivel 8",
        group=True,
        parent="6.1.1.1.1.1.1.1",
    ),
    Accounts(
        active=True,
        enabled=True,
        entity="cacao",
        code="6.1.1.1.1.1.1.1.1.1",
        name="Cuenta Prueba Nivel 9",
        group=False,
        parent="6.1.1.1.1.1.1.1.1",
    ),
)

CENTROS_DE_COSTOS = (
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=False,
        code="A00000",
        name="Centro Costos Predeterminado",
        status="active",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=True,
        code="B00000",
        name="Centro Costos Nivel 0",
        status="active",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=True,
        code="B00001",
        name="Centro Costos Nivel 1",
        status="active",
        parent="B00000",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=True,
        code="B00011",
        name="Centro Costos Nivel 2",
        status="active",
        parent="B00001",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=True,
        code="B00111",
        name="Centro Costos Nivel 3",
        status="active",
        parent="B00011",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=True,
        code="B01111",
        name="Centro Costos Nivel 4",
        status="active",
        parent="B00111",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cacao",
        group=False,
        code="B11111",
        name="Centro Costos Nivel 5",
        status="active",
        parent="B01111",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="cafe",
        group=False,
        code="A00000",
        name="Centro de Costos Predeterminado",
        status="active",
    ),
    CostCenter(
        active=True,
        default=True,
        enabled=True,
        entity="dulce",
        group=False,
        code="A00000",
        name="Centro de Costos Predeterminados",
        status="active",
    ),
)


PROYECTOS = (
    Project(
        enabled=True,
        entity="cacao",
        code="PTO001",
        name="Proyecto Prueba",
        start=date(year=2020, month=6, day=5),
        end=date(year=2020, month=9, day=5),
        budget=10000,
        status="open",
    ),
    Project(
        enabled=True,
        entity="dulce",
        code="PTO002",
        name="Proyecto Demo",
        start=date(year=2024, month=6, day=5),
        end=date(year=2024, month=9, day=5),
        budget=10000,
        status="open",
    ),
    Project(
        enabled=True,
        entity="cacao",
        code="PTO003",
        name="Proyecto Demostracion",
        start=date(year=2024, month=6, day=5),
        end=date(year=2024, month=9, day=5),
        budget=10000,
        status="open",
    ),
)

TASAS_DE_CAMBIO = (
    ExchangeRate(
        origin="NIO",
        destination="USD",
        rate=34.5984,
        date=date(year=int(datetime.now().year), month=6, day=30),
    ),
    ExchangeRate(
        origin="NIO",
        destination="USD",
        rate=34.5984,
        date=date(year=int(datetime.now().year), month=6, day=29),
    ),
    ExchangeRate(
        origin="NIO",
        destination="USD",
        rate=34.5964,
        date=date(year=int(datetime.now().year), month=6, day=28),
    ),
)

PERIODOS = (
    AccountingPeriod(
        entity="cacao",
        name=str(datetime.now().year),
        status="open",
        enabled=False,
        start=date(year=datetime.now().year, month=1, day=1),
        end=date(year=datetime.now().year, month=12, day=31),
    ),
    AccountingPeriod(
        entity="cacao",
        name=str(int(datetime.now().year) - 1),
        status="closed",
        enabled=False,
        start=date(year=(int(datetime.now().year) - 1), month=1, day=1),
        end=date(year=(int(datetime.now().year) - 1), month=12, day=31),
    ),
)
