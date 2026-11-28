# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Funciones auxiliares relacionadas a la base de datos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date
from os import environ
from typing import Any, Optional, cast
from uuid import NAMESPACE_URL, uuid5

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Flask, g, has_request_context
from sqlalchemy import update
from sqlalchemy.exc import InternalError, InterfaceError, OperationalError, ProgrammingError, SQLAlchemyError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import database
from cacao_accounting.config import env_bool
from cacao_accounting.logs import log

from cacao_accounting.i18n import _

MAXIMO_RESULTADOS_EN_CONSULTA_PAGINADA = 10
DB_CONNECTION_FAILED = "No se pudo establecer conexion a la base de datos."
DB_RETRYING_CONNECTION = "Reintentando conectar a la base de datos."

# <---------------------------------------------------------------------------------------------> #
# Herramientas auxiliares para verificar la ejecución de la base de datos.

if environ.get("CACAO_TEST", None):  # pragma: no cover
    TIEMPO_ESPERA = 0
else:
    TIEMPO_ESPERA = 20


def verifica_coneccion_db(app):
    """Verifica si es posible conectarse a la base de datos.

    Un ``SELECT`` simple demuestra conectividad sin asumir que tablas de
    aplicación ya existan (#1898).
    """
    import time

    # Con ``CACAO_TEST`` la espera es cero, así que la condición del ``while``
    # nunca se cumpliría y ``DB_CONN`` quedaría sin definir. Se fuerza al menos
    # un intento para que la verificación sea real en pruebas.
    intentos_restantes = 1 if TIEMPO_ESPERA <= 0 else None

    with app.app_context():
        __inicio = time.time()
        DB_CONN = False
        while (time.time() - __inicio) < TIEMPO_ESPERA or intentos_restantes:
            log.info("Verificando conexión a la base de datos.")
            try:
                from sqlalchemy import text

                database.session.execute(text("SELECT 1"))
                DB_CONN = True
                log.info("Conexión a la base de datos exitosa.")
                break
            except (OperationalError, TypeError, InterfaceError, ProgrammingError, InternalError):
                DB_CONN = False
                database.session.rollback()
                log.warning(DB_CONNECTION_FAILED)
                log.info(DB_RETRYING_CONNECTION)

            if not environ.get("CACAO_TEST", None):
                time.sleep(2)
            elif intentos_restantes:
                intentos_restantes = 0

        if not DB_CONN:
            log.warning("No fue imposible establecer una conexión con la base de datos.")
        return DB_CONN


def entidades_creadas():
    """Verifica si al menos una entidad ha sido creado en el sistema."""
    from cacao_accounting.database import Entity

    try:
        CONSULTA = database.session.execute(database.select(Entity)).first()

        if CONSULTA:
            return True
        else:
            return False

    except (OperationalError, TypeError, InterfaceError, ProgrammingError, InternalError):
        database.session.rollback()
        return False


def _tabla_existe(nombre_tabla: str) -> bool:
    """Indica si una tabla existe en el esquema actual."""
    try:
        from sqlalchemy import inspect as sa_inspect

        return sa_inspect(database.engine).has_table(nombre_tabla)
    except (OperationalError, ProgrammingError, InterfaceError):
        database.session.rollback()
        return False


def _columnas_tabla(nombre_tabla: str) -> set[str]:
    """Devuelve los nombres de columna de una tabla existente."""
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(database.engine)
    if not inspector.has_table(nombre_tabla):
        return set()
    return {column["name"] for column in inspector.get_columns(nombre_tabla)}


def _revision_actual_alembic() -> tuple[str, ...]:
    """Devuelve las revisiones Alembic aplicadas en la base actual."""
    from cacao_accounting import alembic

    try:
        return tuple(str(getattr(rev, "revision", rev)) for rev in alembic.current())
    except Exception:
        database.session.rollback()
        return ()


def _cabecera_alembic() -> tuple[str, ...]:
    """Devuelve las revisiones head conocidas por Alembic."""
    from cacao_accounting import alembic

    heads = alembic.heads()
    # Flask-Alembic puede devolver scripts o ids según versión.
    result = []
    for item in heads:
        result.append(str(getattr(item, "revision", item)))
    return tuple(result)


