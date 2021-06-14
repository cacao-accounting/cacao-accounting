from unittest import TestCase
from sqlalchemy import create_engine
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data

from .x_basicos import Basicos


# <-------------------------------------------------------------------------> #
# Conecciones para cada tipo de base de datos.
SQLITE = "sqlite://"
MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
POSTGRESQL = "postgresql+pg8000://cacao:cacao@localhost:5432/cacao"
MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"

# <-------------------------------------------------------------------------> #
# Validamos que bases de datos estan disponibles


def verficar_conceccion_a_mysql():
    try:
        engine = create_engine(MYSQL)
        with engine.connect() as con:
            rs = con.execute("SELECT VERSION()")
            for row in rs:
                pass
        return True
    except:
        return False


def verficar_conceccion_a_postgresql():
    try:
        engine = create_engine(POSTGRESQL)
        with engine.connect() as con:
            rs = con.execute("SELECT VERSION()")
            for row in rs:
                pass
        return True
    except:
        return False


def verficar_conceccion_a_mssql():
    try:
        engine = create_engine(MSSQL)
        with engine.connect() as con:
            rs = con.execute("SELECT @@VERSION")
            for row in rs:
                pass
        return True
    except:
        return False


TEST_SQLITE = True  # Siempre disponible
TEST_MYSQL = verficar_conceccion_a_mysql()
TEST_POSTGRESQL = verficar_conceccion_a_postgresql()
TEST_MSSQL = verficar_conceccion_a_mssql()

# <-------------------------------------------------------------------------> #
# Pruebas unitarias por tipo de base de datos:


class TestSQLite(TestCase, Basicos):
    def setUp(self):
        self.dbengine = TEST_SQLITE
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": SQLITE,
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            db.create_all()
            base_data(carga_rapida=True)
            demo_data()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def test_db(self):
        URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert URL.startswith("sqlite://")


class TestMySQL(TestCase, Basicos):
    def setUp(self):
        self.dbengine = TEST_MYSQL
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": MYSQL,
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            if TEST_MYSQL:
                db.create_all()
                base_data(carga_rapida=True)
                demo_data()

    def tearDown(self):
        with self.app.app_context():
            if TEST_MYSQL:
                db.drop_all()

    def test_db(self):
        URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert URL.startswith("mysql+pymysql://")


class TestPostgresql(TestCase, Basicos):
    def setUp(self):
        self.dbengine = TEST_POSTGRESQL
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": POSTGRESQL,
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            if TEST_POSTGRESQL:
                db.create_all()
                base_data(carga_rapida=True)
                demo_data()

    def tearDown(self):
        with self.app.app_context():
            if TEST_POSTGRESQL:
                db.drop_all()

    def test_db(self):
        URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert URL.startswith("postgresql+pg8000://")


class TestMSSQL(TestCase, Basicos):
    def setUp(self):
        self.dbengine = TEST_MSSQL
        if TEST_MSSQL:
            self.app = create_app(
                {
                    "SQLALCHEMY_DATABASE_URI": MSSQL,
                    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                    "ENV": "development",
                    "SECRET_KEY": "dev",
                }
            )
            with self.app.app_context():
                if TEST_MSSQL:
                    db.create_all()
                    base_data(carga_rapida=True)
                    demo_data()
        else:
            self.app = None

    def tearDown(self):
        if self.app:
            with self.app.app_context():

                db.drop_all()

    def test_db(self):
        if TestMSSQL and self.app is not None:
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mssql+pyodbc://")
