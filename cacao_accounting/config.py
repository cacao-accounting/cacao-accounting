# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo para la configuración centralizada de la configuración de la aplicacion."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ, name
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database_url import database_url_from_parts
from cacao_accounting.logs import log
from cacao_accounting.runtime_mode import detect_desktop_mode

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# < --------------------------------------------------------------------------------------------- >
# Directorios de la aplicacion
DIRECTORIO_APP = Path(__file__).parent
DIRECTORIO_PRINCIPAL = DIRECTORIO_APP.parent
DIRECTORIO_PLANTILLAS = str(DIRECTORIO_APP / "templates")
DIRECTORIO_ARCHIVOS = str(DIRECTORIO_APP / "static")
POSTGRESQL_URI_PREFIX = "postgresql://"

# < --------------------------------------------------------------------------------------------- >
# URI de conexión a bases de datos por defecto
if name == "nt":
    SQLITE = f"sqlite:///{DIRECTORIO_PRINCIPAL}\\cacaoaccounting.db"
else:
    SQLITE = f"sqlite:///{DIRECTORIO_PRINCIPAL}/cacaoaccounting.db"

# < --------------------------------------------------------------------------------------------- >
# Permite al usuario establecer cuantos hilos utilizar para ejecutar el servidor WSGI por defecto,
# util para instalaciones en un equipo dedicado, en otros entornos como contenedores se utiliza un
# valor razonable por defecto.
THREADS = environ.get("CACAO_THREADS") or environ.get("THREADS") or 4

# < --------------------------------------------------------------------------------------------- >
# Permite al usuario establecer en que puerto servir la aplicacion con el servidor WSGI por defecto
PORT = environ.get("CACAO_PORT") or environ.get("PORT") or 8080

# < --------------------------------------------------------------------------------------------- >
# En entornos de web y de contenedores es un patron recomendado utlizar variables del entorno para
# configurar la aplicacion.

_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})


def env_bool(name: str, default: bool = False) -> bool:
    """Interpreta una variable de entorno booleana sin usar truthiness de strings."""
    value = environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


# Force tests to run by default on an in-memory database, except those designed for a specific database.
is_testing = env_bool("CACAO_TEST") or env_bool("CI") or (environ.get("PYTEST_VERSION") is not None)


def _database_url_from_environment() -> str | None:
    """Compone la URL desde CACAO_DB_* codificando la contraseña (#1851)."""
    password = environ.get("CACAO_DB_PASSWORD")
    if not password:
        return None
    return database_url_from_parts(
        user=environ.get("CACAO_DB_USER", "cacao"),
        password=password,
        host=environ.get("CACAO_DB_HOST", "db"),
        port=environ.get("CACAO_DB_PORT", "5432"),
        name=environ.get("CACAO_DB_NAME", "cacaodb"),
    )


if is_testing:
    env_db = (
        environ.get("CACAO_DATABASE_URL")
        or environ.get("CACAO_DB")
        or environ.get("DATABASE_URL")
        or _database_url_from_environment()
    )
    if env_db and (
        "mysql" in env_db or "postgresql" in env_db or "mariadb" in env_db or "mssql" in env_db or "sqlite:///" in env_db
    ):
        DATABASE_URL = env_db
    else:
        DATABASE_URL = "sqlite:///:memory:"
else:
    DATABASE_URL = (
        environ.get("CACAO_DATABASE_URL")
        or environ.get("CACAO_DB")
        or environ.get("DATABASE_URL")
        or _database_url_from_environment()
        or SQLITE
    )

SECRET_KEY = environ.get("CACAO_SECRET_KEY") or environ.get("CACAO_KEY") or environ.get("SECRET_KEY")


