import pytest
from cacao_accounting import database, datos


class Basicos:
    def __init__(self) -> None:
        pass

    @pytest.mark.slow
    def test_verifica_db(self):
        if self.dbengine:
            from cacao_accounting.database.helpers import verifica_coneccion_db

            assert verifica_coneccion_db(self.app) is True

    @pytest.mark.slow
    def test_verifica_migracion_db_V(self):
        if self.dbengine:
            from cacao_accounting.database import Metadata, database
            from cacao_accounting.database.helpers import requiere_migracion_db, db_metadata

            with self.app.app_context():
                db_metadata(self.app)
                meta = Metadata.query.first()
                meta.dbversion = "hola"
                meta.cacaoversion = "hola"
                database.session.add(meta)
                database.session.commit()
                meta = Metadata.query.first()
                assert meta.dbversion == "hola"
                assert meta.cacaoversion == "hola"
                assert requiere_migracion_db(self.app) is True

    @pytest.mark.slow
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

    @pytest.mark.slow
    def test_inicia_base_de_datos_V(self):
        from cacao_accounting.database import database
        from cacao_accounting.database.helpers import inicia_base_de_datos

        if self.dbengine:
            with self.app.app_context():
                database.drop_all()
                assert inicia_base_de_datos(self.app) is True

    @pytest.mark.slow
    def test_db_actual(self):
        if self.dbengine:
            from cacao_accounting.app import bd_actual

            with self.app.app_context():
                assert bd_actual() is not None

    @pytest.mark.slow
    def test_obtener_lista_entidades_por_id_razonsocial(self):
        from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

        if self.dbengine:
            with self.app.app_context():
                assert obtener_lista_entidades_por_id_razonsocial() is not None

    @pytest.mark.slow
    def test_user_from_env(self):
        from os import environ

        environ["CACAO_USER"] = "wmoreno"
        environ["CACAO_PWD"] = "wmoreno1A+"

        from cacao_accounting.database import database
        from cacao_accounting.database.helpers import inicia_base_de_datos

        if self.dbengine:
            with self.app.app_context():
                database.drop_all()
                assert inicia_base_de_datos(self.app) is True
