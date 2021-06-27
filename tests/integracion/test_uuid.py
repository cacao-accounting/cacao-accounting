import pytest

from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy


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

DATABASE = SQLAlchemy(UUID_APP)


class UUIDTTabla(DATABASE.Model):
    id = COLUMNA_UUID
    name = DATABASE.Column(DATABASE.String(5), nullable=False)


def test_crear_tabla_con_columna_uuid():
    with UUID_APP.app_context():
        # Eliminamos las tablas por si existe de una ejecucion anterior
        DATABASE.drop_all()
        DATABASE.create_all()
        registro1 = UUIDTTabla(name="Python")
        registro2 = UUIDTTabla(name="PHP")
        DATABASE.session.add(registro1)
        DATABASE.session.add(registro2)


def test_texto_unico():
    from cacao_accounting.database.uuid import obtiene_texto_unico

    texto1 = obtiene_texto_unico()
    texto2 = obtiene_texto_unico()
    assert texto1 != texto2


class UUID:
    def __init__(self) -> None:
        self.uuid_db = DATABASE
        self.uuid_table = UUIDTTabla

    def test_insertar_registro_con_uuid(self):
        if self.dbengine:
            with current_app.app_context():
                # Eliminamos las tablas por si existe de una ejecucion anterior
                self.uuid_db.drop_all()
                self.uuid_db.create_all()
                registro1 = self.uuid_table(name="Python")
                registro2 = self.uuid_table(name="PHP")
                registro3 = self.uuid_table(name="Ruby")
                registro4 = self.uuid_table(name="Java")
                registro5 = self.uuid_table(name="Rust")
                registro5 = self.uuid_table(name="Go")
                self.uuid_db.session.add(registro1)
                self.uuid_db.session.add(registro2)
                self.uuid_db.session.add(registro3)
                self.uuid_db.session.add(registro4)
                self.uuid_db.session.add(registro5)
                self.uuid_db.session.commit()
