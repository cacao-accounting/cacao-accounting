from os import environ
from unittest import TestCase
from sqlalchemy import create_engine
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, dev_data

from .x_basicos import Basicos


# <-------------------------------------------------------------------------> #
# Conecciones para cada tipo de base de datos.
SQLITE = "sqlite://"
MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
MARIADB = "mariadb+pymysql://cacao:cacao@localhost:3307/cacao"
POSTGRESQL = "postgresql+pg8000://cacao:cacao@localhost:5432/cacao"
MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"

# Online testing
DB4FREE = "mysql+pymysql://cacao_test:cacao_test@db4free.net:3306/cacao_test"
ELEPHANTSQL = "postgresql+pg8000://fnifwoyu:ZHW8k1Y3z0Pvl1iOcDnimcvnFdx-SSrU@ruby.db.elephantsql.com/fnifwoyu"

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


def verficar_conceccion_a_mariadb():
    try:
        engine = create_engine(MARIADB)
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
TEST_MARIADB = verficar_conceccion_a_mariadb()
TEST_POSTGRESQL = verficar_conceccion_a_postgresql()
TEST_MSSQL = verficar_conceccion_a_mssql()

# <-------------------------------------------------------------------------> #
# Pruebas unitarias por tipo de base de datos:


class TestSQLite(TestCase, Basicos):
    def setUp(self):
        environ["CACAO_DB"] = SQLITE
        self.dbengine = TEST_SQLITE
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": environ.get("CACAO_DB"),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            db.create_all()
            base_data(carga_rapida=True)
            dev_data()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()
            environ.pop("CACAO_DB")

    def test_db(self):
        self.URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert self.URL.startswith("sqlite://")
        assert environ.get("CACAO_DB") == self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert environ.get("CACAO_DB") == SQLITE
        assert self.app.config["SQLALCHEMY_DATABASE_URI"] == SQLITE


class TestMySQL(TestCase, Basicos):
    def setUp(self):
        environ["CACAO_DB"] = MYSQL
        self.dbengine = TEST_MYSQL
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": environ.get("CACAO_DB"),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            if TEST_MYSQL:
                db.create_all()
                base_data(carga_rapida=True)
                dev_data()

    def tearDown(self):
        with self.app.app_context():
            if TEST_MYSQL:
                db.drop_all()
                environ.pop("CACAO_DB")

    def test_db(self):
        self.URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert self.URL.startswith("mysql+pymysql://")
        assert environ.get("CACAO_DB") == self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert environ.get("CACAO_DB") == MYSQL
        assert self.app.config["SQLALCHEMY_DATABASE_URI"] == MYSQL


class TestMariaDB(TestCase, Basicos):
    def setUp(self):
        environ["CACAO_DB"] = MARIADB
        self.dbengine = TEST_MARIADB
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": environ.get("CACAO_DB"),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            if TEST_MARIADB:
                db.create_all()
                base_data(carga_rapida=True)
                dev_data()

    def tearDown(self):
        with self.app.app_context():
            if TEST_MARIADB:
                db.drop_all()

    def test_db(self):
        self.URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert self.URL.startswith("mariadb+pymysql://")
        assert environ.get("CACAO_DB") == self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert environ.get("CACAO_DB") == MARIADB
        assert self.app.config["SQLALCHEMY_DATABASE_URI"] == MARIADB


class TestPostgresql(TestCase, Basicos):
    def setUp(self):
        environ["CACAO_DB"] = POSTGRESQL
        self.dbengine = TEST_POSTGRESQL
        self.app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": environ.get("CACAO_DB"),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "ENV": "development",
                "SECRET_KEY": "dev",
            }
        )
        with self.app.app_context():
            if TEST_POSTGRESQL:
                db.create_all()
                base_data(carga_rapida=True)
                dev_data()

    def tearDown(self):
        with self.app.app_context():
            if TEST_POSTGRESQL:
                db.drop_all()

    def test_db(self):
        self.URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert self.URL.startswith("postgresql+pg8000://")
        assert environ.get("CACAO_DB") == self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert environ.get("CACAO_DB") == POSTGRESQL
        assert self.app.config["SQLALCHEMY_DATABASE_URI"] == POSTGRESQL


class TestMSSQL(TestCase, Basicos):
    def setUp(self):
        self.dbengine = TEST_MSSQL
        if TEST_MSSQL:
            environ["CACAO_DB"] = MSSQL
            self.app = create_app(
                {
                    "SQLALCHEMY_DATABASE_URI": environ.get("CACAO_DB"),
                    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                    "ENV": "development",
                    "SECRET_KEY": "dev",
                }
            )
            with self.app.app_context():
                if TEST_MSSQL:
                    db.create_all()
                    base_data(carga_rapida=True)
                    dev_data()
        else:
            self.app = None

    def tearDown(self):
        if self.app:
            with self.app.app_context():
                db.drop_all()

    def test_db(self):
        if TestMSSQL and self.app is not None:
            self.URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert self.URL.startswith("mssql+pyodbc://")
            assert environ.get("CACAO_DB") == self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert environ.get("CACAO_DB") == MSSQL
            assert self.app.config["SQLALCHEMY_DATABASE_URI"] == MSSQL
