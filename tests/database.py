import pytest
from unittest import TestCase
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data

# <-------------------------------------------------------------------------> #
# Conecciones para cada tipo de base de datos.
SQLITE = "sqlite://"
MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
POSTGRESQL = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Validamos que bases de datos estan disponibles
try:
    from sqlalchemy import create_engine

    engine = create_engine(MYSQL)
    with engine.connect() as con:
        rs = con.execute("SELECT VERSION()")
        for row in rs:
            pass
        mysql_disponible = True
        print("MySQL disponible")
except:
    mysql_disponible = False
    print("MySQL no disponible")


try:

    import psycopg2
    from sqlalchemy import create_engine

    conn = psycopg2.connect("dbname='cacao' user='cacao' host='localhost' password='cacao'")
    cur = conn.cursor()
    cur.execute("SELECT version();")
    records = cur.fetchall()

    engine = create_engine(POSTGRESQL)
    with engine.connect() as con:
        rs = con.execute("SELECT VERSION()")
        for row in rs:
            pass
    postgresql_disponible = True
    print("Postgresql disponible")
except:
    postgresql_disponible = False
    print("Postgresql no disponible")
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Clases base para los test, cado uno de estas clases debe ejecutarse correctamente
# con cada motor de base de datos soportado:
#   - SQLite
#   - Postgresl
#   - MySQL

CONFIG = {}
CONFIG["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CONFIG["ENV"] = "development"
CONFIG["SECRET_KEY"] = "dev"
CONFIG["EXPLAIN_TEMPLATE_LOADING"] = True
CONFIG["DEGUG"] = True


def desplegar_base_de_datos():
    db.drop_all()
    db.create_all()
    base_data(carga_rapida=True)


ENTIDAD1 = {
    "id": "cafe",
    "razon_social": "Cafe y Mas Sociedad Anonima",
    "nombre_comercial": "Cafe y Mas",
    "id_fiscal": "J0310000000078",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@cafeland.com",
    "web": "cafeland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
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
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
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
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": False,
}


class Entidad:
    def test_crear_entidad(self):
        from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
        from cacao_accounting.database import Entidad

        e = RegistroEntidad()
        e.crear_entidad(datos=ENTIDAD1)
        entidades1 = Entidad.query.count()
        assert entidades1 == 1
        e.crear_entidad(datos=ENTIDAD2)
        entidades2 = Entidad.query.count()
        assert entidades2 == 2


CENTRO_DE_COSTO1 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "entidad": "cacao",
    "codigo": "11.01",
    "nombre": "Centro de Costos de Prueba",
    "grupo": False,
    "padre": None,
}

CENTRO_DE_COSTO2 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "entidad": "cacao",
    "codigo": "11.02",
    "nombre": "Centro de Costos de Prueba 2",
    "grupo": True,
    "padre": None,
}


class CentroCosto:
    def test_crear_centrocosto(self):
        from cacao_accounting.datos import demo_data
        from cacao_accounting.contabilidad.registros.ccosto import RegistroCentroCosto

        demo_data()
        c = RegistroCentroCosto()
        c.crear(datos=CENTRO_DE_COSTO1)
        c.crear(datos=CENTRO_DE_COSTO2)


UNIDAD1 = {
    "id": "ocotal",
    "nombre": "Sucursal Ocotal",
    "entidad": "cacao",
    "corre_electronico": "sucursal1@chocoland.com",
    "web": "chocoland.com",
    "telefono1": "+505 8667 2108",
    "telefono2": "+505 8771 0980",
    "fax": "+505 7272 8181",
    "pais": "Nicaragua",
    "departamento": "Nueva Segovia",
    "ciudad": "Ocotal",
    "direccion1": "Parque Central",
}


class Unidad:
    def test_crear_unidad(self):
        from cacao_accounting.datos import demo_data
        from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

        demo_data()
        r = RegistroUnidad()
        r.crear(UNIDAD1)


PROYECTO = {
    "activo": True,
    "habilitado": True,
    "entidad": "cacao",
    "codigo": "11.01",
    "nombre": "Proyecto de Prueba",
    "grupo": False,
    "padre": None,
    "finalizado": False,
    "presupuesto": 100000.00,
    "ejecutado": 50000,
}


class Proyecto:
    def test_crear_proyecto(self):
        from cacao_accounting.contabilidad.registros.proyecto import RegistroProyecto
        from cacao_accounting.datos import demo_data

        demo_data()
        p = RegistroProyecto()
        p.crear(datos=PROYECTO)


# <-------------------------------------------------------------------------> #
class BaseSQLite:
    app = create_app(CONFIG)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLITE
    app.app_context().push()


class TestSQLite(BaseSQLite, TestCase, Entidad, CentroCosto, Unidad, Proyecto):
    def setUp(self):
        db.drop_all()
        db.create_all()
        base_data()

    def tearDown(self):
        pass

    def test_db(self):
        URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert URL.startswith("sqlite")

    def test_demo(self):
        db.drop_all()
        db.create_all()
        base_data(carga_rapida=False)
        demo_data()
        db.drop_all()


# <-------------------------------------------------------------------------> #
if mysql_disponible:

    class BaseMySQL:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = MYSQL
        app.app_context().push()

    class TestMySQL(BaseMySQL, TestCase, Entidad, CentroCosto, Unidad, Proyecto):
        def setUp(self):
            db.drop_all()
            db.create_all()
            base_data()

        def tearDown(self):
            pass

        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mysql")

        def test_demo(self):
            db.drop_all()
            db.create_all()
            base_data(carga_rapida=False)
            demo_data()
            db.drop_all()


# <-------------------------------------------------------------------------> #
if postgresql_disponible:

    class BasePostgresl:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = POSTGRESQL
        app.app_context().push()

    class TestPostgresl(BasePostgresl, TestCase, Entidad, CentroCosto, Unidad, Proyecto):
        def setUp(self):
            db.drop_all()
            db.create_all()
            base_data()

        def tearDown(self):
            pass

        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("postgresql")

        def test_demo(self):
            db.drop_all()
            db.create_all()
            base_data(carga_rapida=False)
            demo_data()
            db.drop_all()
