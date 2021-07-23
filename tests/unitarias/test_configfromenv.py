import pytest


@pytest.fixture
def configurar_environ():
    from os import environ

    environ["CACAO_KEY"] = "3MpNPPdN+1235asdfKJDLDLS@"
    environ["CACAO_DB"] = "sqlite:///cacaoaccounting.db"


def test_config_from_env(configurar_environ):
    from cacao_accounting.config import probar_configuracion_por_variables_de_entorno, configuracion

    assert probar_configuracion_por_variables_de_entorno() is True
    assert configuracion is not None


@pytest.fixture
def configurar_environ1():
    from os import environ

    environ["CACAO_KEY"] = "hola"
    environ["CACAO_DB"] = "hola"


def test_config_from_env_false(configurar_environ1):
    from cacao_accounting.config import probar_configuracion_por_variables_de_entorno, configuracion

    assert probar_configuracion_por_variables_de_entorno() is False
    assert configuracion is not None
