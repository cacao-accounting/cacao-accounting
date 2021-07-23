import pytest

@pytest.fixture
def configurar_environ():
    from  os import environ
    environ["CACAO_KEY"] = "3MpNPPdN+1235asdfKJDLDLS@"
    environ["CACAO_DB"] = "sqlite:///cacaoaccounting.db"


def test_config_from_env(configurar_environ):
    from cacao_accounting.config import probar_configuracion_por_variables_de_entorno
    assert probar_configuracion_por_variables_de_entorno() is True