def _clasificar_estado_esquema(
    *,
    tablas_core: set[str],
    tablas_existentes: set[str],
    esquema_completo: bool,
    tabla_alembic: bool,
    revisiones: tuple[str, ...],
    heads: tuple[str, ...],
    bootstrap_incompleto: bool,
) -> str:
    """Resuelve el estado del esquema con retornos tempranos (#1898)."""
    tablas_presentes = tablas_core & tablas_existentes
    if not tablas_presentes and not tabla_alembic:
        return "empty"
    if not tablas_core.issubset(tablas_existentes):
        return "partial"
    if not esquema_completo and not tabla_alembic:
        return "partial"
    if esquema_completo and not tabla_alembic:
        return "bootstrap_incomplete" if bootstrap_incompleto else "unversioned"
    if not revisiones or not esquema_completo:
        return "partial"
    if set(revisiones) != set(heads):
        return "outdated"
    return "current" if not bootstrap_incompleto else "bootstrap_incomplete"


def _esquema_tiene_columnas_requeridas(
    inspector: Any,
    tablas_modelo: set[str],
    tablas_existentes: set[str],
) -> bool:
    """Comprueba que cada tabla del modelo conserva sus columnas requeridas."""
    if not tablas_modelo or not tablas_modelo.issubset(tablas_existentes):
        return False
    metadata = cast(Any, database.Model).metadata
    for tabla in tablas_modelo:
        columnas_requeridas = set(metadata.tables[tabla].columns.keys())
        columnas_existentes = {column["name"] for column in inspector.get_columns(tabla)}
        if not columnas_requeridas.issubset(columnas_existentes):
            return False
    return True


def estado_esquema_base_datos() -> dict[str, object]:
    """Clasifica el estado del esquema para comandos de base de datos.

    El contrato de upgrades (#1898) distingue base vacía, inicializada,
    parcialmente inicializada e incompatible. La existencia de ``User`` no es
    prueba suficiente de bootstrap completo.
    """
    from cacao_accounting.database import CacaoConfig, User

    tablas_core = {"user", "cacao_config", "modules"}
    tablas_presentes = {tabla for tabla in tablas_core if _tabla_existe(tabla)}
    tabla_alembic = _tabla_existe("alembic_version")
    revisiones = _revision_actual_alembic() if tabla_alembic else ()
    heads = _cabecera_alembic()
    usuarios = False
    config_count = 0
    if "user" in tablas_presentes:
        try:
            usuarios = database.session.execute(database.select(User.id)).first() is not None
        except (OperationalError, ProgrammingError, InterfaceError):
            database.session.rollback()
    if "cacao_config" in tablas_presentes:
        try:
            config_count = int(
                database.session.execute(database.select(database.func.count()).select_from(CacaoConfig)).scalar() or 0
            )
        except (OperationalError, ProgrammingError, InterfaceError):
            database.session.rollback()

    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(database.engine)
    tablas_existentes = set(inspector.get_table_names())
    tablas_modelo = set(cast(Any, database.Model).metadata.tables.keys())
    esquema_completo = _esquema_tiene_columnas_requeridas(inspector, tablas_modelo, tablas_existentes)
    bootstrap_incompleto = bool(tablas_presentes == tablas_core and not datos_base_completos())
    bootstrap_iniciado = _bootstrap_iniciado(usuarios, config_count) if tablas_presentes else False
    estado = _clasificar_estado_esquema(
        tablas_core=tablas_core,
        tablas_existentes=tablas_existentes,
        esquema_completo=esquema_completo,
        tabla_alembic=tabla_alembic,
        revisiones=revisiones,
        heads=heads,
        bootstrap_incompleto=bootstrap_incompleto,
    )

    return {
        "status": estado,
        "tables": sorted(tablas_presentes),
        "alembic_table": tabla_alembic,
        "revisions": list(revisiones),
        "heads": list(heads),
        "users": usuarios,
        "config_count": config_count,
        "bootstrap_started": bootstrap_iniciado,
    }


def verificar_esquema_base_datos(*, permitir_migrar: bool = False) -> dict[str, object]:
    """Verifica compatibilidad del esquema sin mutar datos por defecto.

    ``serve`` usa este contrato en modo verificación: no migra ni repara.
    ``db migrate`` puede solicitar migración explícita con
    ``permitir_migrar=True``.
    """
    from cacao_accounting import alembic

    estado = estado_esquema_base_datos()
    status = str(estado["status"])

    if status == "empty":
        raise RuntimeError(_("La base de datos no está inicializada; ejecute primero 'cacaoctl db init'."))
    if status in {"partial", "bootstrap_incomplete"}:
        raise RuntimeError(
            _("La base de datos tiene un esquema parcial o inconsistente; restaure un respaldo o inicialice una base nueva.")
        )
    if status == "unversioned":
        if not permitir_migrar:
            raise RuntimeError(
                _(
                    "La base de datos no tiene historial Alembic; "
                    "ejecute 'cacaoctl db migrate' para registrar la revisión compatible."
                )
            )
        alembic.stamp("head")
        estado = estado_esquema_base_datos()
        status = str(estado["status"])
    if status == "outdated":
        if not permitir_migrar:
            raise RuntimeError(_("La base de datos requiere migraciones; ejecute 'cacaoctl db migrate' antes de servir."))
        alembic.upgrade(target="head")
        estado = estado_esquema_base_datos()
        status = str(estado["status"])
    if status not in {"current"}:
        raise RuntimeError(_("El estado del esquema de base de datos no es compatible: %(status)s") % {"status": status})
    return estado


