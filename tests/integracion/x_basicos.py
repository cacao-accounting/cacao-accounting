class Basicos:
    

        def test_verifica_db(self):
            if self.dbengine:
                from cacao_accounting.database import verifica_coneccion_db
                assert verifica_coneccion_db(self.app) is True