def normaliza_direccion_base_datos(uri: str) -> tuple[str, dict[str, dict[str, str]]]:
    """Normaliza la URI de base de datos para compatibilidad entre proveedores.

    Las URL ``postgres://`` y ``postgresql://`` (sin driver explícito) se
    resuelven al driver ``psycopg`` (psycopg 3), que es el único soportado.
    """
    direccion = str(uri)
    opciones_motor: dict[str, dict[str, str]] = {}

    if direccion.startswith("postgres://"):
        direccion = direccion.replace("postgres://", "postgresql+psycopg://", 1)
    elif direccion.startswith(POSTGRESQL_URI_PREFIX):
        direccion = direccion.replace(POSTGRESQL_URI_PREFIX, "postgresql+psycopg://", 1)

    if direccion.startswith("postgresql+psycopg://"):
        uri_parseada = urlsplit(direccion)
        query = dict(parse_qsl(uri_parseada.query, keep_blank_values=True))
        sslmode = query.pop("sslmode", "").lower()
        query.pop("channel_binding", None)

        # Neon/serverless Postgres can close idle connections; pre-ping avoids
        # AdminShutdown/OperationalError surfacing to users on the next request.
        opciones_motor["pool_pre_ping"] = True
        opciones_motor["pool_recycle"] = int(environ.get("CACAO_DB_POOL_RECYCLE", "280"))
        if sslmode in {"require", "verify-ca", "verify-full"}:
            opciones_motor["connect_args"] = {"sslmode": sslmode}

        direccion = urlunsplit(
            (uri_parseada.scheme, uri_parseada.netloc, uri_parseada.path, urlencode(query), uri_parseada.fragment)
        )

    return direccion, opciones_motor


def valida_direccion_base_datos(uri: str) -> bool:
    """Verifica que la URI de la database este en el formato correcto."""
    direccion = str(uri)
    match direccion:
        case _ if direccion.startswith("mysql+pymysql"):
            return True
        case _ if direccion.startswith("mariadb+mariadbconnector"):
            log.warning("El soporte a MariaDB es expimental.")
            return True
        case _ if direccion.startswith(POSTGRESQL_URI_PREFIX):
            return True
        case _ if direccion.startswith("postgresql+psycopg://"):
            return True
        case _ if direccion.startswith("sqlite"):
            return True
        case _:
            log.warning("Favor revise la configuración de acceso a la base de datos.")
            return False


configuracion: dict[str, bool | str | int | dict[str, dict[str, str]]] = {}

DATABASE_URL_NORMALIZADA, DATABASE_ENGINE_OPTIONS = normaliza_direccion_base_datos(DATABASE_URL)

if valida_direccion_base_datos(DATABASE_URL_NORMALIZADA):
    configuracion["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL_NORMALIZADA
    if DATABASE_ENGINE_OPTIONS:
        configuracion["SQLALCHEMY_ENGINE_OPTIONS"] = DATABASE_ENGINE_OPTIONS
configuracion["SECRET_KEY"] = SECRET_KEY or ""
configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Printing and validation settings
configuracion["EXTERNAL_DOCUMENT_VALIDATION_ENABLED"] = env_bool("EXTERNAL_DOCUMENT_VALIDATION_ENABLED", True)
configuracion["EXTERNAL_DOCUMENT_VALIDATION_BASE_URL"] = environ.get(
    "EXTERNAL_DOCUMENT_VALIDATION_BASE_URL", "https://cacaocontent.com"
)

# Límite por archivo para adjuntos. Se puede ajustar desde el backend; el
# límite global de la petición se eleva para cubrirlo en ``create_app``.
configuracion["ATTACHMENT_MAX_FILE_SIZE"] = int(environ.get("CACAO_ATTACHMENT_MAX_FILE_SIZE", str(25 * 1024 * 1024)))

if env_bool("CACAO_TEST"):
    configuracion["DEBUG"] = True
    configuracion["TEMPLATES_AUTO_RELOAD"] = True

if environ.get("CACHE_REDIS_URL"):
    configuracion["CACHE_TYPE"] = "RedisCache"
    configuracion["CACHE_REDIS_URL"] = environ.get("CACHE_REDIS_URL") or ""
else:
    configuracion["CACHE_TYPE"] = "SimpleCache"

if environ.get("RATELIMIT_STORAGE_URI"):
    configuracion["RATELIMIT_STORAGE_URI"] = environ.get("RATELIMIT_STORAGE_URI") or ""


MODO_ESCRITORIO = detect_desktop_mode()

TESTING_MODE = env_bool("CACAO_TEST") or env_bool("CI") or environ.get("PYTEST_VERSION") is not None