def usuarios_creados():
    """Verifica si al menos un usuario ha sido creado en el sistema."""
    from cacao_accounting.database import User

    try:
        CONSULTA = database.session.execute(database.select(User)).first()

        if CONSULTA is not None:
            return True
        else:
            return False

    except (OperationalError, TypeError, InterfaceError, ProgrammingError, InternalError):
        database.session.rollback()
        return False


def datos_base_completos() -> bool:
    """Verifica que el seed base requerido esté completo (#1848).

    La existencia de ``User`` no demuestra que el bootstrap terminó: un fallo
    intermedio deja módulos, roles, administrador o monedas incompletos. Esta
    verificación es la señal explícita que usa la máquina de estados del
    esquema para no declarar inicializada una base parcial.
    """
    from cacao_accounting.auth.roles import ROLES_PREDETERMINADOS
    from cacao_accounting.database import CacaoConfig, Currency, Modules, Roles, User
    from cacao_accounting.modulos import MODULOS_STANDAR
    from cacao_accounting.setup.catalogs import SETUP_SEED_CURRENCY_CODES

    try:
        setup_completo = (
            database.session.execute(database.select(CacaoConfig.id).filter_by(key="SETUP_COMPLETE")).first() is not None
        )
        if setup_completo:
            # Bases existentes: el marcador de fin de bootstrap ya se escribió.
            return True
        modulos = set(database.session.execute(database.select(Modules.module)).scalars())
        roles = set(database.session.execute(database.select(Roles.name)).scalars())
        monedas = set(database.session.execute(database.select(Currency.code)).scalars())
        administrador = database.session.execute(database.select(User.id).filter_by(classification="admin")).first()
    except (OperationalError, ProgrammingError, InterfaceError, InternalError):
        database.session.rollback()
        return False
    return (
        {modulo["modulo"] for modulo in MODULOS_STANDAR} <= modulos
        and {rol["name"] for rol in ROLES_PREDETERMINADOS} <= roles
        and set(SETUP_SEED_CURRENCY_CODES) <= monedas
        and administrador is not None
    )


def _bootstrap_iniciado(usuarios: bool, config_count: int) -> bool:
    """Indica si la base ya tiene algún dato de seed (aunque esté incompleto)."""
    if usuarios or config_count:
        return True
    from cacao_accounting.database import Currency, Modules, Roles

    try:
        for modelo in (Modules, Roles, Currency):
            if database.session.execute(database.select(modelo.id).limit(1)).first() is not None:
                return True
    except (OperationalError, ProgrammingError, InterfaceError, InternalError):
        database.session.rollback()
        return False
    return False


def _asegurar_tabla_alembic() -> None:
    """Marca el esquema actual en Alembic cuando la base ya existe."""
    if _tabla_existe("alembic_version"):
        return
    from sqlalchemy import text

    heads = _cabecera_alembic()
    head = heads[-1] if heads else "head"
    # Usar SQL directo para evitar efectos secundarios de Flask-Alembic stamp
    # sobre conexiones SQLite en memoria/StaticPool durante bootstrap.
    database.session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
    database.session.execute(text("DELETE FROM alembic_version"))
    database.session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": head})
    database.session.commit()


