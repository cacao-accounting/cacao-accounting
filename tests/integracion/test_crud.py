import pytest
from datetime import date
from unittest import TestCase
from sqlalchemy import create_engine
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data


def test_verifica_coneccion_db():
    from flask import Flask
    from cacao_accounting.database import verifica_coneccion_db

    app = Flask(__name__)
    assert verifica_coneccion_db(app) == True


def desplegar_base_de_datos():
    db.drop_all()
    db.create_all()
    base_data(carga_rapida=True)


ENTIDAD1 = {
    "id": "cafe1",
    "razon_social": "Cafe y Mas Sociedad Anonima",
    "nombre_comercial": "Cafe y Mas",
    "id_fiscal": "J0320000000078",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@cafeland.com",
    "web": "cafeland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": True,
    "predeterminada": True,
}

ENTIDAD2 = {
    "id": "soda",
    "razon_social": "Soda Land Sociedad Anonima",
    "nombre_comercial": "Soda Land",
    "id_fiscal": "J0310000000778",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@sodaland.com",
    "web": "sodaland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": True,
    "predeterminada": False,
}


ENTIDAD3 = {
    "id": "soda",
    "razon_social": "Soda Land Sociedad Anonima",
    "nombre_comercial": "Soda Land",
    "id_fiscal": "J0310000000778",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@sodaland.com",
    "web": "sodaland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": True,
    "predeterminada": False,
}


class Entidad:
    def test_crear_entidad(self):
        pass


CENTRO_DE_COSTO1 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "entidad": "cacao",
    "grupo": False,
    "codigo": "C11111",
    "nombre": "Centro Costos Prueba",
    "status": "activa",
}

CENTRO_DE_COSTO2 = {
    "activa": True,
    "predeterminado": False,
    "habilitada": True,
    "entidad": "cacao",
    "grupo": False,
    "codigo": "D11111",
    "nombre": "Centro Costos Prueba",
    "status": "activa",
}

CENTRO_DE_COSTO3 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "entidad": "cacao",
    "grupo": False,
    "codigo": "E11111",
    "nombre": "Centro Costos Prueba",
    "status": "activa",
}


class CentroCosto:
    def test_crear_centrocosto(self):
        from cacao_accounting.contabilidad.registros.ccosto import RegistroCentroCosto

        demo_data()
        c = RegistroCentroCosto()
        c.crear_registro_principal(datos=CENTRO_DE_COSTO1)
        c.crear_registro_principal(datos=CENTRO_DE_COSTO2)
        c.crear_registro_principal(datos=CENTRO_DE_COSTO3)


UNIDAD1 = {
    "id": "ocotal",
    "nombre": "Sucursal Ocotal",
    "entidad": "cacao",
    "correo_electronico": "sucursal1@chocoland.com",
    "web": "chocoland.com",
    "telefono1": "+505 8667 2108",
    "telefono2": "+505 8771 0980",
    "fax": "+505 7272 8181",
}

UNIDAD2 = {
    "id": "esteli",
    "nombre": "Sucursal Esteli",
    "correo_electronico": "sucursal2@chocoland.com",
    "web": "chocoland.com",
    "telefono1": "+505 8667 2108",
    "telefono2": "+505 8771 0980",
    "fax": "+505 7272 8181",
}


class Unidad:
    def test_crear_unidad(self):
        from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

        demo_data()
        r = RegistroUnidad()
        r.crear_registro_principal(datos=UNIDAD1)
        r.crear_registro_principal(datos=UNIDAD2)


PROYECTO = {
    "habilitado": True,
    "entidad": "cacao",
    "codigo": "PTO002",
    "nombre": "Proyecto Pruebas",
    "fechainicio": date(year=2020, month=6, day=5),
    "fechafin": date(year=2020, month=9, day=5),
    "presupuesto": 10000,
    "status": "abierto",
}


class Proyecto:
    def test_crear_proyecto(self):
        from cacao_accounting.contabilidad.registros.proyecto import RegistroProyecto

        demo_data()
        p = RegistroProyecto()
        p.crear_registro_principal(datos=PROYECTO)


MONEDA = {"id": "LALA", "nombre": "Cordobas Oro", "codigo": 55889, "decimales": 2}


class Moneda:
    def test_crear_moneda(self):
        from cacao_accounting.contabilidad.registros.moneda import RegistroMoneda

        r = RegistroMoneda()
        r.crear_registro_principal(MONEDA)


class Varios:
    def test_obtener_ctas_base(self):
        from cacao_accounting.contabilidad import obtener_catalogo_base

        obtener_catalogo_base()

    def test_obtener_ctas(self):
        from cacao_accounting.contabilidad import obtener_catalogo

        obtener_catalogo()

    def test_obtener_entidades(self):
        from cacao_accounting.contabilidad import obtener_entidades

        obtener_entidades()

    def test_obtener_lista_entidades_por_id_razonsocial(self):
        from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

        obtener_lista_entidades_por_id_razonsocial()


