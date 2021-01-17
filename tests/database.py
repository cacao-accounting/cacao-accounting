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


class Entidad:
    def test_crear_entidad(self):
        from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad

        e = RegistroEntidad()
        e.crear_entidad(datos=ENTIDAD1)


# <-------------------------------------------------------------------------> #
class BaseSQLite:
    app = create_app(CONFIG)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLITE


class TestSQLite(BaseSQLite, TestCase):
    def test_db(self):
        URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
        assert URL.startswith("sqlite")

    def test_demo(self):
        db.drop_all()
        db.create_all()
        base_data(carga_rapida=False)
        demo_data()
        db.drop_all()


class EjecutarSQLite(BaseSQLite, TestCase, Entidad):
    def setUp(self):
        db.drop_all()
        db.create_all()
        base_data()

    def tearDown(self):
        pass


# <-------------------------------------------------------------------------> #
if mysql_disponible:

    class BaseMySQL:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = MYSQL
        app.app_context().push()

    class TestMySQL(BaseMySQL, TestCase):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mysql")

        def test_demo(self):
            db.drop_all()
            db.create_all()
            base_data(carga_rapida=False)
            demo_data()
            db.drop_all()

    class EjecutarMySQL(BaseMySQL, TestCase, Entidad):
        def setUp(self):
            db.drop_all()
            db.create_all()
            base_data()

        def tearDown(self):
            pass


# <-------------------------------------------------------------------------> #
if postgresql_disponible:

    class BasePostgresl:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = POSTGRESQL
        app.app_context().push()

    class TestPostgresl(BasePostgresl, TestCase):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("postgresql")

        def test_demo(self):
            db.drop_all()
            db.create_all()
            base_data(carga_rapida=False)
            demo_data()
            db.drop_all()

        class EjecutarPostgresl(BasePostgresl, TestCase, Entidad):
            def setUp(self):
                db.drop_all()
                db.create_all()
                base_data()

            def tearDown(self):
                pass