def inicia_base_de_datos(app: Flask, user: str, passwd: str, with_examples: bool) -> bool:  # pragma: no cover
    """Inicia esquema de base datos.

    Contrato #1898/#2234: para bases nuevas crea esquema y lo marca en Alembic.
    Para bases existentes verifica compatibilidad y solo aplica migraciones
    Alembic; no completa bootstrap parcial usando existencia de `User`.
    """
    from cacao_accounting.datos import base_data, dev_data

    with app.app_context():
        estado = estado_esquema_base_datos()
        status = str(estado["status"])

        if status not in {"empty", "bootstrap_incomplete"}:
            if status == "partial":
                log.error("Base de datos con esquema parcial; no se puede completar automáticamente.")
                return False
            try:
                verificar_esquema_base_datos(permitir_migrar=True)
            except Exception:
                log.exception("No se pudo verificar/migrar el esquema existente.")
                return False
            return bool(status in {"current", "outdated", "unversioned"})

        if status == "bootstrap_incomplete":
            if estado.get("bootstrap_started"):
                # #1848/#1898: una base parcial no se completa mutando
                # silenciosamente el catálogo; la recuperación es explícita.
                log.error(
                    "Bootstrap base incompleto: faltan módulos, roles, administrador o monedas. "
                    "Restaure un respaldo o reinicialice con 'cacaoctl db init --force'."
                )
                return False
            # Esquema creado sin ningún dato de seed: inicialización segura.
            try:
                if with_examples:
                    base_data(user, passwd, carga_rapida=False)
                    dev_data()
                else:
                    base_data(user, passwd, carga_rapida=True)
                    from cacao_accounting.database import CacaoConfig as Config

                    existe_setup = database.session.execute(database.select(Config.id).filter_by(key="SETUP_COMPLETE")).first()
                    if not existe_setup:
                        database.session.add(Config(key="SETUP_COMPLETE", value="False"))
                        database.session.commit()
                _asegurar_tabla_alembic()
                return True
            except SQLAlchemyError:
                database.session.rollback()
                log.exception("No se pudo completar el bootstrap de la base de datos.")
                return False

        log.info("Intentando inicializar base de datos.")
        try:
            database.create_all()
            log.info("Esquema de base de datos creado correctamente.")
            if with_examples:
                log.trace("Creando datos de prueba.")
                base_data(user, passwd, carga_rapida=False)
                dev_data()
            else:
                base_data(user, passwd, carga_rapida=True)
            if not with_examples:
                from cacao_accounting.database import CacaoConfig as Config

                database.session.add(Config(key="SETUP_COMPLETE", value="False"))
                database.session.commit()
            _asegurar_tabla_alembic()
            return True
        except SQLAlchemyError:
            database.session.rollback()
            log.exception("No se pudo inicializar esquema de base de datos.")
            return False


def obtener_id_modulo_por_nombre(modulo: str | None) -> str | None:
    """Devuelve el UUID de un modulo por su nombre."""
    if modulo:
        from cacao_accounting.database import Modules, database

        MODULO = database.session.execute(database.select(Modules).filter_by(module=modulo)).scalar_one_or_none()
        return MODULO.id if MODULO is not None else None
    else:
        return None


def obtener_id_rol_por_monbre(rol: str) -> str:
    """Devuelve el UUID de un rol en base a su nombre."""
    from cacao_accounting.database import Roles

    ROL = Roles.query.filter_by(name=rol).first()
    return ROL.id


def db_version():  # pragma: no cover
    """Return database version as text."""
    from flask import current_app
    from sqlalchemy.sql import text

    from cacao_accounting.database import database

    with current_app.app_context():
        bind = database.session.get_bind()
        dialect = bind.dialect.name if bind is not None else ""
        if dialect in {"mysql", "mariadb"}:
            query = text("SELECT version();")
        elif dialect in {"postgresql", "postgres"}:
            query = text("SELECT VERSION();")
        else:
            query = text("select sqlite_version();")
        result = database.session.execute(query)
        for row in result:
            return str(row)
        return ""


# <---------------------------------------------------------------------------------------------> #
# Series e Identificadores — Framework robusto.
#
# Principio: los tokens se resuelven usando posting_date, NUNCA created_at.
# Esto garantiza que el identificador refleja la fecha contable del documento.
#
# Tokens soportados en prefix_template:
#   *YYYY*  → año completo del posting_date  (ej: 2025)
#   *YY*    → año corto del posting_date     (ej: 25)
#   *MMM*   → mes en texto 3 letras          (ej: JUN)
#   *MM*    → mes en dos dígitos             (ej: 06)
#   *DD*    → día en dos dígitos             (ej: 15)
#
# Ejemplo de template: "CHOCO-SI-*YYYY*-*MMM*-"
# Con posting_date=2025-06-15 → "CHOCO-SI-2025-JUN-00001"
# <---------------------------------------------------------------------------------------------> #


