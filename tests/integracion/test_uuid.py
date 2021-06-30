from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from .test_db import SQLITE
from .test_db import MARIADB
from .test_db import MSSQL
from .test_db import MYSQL
from .test_db import POSTGRESQL
from .test_db import verficar_conceccion_a_mariadb
from .test_db import verficar_conceccion_a_mssql
from .test_db import verficar_conceccion_a_mysql
from .test_db import verficar_conceccion_a_postgresql


UUID_APP = Flask(__name__)

CONF = {
    "SQLALCHEMY_DATABASE_URI": "sqlite:///uuid.db",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "ENV": "development",
    "SECRET_KEY": "dev",
    "TESTING": True,
}

with UUID_APP.app_context():
    from cacao_accounting.database.uuid import COLUMNA_UUID

UUID_APP.config.from_mapping(CONF)

DATABASE = SQLAlchemy()
DATABASE.init_app(UUID_APP)


class Tabla:
    id = COLUMNA_UUID
    name = DATABASE.Column(DATABASE.String(10), nullable=False)


class UUIDTTabla(DATABASE.Model, Tabla):
    pass


def test_crear_tabla_con_columna_uuid():
    with UUID_APP.app_context():
        # Eliminamos las tablas por si existe de una ejecucion anterior
        DATABASE.drop_all()
        DATABASE.create_all()
        registro1 = UUIDTTabla(name="Python")
        registro2 = UUIDTTabla(name="PHP")
        DATABASE.session.add(registro1)
        DATABASE.session.add(registro2)
        DATABASE.session.commit()


def test_texto_unico():
    from cacao_accounting.database.uuid import obtiene_texto_unico

    texto1 = obtiene_texto_unico()
    texto2 = obtiene_texto_unico()
    assert texto1 != texto2


SQLITE_APP = Flask(__name__)
SQLITE_APP.config["SQLALCHEMY_DATABASE_URI"] = SQLITE

SQLITE_DB = SQLAlchemy()
SQLITE_DB.init_app(SQLITE_APP)


class UUIDSQLite(SQLITE_DB.Model, Tabla):
    pass


def test_uuid_sqlite():
    with SQLITE_APP.app_context():
        # Eliminamos las tablas por si existe de una ejecucion anterior
        SQLITE_DB.drop_all()
        SQLITE_DB.create_all()
        registro1 = UUIDSQLite(name="Python")
        registro2 = UUIDSQLite(name="PHP")
        SQLITE_DB.session.add(registro1)
        SQLITE_DB.session.add(registro2)
        SQLITE_DB.session.commit()


MARIADB_APP = Flask(__name__)
MARIADB_APP.config["SQLALCHEMY_DATABASE_URI"] = MARIADB

MARIADB_DB = SQLAlchemy()
MARIADB_DB.init_app(MARIADB_APP)


class UUIDMARIADB(MARIADB_DB.Model, Tabla):
    pass


if verficar_conceccion_a_mariadb():

    def test_uuid_mariadb():
        with MARIADB_APP.app_context():
            # Eliminamos las tablas por si existe de una ejecucion anterior
            MARIADB_DB.drop_all()
            MARIADB_DB.create_all()
            registro1 = UUIDMARIADB(name="Python")
            registro2 = UUIDMARIADB(name="PHP")
            MARIADB_DB.session.add(registro1)
            MARIADB_DB.session.add(registro2)
            MARIADB_DB.session.commit()


MSSQL_APP = Flask(__name__)
MSSQL_APP.config["SQLALCHEMY_DATABASE_URI"] = MSSQL

MSSQL_DB = SQLAlchemy()
MSSQL_DB.init_app(MSSQL_APP)


class UUIDMSSQL(MSSQL_DB.Model, Tabla):
    pass


if verficar_conceccion_a_mssql():

    def test_uuid_mssql():
        with MSSQL_APP.app_context():
            # Eliminamos las tablas por si existe de una ejecucion anterior
            MSSQL_DB.drop_all()
            MSSQL_DB.create_all()
            registro1 = UUIDMSSQL(name="Python")
            registro2 = UUIDMSSQL(name="PHP")
            MSSQL_DB.session.add(registro1)
            MSSQL_DB.session.add(registro2)
            MSSQL_DB.session.commit()


MYSQL_APP = Flask(__name__)
MYSQL_APP.config["SQLALCHEMY_DATABASE_URI"] = MYSQL

MYSQL_DB = SQLAlchemy()
MYSQL_DB.init_app(MYSQL_APP)


class UUIDMYSQL(MYSQL_DB.Model, Tabla):
    pass


if verficar_conceccion_a_mysql():

    def test_uuid_mysql():
        with MYSQL_APP.app_context():
            # Eliminamos las tablas por si existe de una ejecucion anterior
            MYSQL_DB.drop_all()
            MYSQL_DB.create_all()
            registro1 = UUIDMYSQL(name="Python")
            registro2 = UUIDMYSQL(name="PHP")
            MYSQL_DB.session.add(registro1)
            MYSQL_DB.session.add(registro2)
            MYSQL_DB.session.commit()


POSTGRESQL_APP = Flask(__name__)
POSTGRESQL_APP.config["SQLALCHEMY_DATABASE_URI"] = POSTGRESQL

POSTGRESQL_DB = SQLAlchemy()
POSTGRESQL_DB.init_app(POSTGRESQL_APP)


class UUIDPOSTGRESQL(POSTGRESQL_DB.Model, Tabla):
    pass


if verficar_conceccion_a_postgresql():

    def test_uuid_postgresl():
        with POSTGRESQL_APP.app_context():
            # Eliminamos las tablas por si existe de una ejecucion anterior
            POSTGRESQL_DB.drop_all()
            POSTGRESQL.create_all()
            registro1 = UUIDPOSTGRESQL(name="Python")
            registro2 = UUIDPOSTGRESQL(name="PHP")
            POSTGRESQL_DB.session.add(registro1)
            POSTGRESQL_DB.session.add(registro2)
            POSTGRESQL_DB.session.commit()
