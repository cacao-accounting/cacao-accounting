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
from datetime import date

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import proteger_passwd as _pg
from cacao_accounting.database import CentroCosto, Cuentas, Entidad, PeriodoContable, Proyecto, Serie, TasaDeCambio, Unidad

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------


BASE_USUARIOS = [
    {
        "usuario": "admin",
        "correo_e": "a@dm.com",
        "clave_acceso": _pg("admin"),
    },
    {
        "usuario": "audit",
        "correo_e": "au@dm.com",
        "clave_acceso": _pg("audit"),
    },
    {
        "usuario": "analist",
        "correo_e": "an@dm.com",
        "clave_acceso": _pg("analist"),
    },
    {
        "usuario": "conta",
        "correo_e": "con@dm.com",
        "clave_acceso": _pg("conta"),
    },
    {
        "usuario": "contaj",
        "correo_e": "conj@dm.com",
        "clave_acceso": _pg("contaj"),
    },
    {
        "usuario": "compras",
        "correo_e": "compras@dm.com",
        "clave_acceso": _pg("compras"),
    },
    {
        "usuario": "comprasj",
        "correo_e": "comprasj@dm.com",
        "clave_acceso": _pg("comprasj"),
    },
    {
        "usuario": "ventas",
        "correo_e": "ventas@dm.com",
        "clave_acceso": _pg("ventas"),
    },
    {
        "usuario": "ventasj",
        "correo_e": "ventasj@dm.com",
        "clave_acceso": _pg("ventasj"),
    },
    {
        "usuario": "inventario",
        "correo_e": "in@dm.com",
        "clave_acceso": _pg("inventario"),
    },
    {
        "usuario": "inventarioj",
        "correo_e": "inj@dm.com",
        "clave_acceso": _pg("inventarioj"),
    },
    {
        "usuario": "tesoreria",
        "correo_e": "t@dm.com",
        "clave_acceso": _pg("tesoreria"),
    },
    {
        "usuario": "tesoreriaj",
        "correo_e": "tj@dm.com",
        "clave_acceso": _pg("tesoreriaj"),
    },
    {
        "usuario": "pasante",
        "correo_e": "p@dm.com",
        "clave_acceso": _pg("pasante"),
    },
    {
        "usuario": "usuario",
        "correo_e": "u@dm.com",
        "clave_acceso": _pg("usuario"),
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
    Unidad(
        nombre="Casa Matriz",
        entidad="cacao",
        unidad="matriz",
        status="activo",
    ),
    Unidad(
        nombre="Movil",
        entidad="cacao",
        unidad="movil",
        status="activo",
    ),
    Unidad(
        nombre="Masaya",
        entidad="cacao",
        unidad="masaya",
        status="inactivo",
    ),
)


ENTIDADES = (
    Entidad(
        id="01J092PXHEBF4M129A7GZZ48E2",
        entidad="cacao",
        razon_social="Choco Sonrisas Sociedad Anonima",
        nombre_comercial="Choco Sonrisas",
        id_fiscal="J0310000000000",
        moneda="NIO",
        tipo_entidad="Sociedad",
        correo_electronico="info@chocoworld.com",
        web="chocoworld.com",
        telefono1="+505 8456 6543",
        telefono2="+505 8456 7543",
        fax="+505 8456 7545",
        habilitada=True,
        predeterminada=True,
        status="predeterminado",
    ),
    Entidad(
        entidad="cafe",
        razon_social="Mundo Cafe Sociedad Anonima",
        nombre_comercial="Mundo Cafe",
        id_fiscal="J0310000000001",
        moneda="USD",
        tipo_entidad="Sociedad",
        correo_electronico="info@mundocafe.com",
        web="mundocafe.com",
        telefono1="+505 8456 6542",
        telefono2="+505 8456 7542",
        fax="+505 8456 7546",
        habilitada=True,
        predeterminada=False,
        status="activo",
    ),
    Entidad(
        entidad="dulce",
        razon_social="Mundo Sabor Sociedad Anonima",
        nombre_comercial="Dulce Sabor",
        id_fiscal="J0310000000002",
        moneda="NIO",
        tipo_entidad="Sociedad",
        correo_electronico="info@chocoworld.com",
        web="chocoworld.com",
        telefono1="+505 8456 6543",
        telefono2="+505 8456 7543",
        fax="+505 8456 7545",
        habilitada=False,
        predeterminada=False,
        status="inactivo",
    ),
)

SERIES = (
    Serie(
        entidad="cacao",
        documento="journal",
        habilitada=True,
        predeterminada=True,
        serie="CD-CACAO",
    ),
    Serie(
        entidad="cafe",
        documento="journal",
        habilitada=True,
        predeterminada=True,
        serie="CD-CAFE",
    ),
    Serie(
        entidad="dulce",
        documento="journal",
        habilitada=True,
        predeterminada=True,
        serie="CD-DULCE",
    ),
)


CUENTAS = (
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6",
        nombre="Cuenta Prueba Nivel 0",
        grupo=True,
        padre=None,
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1",
        nombre="Cuenta Prueba Nivel 1",
        grupo=True,
        padre="6",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1",
        nombre="Cuenta Prueba Nivel 2",
        grupo=True,
        padre="6.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1",
        nombre="Cuenta Prueba Nivel 3",
        grupo=True,
        padre="6.1.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1.1",
        nombre="Cuenta Prueba Nivel 4",
        grupo=True,
        padre="6.1.1.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1.1.1",
        nombre="Cuenta Prueba Nivel 5",
        grupo=True,
        padre="6.1.1.1.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1.1.1.1",
        nombre="Cuenta Prueba Nivel 6",
        grupo=True,
        padre="6.1.1.1.1.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1.1.1.1.1",
        nombre="Cuenta Prueba Nivel 7",
        grupo=True,
        padre="6.1.1.1.1.1.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1.1.1.1.1.1",
        nombre="Cuenta Prueba Nivel 8",
        grupo=True,
        padre="6.1.1.1.1.1.1.1",
    ),
    Cuentas(
        activa=True,
        habilitada=True,
        entidad="cacao",
        codigo="6.1.1.1.1.1.1.1.1.1",
        nombre="Cuenta Prueba Nivel 9",
        grupo=False,
        padre="6.1.1.1.1.1.1.1.1",
    ),
)