def resolve_naming_series_prefix(template: str, posting_date: date, company: Optional[str] = None) -> str:
    """Resuelve los tokens dinamicos de un template de serie.

    Los tokens se resuelven usando posting_date (fecha contable),
    nunca la fecha de creacion del registro.

    Args:
        template: Plantilla con tokens como 'COMP-SI-*YYYY*-*MMM*-'
        posting_date: Fecha contable del documento (no created_at)

    Returns:
        Prefijo resuelto listo para concatenar con el numero de secuencia.
    """
    MONTH_ABBR = {
        1: "ENE",
        2: "FEB",
        3: "MAR",
        4: "ABR",
        5: "MAY",
        6: "JUN",
        7: "JUL",
        8: "AGO",
        9: "SEP",
        10: "OCT",
        11: "NOV",
        12: "DIC",
    }

    result = template
    result = result.replace("*YYYY*", str(posting_date.year))
    result = result.replace("*YY*", str(posting_date.year)[-2:])
    result = result.replace("*MMM*", MONTH_ABBR[posting_date.month])
    result = result.replace("*MM*", f"{posting_date.month:02d}")
    result = result.replace("*DD*", f"{posting_date.day:02d}")
    result = result.replace("*COMP*", company or "")

    return result


def format_sequence_value(value: int, padding: int) -> str:
    """Formatea un valor de secuencia con el padding indicado.

    Args:
        value: Valor entero de la secuencia.
        padding: Cantidad de dígitos con cero a la izquierda.

    Returns:
        Cadena formateada. Ejemplo: value=5, padding=5 → '00005'
    """
    return str(value).zfill(padding)


def sequence_period_key(sequence_id: str, posting_date: date, reset_policy: str | None = None) -> str:
    """Devuelve la clave del periodo de numeracion que consume una secuencia.

    ``global`` agrupa la politica ``never``; ``YYYY`` la anual y ``YYYY-MM`` la
    mensual. La clave se deriva de la fecha contable, no de la fecha de alta.
    """
    policy = _effective_sequence_reset_policy(sequence_id, reset_policy)
    if policy == "monthly":
        return f"{posting_date.year:04d}-{posting_date.month:02d}"
    if policy == "yearly":
        return f"{posting_date.year:04d}"
    return "global"


def _period_counter_id(sequence_id: str, period_key: str) -> str:
    """Devuelve un identificador estable para el contador de una secuencia y periodo.

    MySQL ``INSERT ... ON DUPLICATE KEY UPDATE`` bloquea tanto la clave primaria
    como la restricción única. Si cada concurrente inserta un ``id`` distinto,
    los bloqueos se adquieren en órdenes incompatibles y InnoDB aborta con error
    1213. Derivar el ``id`` de la propia clave garantiza una sola fila y un
    único orden de bloqueo para todas las reservas del mismo periodo.
    """
    return uuid5(NAMESPACE_URL, f"cacao:sequence-period-counter:{sequence_id}:{period_key}").hex[:26]


def _period_counter_upsert(sequence_id: str, period_key: str, dialect: Optional[str] = None):
    """Devuelve el insert idempotente del contador de periodo para el motor activo.

    ``ON CONFLICT DO NOTHING`` (SQLite/PostgreSQL) y ``ON DUPLICATE KEY``
    (MySQL) crean la fila una sola vez incluso bajo concurrencia. Después el
    incremento se aplica con un ``UPDATE`` atómico, así que SQLite no depende
    de ``FOR UPDATE`` para serializar. La clave primaria del contador es
    determinista para evitar deadlocks de InnoDB con índices múltiples.
    """
    from cacao_accounting.database import SequencePeriodCounter

    values = {
        "id": _period_counter_id(sequence_id, period_key),
        "sequence_id": sequence_id,
        "period_key": period_key,
        "current_value": 0,
    }
    dialect = dialect or database.session.connection().dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        return (
            sqlite_insert(SequencePeriodCounter)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["sequence_id", "period_key"])
        )
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as postgresql_insert

        return (
            postgresql_insert(SequencePeriodCounter)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["sequence_id", "period_key"])
        )
    if dialect == "mysql":
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        statement = mysql_insert(SequencePeriodCounter).values(**values)
        return statement.on_duplicate_key_update(current_value=SequencePeriodCounter.current_value)
    return None