@pytest.fixture(autouse=True)
def cargar_datos():
    db.drop_all()
    db.session.commit()
    db.create_all()
    base_data()
    yield
    db.drop_all()


CONFIG = {}
CONFIG["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CONFIG["ENV"] = "development"
CONFIG["SECRET_KEY"] = "dev"
CONFIG["EXPLAIN_TEMPLATE_LOADING"] = True
CONFIG["DEGUG"] = True

# <-------------------------------------------------------------------------> #
# Conecciones para cada tipo de base de datos.
SQLITE = "sqlite://"
MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
POSTGRESQL = "postgresql+pg8000://cacao:cacao@localhost:5432/cacao"
MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Validamos que bases de datos estan disponibles


engine = create_engine(SQLITE)
with engine.connect() as con:
    rs = con.execute("SELECT sqlite_version()")
    for row in rs:
        print("SQLite version:")
        print(row)

try:

    engine = create_engine(MYSQL)
    with engine.connect() as con:
        rs = con.execute("SELECT VERSION()")
        for row in rs:
            print("MySQL disponible version:")
            print(row)
        mysql_disponible = True

except:
    mysql_disponible = False
    print("MySQL no disponible")


try:
    engine = create_engine(POSTGRESQL)
    with engine.connect() as con:
        rs = con.execute("SELECT VERSION()")
        for row in rs:
            print("Postgresql disponible version:")
            print(row)
    postgresql_disponible = True
except:
    postgresql_disponible = False
    print("Postgresql no disponible")

try:

    engine = create_engine(MSSQL)
    with engine.connect() as con:
        rs = con.execute("SELECT @@VERSION")
        for row in rs:
            print("MS SQL Server disponible version:")
            print(row)
    mssql_disponible = True
except:
    print("MS SQL Server no disponible")
    mssql_disponible = False


# <-------------------------------------------------------------------------> #
# Pruebas unitarias basicas relacionadas a la base de datos.


def test_crea_db():
    from cacao_accounting.config import configuracion
    from cacao_accounting.database import inicia_base_de_datos

    APP = create_app(configuracion)
    inicia_base_de_datos(APP)
    APP.config["ENV"] = "production"
    assert inicia_base_de_datos(APP) is False
    APP.config["SQLALCHEMY_DATABASE_URI"] = "hola"
    assert inicia_base_de_datos(APP) is False


def test_requiere_migracion_db():
    from cacao_accounting.config import configuracion
    from cacao_accounting.database import requiere_migracion_db

    APP = create_app(configuracion)
    APP.app_context().push()
    db.create_all()
    requiere_migracion_db(APP)


def test_obtener_listado_entidades():
    from flask import current_app
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    with current_app.test_request_context():
        with current_app.app_context():
            LISTA_ENTIDADES = obtener_lista_entidades_por_id_razonsocial()
            assert type(LISTA_ENTIDADES) == type([])



# <-------------------------------------------------------------------------> #
# Clases base para los test, cado uno de estas clases debe ejecutarse correctamente
# con cada motor de base de datos soportado:
#   - SQLite
#   - Postgresl
#   - MySQL


# <-------------------------------------------------------------------------> #
class BaseSQLite:
    app = create_app(CONFIG)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLITE
    app.app_context().push()


class TestSQLite(BaseSQLite, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda, Varios):
    def test_db(self):
        URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert URL.startswith("sqlite")

    def test_demo(self):
        demo_data()


# <-------------------------------------------------------------------------> #
if mysql_disponible:

    class BaseMySQL:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = MYSQL
        app.app_context().push()

    class TestMySQL(BaseMySQL, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda, Varios):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mysql")

        def test_demo(self):
            demo_data()


# <-------------------------------------------------------------------------> #
if postgresql_disponible:

    class BasePostgresl:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = POSTGRESQL
        app.app_context().push()

    class TestPostgresl(BasePostgresl, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda, Varios):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("postgresql")

        def test_demo(self):
            demo_data()


# <-------------------------------------------------------------------------> #
if mssql_disponible:

    class BaseSQLServer:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = MSSQL
        app.app_context().push()

    class TestSQLServer(BaseSQLServer, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda, Varios):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mssql")

        def test_demo(self):
            demo_data()


# Ejecutar al final ya que modifica variables de entorno
@pytest.fixture
def variables_de_entorno():
    from os import environ
    from flask import current_app

    environ["CACAO_USER"] = "testing-user"
    environ["CACAO_PWD"] = "testing-pwd"
    current_app.app_context().push()


def test_user_from_environ(variables_de_entorno):
    from os import environ
    from flask import current_app
    from cacao_accounting.datos.base import crea_usuario_admin
    from cacao_accounting.database import Usuario

    assert environ["CACAO_USER"] == "testing-user"
    assert environ["CACAO_PWD"] == "testing-pwd"
    current_app.app_context().push()
    db.create_all()
    crea_usuario_admin()
    consulta = db.session.query(Usuario).filter(Usuario.id == "testing-user").count()
    assert consulta, 1
