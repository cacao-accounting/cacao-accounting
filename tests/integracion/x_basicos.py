class Basicos:
    def __init__(self) -> None:
        pass

    def test_verifica_db(self):
        if self.dbengine:
            from cacao_accounting.database.helpers import verifica_coneccion_db

            assert verifica_coneccion_db(self.app) is True

    def test_verifica_migracion_db_V(self):
        if self.dbengine:
            from cacao_accounting.database import Metadata, db
            from cacao_accounting.database.helpers import requiere_migracion_db, db_metadata

            with self.app.app_context():
                db_metadata(self.app)
                meta = Metadata.query.first()
                meta.dbversion = "hola"
                meta.cacaoversion = "hola"
                db.session.add(meta)
                db.session.commit()
                meta = Metadata.query.first()
                assert meta.dbversion == "hola"
                assert meta.cacaoversion == "hola"
                assert requiere_migracion_db(self.app) is True

    def test_verifica_migracion_db_F(self):
        if self.dbengine:
            from cacao_accounting.metadata import VERSION
            from cacao_accounting.database import DBVERSION
            from cacao_accounting.database import Metadata
            from cacao_accounting.database.helpers import requiere_migracion_db, db_metadata

            with self.app.app_context():
                db_metadata(self.app)
                meta = Metadata.query.first()
                assert meta.dbversion == DBVERSION
                assert meta.cacaoversion == VERSION
                assert requiere_migracion_db(self.app) is False

    def test_inicia_base_de_datos_V(self):
        from cacao_accounting.database import db
        from cacao_accounting.database.helpers import inicia_base_de_datos

        if self.dbengine:
            with self.app.app_context():
                db.drop_all()
                assert inicia_base_de_datos(self.app) is True

    def test_inicia_base_de_datos_F(self):
        from flask import Flask
        from cacao_accounting.database.helpers import inicia_base_de_datos

        self.fapp = Flask(__name__)
        self.fapp.config["SQLALCHEMY_DATABASE_URI"] = "hola"

        if self.dbengine:
            with self.fapp.app_context():
                assert inicia_base_de_datos(self.fapp) is False
                from cacao_accounting.app import bd_actual

                assert bd_actual() is None

    def test_db_actual(self):
        if self.dbengine:
            from cacao_accounting.app import bd_actual

            with self.app.app_context():
                assert bd_actual() is not None