def get_next_period_sequence_value(sequence_id: str, period_key: str) -> int:
    """Reserva atomicamente el siguiente valor del periodo indicado.

    El contador del periodo se crea de forma idempotente y se incrementa con
    un ``UPDATE`` atómico. No depende de ``FOR UPDATE`` ni del orden global de
    creacion, por lo que SQLite y los motores cloud aplican la misma garantía:
    volver a un periodo anterior continua su propio consecutivo.
    """
    from cacao_accounting.database import Sequence, SequencePeriodCounter

    seq = database.session.execute(database.select(Sequence).filter_by(id=sequence_id)).scalar_one_or_none()
    if seq is None:
        raise ValueError(_("Secuencia con id '%(sequence)s' no encontrada.") % {"sequence": sequence_id})

    if period_key == "global":
        database.session.execute(
            update(Sequence)
            .where(Sequence.id == sequence_id)
            .values(current_value=Sequence.current_value + Sequence.increment)
        )
        return int(
            database.session.execute(database.select(Sequence.current_value).where(Sequence.id == sequence_id)).scalar_one()
        )

    upsert = _period_counter_upsert(sequence_id, period_key)
    if upsert is not None:
        database.session.execute(upsert)
    else:
        existing = database.session.execute(
            database.select(SequencePeriodCounter).filter_by(sequence_id=sequence_id, period_key=period_key).with_for_update()
        ).scalar_one_or_none()
        if existing is None:
            database.session.add(SequencePeriodCounter(sequence_id=sequence_id, period_key=period_key, current_value=0))
            database.session.flush()

    database.session.execute(
        update(SequencePeriodCounter)
        .where(SequencePeriodCounter.sequence_id == sequence_id, SequencePeriodCounter.period_key == period_key)
        .values(current_value=SequencePeriodCounter.current_value + seq.increment)
    )
    value = int(
        database.session.execute(
            database.select(SequencePeriodCounter.current_value).where(
                SequencePeriodCounter.sequence_id == sequence_id,
                SequencePeriodCounter.period_key == period_key,
            )
        ).scalar_one()
    )
    database.session.execute(update(Sequence).where(Sequence.id == sequence_id).values(current_value=value))
    return value


def generate_identifier(
    entity_type: str,
    entity_id: str,
    posting_date: date,
    company: Optional[str] = None,
    naming_series_id: Optional[str] = None,
    sequence_id: Optional[str] = None,
) -> str:
    """Genera y registra un identificador unico para un documento.

    El identificador combina:
    1. Prefijo resuelto del NamingSeries (tokens de posting_date)
    2. Numero de secuencia formateado con padding

    El identificador generado se guarda en GeneratedIdentifierLog para
    garantizar unicidad y auditabilidad.

    Args:
        entity_type: Tipo de entidad (ej: 'sales_invoice', 'payment_entry')
        entity_id: ID del registro que recibira el identificador
        posting_date: Fecha contable (no created_at) para resolver tokens
        company: Codigo de la compania (para prefijos por compania)
        naming_series_id: ID del NamingSeries a usar (opcional)
        sequence_id: ID de la Sequence a usar (opcional, requerida si hay serie)

    Returns:
        Identificador completo generado. Ejemplo: 'CHOCO-SI-2025-JUN-00001'

    Raises:
        ValueError: Si los IDs proporcionados no existen.
    """
    from cacao_accounting.database import GeneratedIdentifierLog, NamingSeries, Sequence

    prefix = ""
    sequence_period: Optional[str] = None

    if naming_series_id:
        series = database.session.execute(database.select(NamingSeries).filter_by(id=naming_series_id)).scalar_one_or_none()

        if series is None:
            raise ValueError(_("NamingSeries con id '%(series)s' no encontrada.") % {"series": naming_series_id})

        prefix = resolve_naming_series_prefix(series.prefix_template, posting_date, company)

    if sequence_id:
        seq = database.session.execute(database.select(Sequence).filter_by(id=sequence_id)).scalar_one_or_none()

        if seq is None:
            raise ValueError(_("Sequence con id '%(sequence)s' no encontrada.") % {"sequence": sequence_id})

        sequence_period = sequence_period_key(sequence_id, posting_date, seq.reset_policy)
        next_val = get_next_period_sequence_value(sequence_id, sequence_period)
        suffix = format_sequence_value(next_val, seq.padding)
        full_identifier = f"{prefix}{suffix}"
    else:
        full_identifier = prefix or entity_id

    if company is None:
        from cacao_accounting.default_scope import lock_default_scope

        lock_default_scope("generated_identifier", "global")
        exists = database.session.execute(
            database.select(GeneratedIdentifierLog.id)
            .where(
                GeneratedIdentifierLog.company.is_(None),
                GeneratedIdentifierLog.full_identifier == full_identifier,
            )
            .limit(1)
        ).first()
        if exists is not None:
            raise ValueError(_("El identificador interno ya existe."))

    log_entry = GeneratedIdentifierLog(
        entity_type=entity_type,
        entity_id=entity_id,
        full_identifier=full_identifier,
        sequence_id=sequence_id,
        sequence_period=sequence_period,
        company=company,
        posting_date=posting_date,
    )
    database.session.add(log_entry)
    database.session.flush()

    return full_identifier


