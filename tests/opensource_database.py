import pytest
from unittest import TestCase
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data
from database import desplegar_base_de_datos, Entidad, CentroCosto, Unidad, Proyecto, Moneda


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
            print(row)
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
            print(row)
    postgresql_disponible = True
    print("Postgresql disponible")
except:
    postgresql_disponible = False
    print("Postgresql no disponible")

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


class TestSQLite(BaseSQLite, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda):
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

    class TestMySQL(BaseMySQL, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda):
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

    class TestPostgresl(BasePostgresl, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("postgresql")

        def test_demo(self):
            demo_data()