CENTROS_DE_COSTOS = (
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cacao",
        grupo=False,
        codigo="A00000",
        nombre="Centro Costos Predeterminado",
        status="activo",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cacao",
        grupo=True,
        codigo="B00000",
        nombre="Centro Costos Nivel 0",
        status="activo",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cacao",
        grupo=True,
        codigo="B00001",
        nombre="Centro Costos Nivel 1",
        status="activo",
        padre="B00000",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cacao",
        grupo=True,
        codigo="B00011",
        nombre="Centro Costos Nivel 2",
        status="activo",
        padre="B00001",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cacao",
        grupo=True,
        codigo="B01111",
        nombre="Centro Costos Nivel 4",
        status="activo",
        padre="B00111",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cacao",
        grupo=False,
        codigo="B11111",
        nombre="Centro Costos Nivel 5",
        status="activo",
        padre="B01111",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="cafe",
        grupo=False,
        codigo="A00000",
        nombre="Centro de Costos Predeterminado",
        status="activa",
    ),
    CentroCosto(
        activa=True,
        predeterminado=True,
        habilitada=True,
        entidad="dulce",
        grupo=False,
        codigo="A00000",
        nombre="Centro de Costos Predeterminados",
        status="activa",
    ),
)


PROYECTOS = (
    Proyecto(
        habilitado=True,
        entidad="cacao",
        codigo="PTO001",
        nombre="Proyecto Prueba",
        fechainicio=date(year=2020, month=6, day=5),
        fechafin=date(year=2020, month=9, day=5),
        presupuesto=10000,
        status="abierto",
    ),
    Proyecto(
        habilitado=True,
        entidad="dulce",
        codigo="PTO002",
        nombre="Proyecto Demo",
        fechainicio=date(year=2024, month=6, day=5),
        fechafin=date(year=2024, month=9, day=5),
        presupuesto=10000,
        status="abierto",
    ),
    Proyecto(
        habilitado=True,
        entidad="cacao",
        codigo="PTO003",
        nombre="Proyecto Demo",
        fechainicio=date(year=2024, month=6, day=5),
        fechafin=date(year=2024, month=9, day=5),
        presupuesto=10000,
        status="abierto",
    ),
)

TASAS_DE_CAMBIO = (
    TasaDeCambio(
        base="NIO",
        destino="USD",
        tasa=34.5984,
        fecha=date(year=2021, month=6, day=30),
    ),
    TasaDeCambio(
        base="NIO",
        destino="USD",
        tasa=34.5984,
        fecha=date(year=2021, month=6, day=29),
    ),
    TasaDeCambio(
        base="NIO",
        destino="USD",
        tasa=34.5964,
        fecha=date(year=2021, month=6, day=28),
    ),
)

PERIODOS = (
    PeriodoContable(
        entidad="cacao",
        nombre="2019",
        status="cerrado",
        habilitada=False,
        inicio=date(year=2019, month=1, day=1),
        fin=date(year=2019, month=12, day=31),
    ),
    PeriodoContable(
        entidad="cacao",
        nombre="2020",
        status="cerrado",
        habilitada=False,
        inicio=date(year=2020, month=1, day=1),
        fin=date(year=2020, month=12, day=31),
    ),
)