def get_active_naming_series(entity_type: str, company: Optional[str] = None) -> list:
    """Devuelve las series de numeracion activas para un tipo de entidad.

    Busca primero series especificas de la compania, luego series globales.

    Args:
        entity_type: Tipo de entidad (ej: 'sales_invoice')
        company: Codigo de la compania (opcional)

    Returns:
        Lista de objetos NamingSeries activas ordenadas por nombre.
    """
    from cacao_accounting.database import NamingSeries

    if company:
        from sqlalchemy import or_

        query = database.select(NamingSeries).filter(
            NamingSeries.entity_type == entity_type,
            NamingSeries.is_active.is_(True),
            or_(NamingSeries.company == company, NamingSeries.company.is_(None)),
        )
    else:
        query = database.select(NamingSeries).filter_by(entity_type=entity_type, is_active=True)

    results = database.session.execute(query).scalars().all()
    return list(results)


def _effective_sequence_reset_policy(sequence_id: str, configured_policy: str | None) -> str:
    """Deriva la política efectiva considerando el prefijo de la serie asociada."""
    from cacao_accounting.database import NamingSeries, SeriesSequenceMap

    configured = str(configured_policy or "never")
    if configured == "monthly":
        return configured

    prefix_templates = (
        database.session.execute(
            database.select(NamingSeries.prefix_template)
            .join(SeriesSequenceMap, SeriesSequenceMap.naming_series_id == NamingSeries.id)
            .filter(SeriesSequenceMap.sequence_id == sequence_id)
        )
        .scalars()
        .all()
    )

    if any("*MM*" in template or "*MMM*" in template for template in prefix_templates if template):
        return "monthly"
    if configured == "yearly":
        return configured
    if any("*YYYY*" in template or "*YY*" in template for template in prefix_templates if template):
        return "yearly"
    return configured


def resolver_credenciales_iniciales() -> tuple[str, str]:
    """Resuelve las credenciales de administración iniciales de forma segura.

    Verifica que CACAO_USER y CACAO_PSWD estén configuradas de forma explícita.
    Si faltan, y el entorno actual no está configurado como desarrollo ('dev' o
    'development'), lanza un error para detener la ejecución inmediatamente.

    Returns:
        Tupla con (usuario, contraseña) resueltos.

    Raises:
        ValueError: Si faltan las credenciales y no es entorno de desarrollo.
    """
    environments = {value.strip().lower() for value in (environ.get("FLASK_ENV"), environ.get("ENV")) if value}
    is_dev = not env_bool("CACAO_TEST") and bool(environments) and environments.issubset({"dev", "development"})
    is_database_test = env_bool("CI") and env_bool("CACAO_TEST") and env_bool("CHECK_DATABASE") and not environments

    usuario = environ.get("CACAO_USER") or environ.get("ADMIN_USER")
    contrasena = environ.get("CACAO_PSWD") or environ.get("CACAO_PASSWORD") or environ.get("ADMIN_PASSWORD")

    if not usuario or not contrasena:
        if not is_dev:
            raise ValueError(_("CACAO_USER and CACAO_PSWD must be set in environment"))
        usuario = usuario or "cacao"
        contrasena = contrasena or "cacao"

    if not (is_dev or is_database_test) and usuario.casefold() == "cacao" and contrasena == "cacao":
        raise ValueError(_("Las credenciales predeterminadas CACAO no se permiten fuera de desarrollo."))

    return usuario, contrasena


def batch_number(batch_id: str | None) -> str:
    """Resuelve el número público del lote, con caché por request."""
    if not batch_id:
        return ""
    from cacao_accounting.database import Batch

    if not has_request_context():
        batch = database.session.get(Batch, batch_id)
        return batch.batch_no if batch else ""
    cache = getattr(g, "_batch_number_cache", None)
    if cache is None:
        cache = {}
        g._batch_number_cache = cache
    if batch_id not in cache:
        batch = database.session.get(Batch, batch_id)
        cache[batch_id] = batch.batch_no if batch else ""
    return cache[batch_id]


def _lock_hierarchy_companies(company_codes: set[str]) -> None:
    """Serializa los cambios de jerarquía por compañía en orden determinista.

    Las filas de ``Entity`` actúan como el ancla común de la jerarquía: dos
    transacciones que muevan ramas distintas de la misma compañía no pueden
    validar y escribir simultáneamente, evitando ciclos (#2188). PostgreSQL y
    MySQL conservan el lock hasta el commit; SQLite lo ignora y mantiene su
    modo Desktop de un solo usuario.
    """
    from cacao_accounting.database import Entity

    for company_code in sorted(code for code in company_codes if code):
        database.session.execute(
            database.select(Entity.code)
            .where(Entity.code == company_code)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()


def _fetch_hierarchy_node_locked(node_class, node_id):
    """Lee un nodo con bloqueo para no reutilizar un snapshot previo.

    En MySQL ``REPEATABLE READ`` una lectura normal posterior al lock puede
    seguir viendo el snapshot anterior al commit rival. Las lecturas de la
    jerarquía usan ``FOR UPDATE`` para observar el estado confirmado.
    """
    return database.session.execute(
        database.select(node_class).where(node_class.id == node_id).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _hierarchy_company_codes(entity: str, current_entity: str | None) -> set[str]:
    """Resuelve sin consultar la BD las compañías que deben bloquearse."""
    return {code for code in (entity, current_entity) if code}


def check_hierarchy_cycle(node_class, node_id, proposed_parent_id, *, entity: str, current_entity: str | None = None) -> None:
    """Valida que el padre exista, pertenezca a la compañía y no cree ciclos.

    Las filas de ``Entity`` se bloquean antes que cualquier nodo, en orden
    determinista. Así ninguna transacción retiene un nodo mientras espera un
    ancla ajena; en traslados cruzados se toman las dos anclas en el mismo
    orden. La validación y la escritura quedan serializadas por compañía
    (#2188).
    """
    _lock_hierarchy_companies(_hierarchy_company_codes(entity, current_entity))

    if node_id:
        for descendant_id in get_descendant_ids(node_class, node_id, for_update=True):
            descendant = _fetch_hierarchy_node_locked(node_class, descendant_id)
            if descendant is not None and descendant.entity != entity:
                raise ValueError(_("Los registros de una jerarquía deben pertenecer a la misma compañía."))
    if not proposed_parent_id:
        return
    if proposed_parent_id == node_id:
        raise ValueError(_("Un registro no puede ser padre de sí mismo."))
    parent_node = _fetch_hierarchy_node_locked(node_class, proposed_parent_id)
    if parent_node is None:
        raise ValueError(_("El registro padre seleccionado no existe."))
    if parent_node.entity != entity:
        raise ValueError(_("Los registros de una jerarquía deben pertenecer a la misma compañía."))

    curr_id = proposed_parent_id
    visited = {node_id} if node_id else set()
    while curr_id:
        if curr_id in visited:
            raise ValueError(_("No se permiten ciclos en la jerarquía (RN-003)."))
        visited.add(curr_id)
        parent_node = _fetch_hierarchy_node_locked(node_class, curr_id)
        if parent_node:
            curr_id = parent_node.parent_id
        else:
            break


def update_hierarchy_attributes(node) -> None:
    """Calcula y actualiza recursivamente nivel y path (RN-004).

    Los hijos se releen con ``FOR UPDATE`` después de cada flush para no
    reutilizar una colección ``children`` cacheada antes del commit rival
    (#2188). Los motores que ignoran el lock mantienen la lectura actual.
    """
    if not node.parent_id:
        node.level = 0
        node.path = node.name
    else:
        parent = node.parent
        if parent:
            node.level = parent.level + 1
            node.path = f"{parent.path} / {node.name}"
        else:
            node.level = 0
            node.path = node.name
    database.session.flush()
    children = database.session.execute(
        database.select(type(node))
        .where(type(node).parent_id == node.id)
        .order_by(type(node).id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars()
    for child in children:
        update_hierarchy_attributes(child)


def get_descendant_ids(node_class, node_id, *, for_update: bool = False) -> list[str]:
    """Devuelve todos los IDs descendientes de un nodo (excluyendo el nodo mismo).

    Con ``for_update`` la enumeración usa una lectura bloqueante para no
    reutilizar un snapshot previo al commit rival en motores con aislamiento
    repetible (#2188). El orden por id mantiene determinista la adquisición
    posterior de locks.
    """
    descendants: list[str] = []
    pending = [node_id]
    while pending:
        current_id = pending.pop()
        query = database.select(node_class.id).filter_by(parent_id=current_id).order_by(node_class.id)
        if for_update:
            query = query.with_for_update()
        children = database.session.execute(query).scalars()
        for child_id in children:
            if child_id not in descendants:
                descendants.append(child_id)
                pending.append(child_id)
    return descendants
