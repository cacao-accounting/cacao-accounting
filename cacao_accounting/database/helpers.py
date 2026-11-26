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
from sqlalchemy import Index, delete, func, inspect as sa_inspect, select, update
from sqlalchemy.engine import Connection, Engine
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
    esquema_completo = bool(tablas_modelo) and tablas_modelo.issubset(tablas_existentes)
    bootstrap_incompleto = bool(tablas_presentes == tablas_core and not usuarios and config_count == 0)
    revisiones_set = set(str(r) for r in revisiones)
    heads_set = set(str(h) for h in heads)
    if not tablas_presentes and not tabla_alembic:
        estado = "empty"
    elif tablas_presentes and not tablas_core.issubset(tablas_existentes):
        estado = "partial"
    elif tablas_presentes == tablas_core and not esquema_completo and not tabla_alembic:
        estado = "partial"
    elif esquema_completo and not tabla_alembic:
        estado = "bootstrap_incomplete" if bootstrap_incompleto else "unversioned"
    elif tabla_alembic and not revisiones:
        estado = "partial"
    elif tabla_alembic and not esquema_completo:
        estado = "partial"
    elif tabla_alembic and revisiones_set != heads_set:
        estado = "outdated"
    elif tabla_alembic:
        estado = "current" if not bootstrap_incompleto else "bootstrap_incomplete"
    else:
        estado = "partial"

    return {
        "status": estado,
        "tables": sorted(tablas_presentes),
        "alembic_table": tabla_alembic,
        "revisions": list(revisiones),
        "heads": list(heads),
        "users": usuarios,
        "config_count": config_count,
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
            log.info("Esquema detectado sin bootstrap completo; completando inicialización.")
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
            _validate_and_fix_stock_bin_reserved_qty()
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


def _validate_and_fix_stock_bin_reserved_qty() -> None:
    """Validate and correct StockBin records with negative reserved_qty.

    CheckConstraint 'ck_stock_bin_reserved_non_negative' requires reserved_qty >= 0.
    This function ensures no data violates this constraint before the schema is fully applied.
    Skips execution on empty tables to avoid unnecessary queries during fresh initialization.
    """
    try:
        from cacao_accounting.database import StockBin

        # Skip entirely if the table is empty (fresh database).
        row_count = database.session.execute(database.select(database.func.count()).select_from(StockBin)).scalar()
        if not row_count:
            return

        # Check for any negative reserved_qty values
        negative_bins = database.session.execute(database.select(StockBin).where(StockBin.reserved_qty < 0)).scalars().all()

        if negative_bins:
            log.warning("Found {} StockBin records with negative reserved_qty. Correcting to 0.", len(negative_bins))
            for bin_record in negative_bins:
                bin_record.reserved_qty = 0
            database.session.commit()
            log.info("StockBin reserved_qty validation and correction completed successfully.")
    except (OperationalError, ProgrammingError, InterfaceError):
        # Table doesn't exist yet or other DB errors - safe to ignore during initialization
        pass
    except Exception as exc:
        log.warning("Could not validate StockBin.reserved_qty during initialization: {}", exc)


def _ensure_stock_valuation_layer_batch_column() -> None:
    """Suple idempotentemente la columna ``batch_id`` de ``stock_valuation_layer``.

    El lote es una dimension de primer nivel del almacen: al valorar una salida
    que selecciona un lote especifico solo deben consumirse las capas de entrada
    creadas para ese lote. ``create_all`` solo crea la tabla para esquemas
    nuevos; para bases existentes esta rutina agrega la columna sin migracion
    formal y de forma idempotente.

    La restriccion de llave foranea sobre ``batch.id`` solo se materializa en
    esquemas nuevos (via ``create_all``); en bases existentes SQLite no permite
    agregar una FK con ``ALTER TABLE`` y se suple la columna junto con su indice
    para mantener la paridad operativa con la reconstruccion de la cola.
    """
    try:
        from sqlalchemy import inspect as sa_inspect

        from cacao_accounting.database import StockValuationLayer

        if not sa_inspect(database.engine).has_table(StockValuationLayer.__tablename__):
            return
        current = {column["name"] for column in sa_inspect(database.engine).get_columns(StockValuationLayer.__tablename__)}
        if "batch_id" in current:
            return
        database.session.execute(database.text("ALTER TABLE stock_valuation_layer ADD COLUMN batch_id VARCHAR(26)"))
        database.session.execute(
            database.text("CREATE INDEX IF NOT EXISTS ix_stock_valuation_layer_batch_id ON stock_valuation_layer (batch_id)")
        )
        database.session.commit()
        log.info("Columna batch_id e indice agregados a stock_valuation_layer.")
    except (OperationalError, ProgrammingError, InterfaceError):
        database.session.rollback()
    except Exception as exc:
        log.warning("Could not ensure StockValuationLayer.batch_id during initialization: {}", exc)


def _ensure_user_email_identity_column() -> None:
    """Add and backfill the indexed, portable identity key for user emails.

    Backfilling keeps legacy case variants discoverable without choosing a
    database-specific Unicode ``lower()`` implementation. The index is
    intentionally non-unique so existing ambiguous identities remain visible
    to password recovery, which fails closed when more than one row matches.
    """
    from sqlalchemy import inspect as sa_inspect

    from cacao_accounting.database import User

    inspector = sa_inspect(database.engine)
    if not inspector.has_table(User.__tablename__):
        return

    columns = {column["name"] for column in inspector.get_columns(User.__tablename__)}
    if User.email_identity.name not in columns:
        _add_user_email_identity_column(User)
    _create_user_email_identity_index(User)
    _backfill_user_email_identity(User)


def _add_user_email_identity_column(User) -> None:
    """Add the identity column, tolerating another process creating it first."""
    from time import sleep

    from sqlalchemy import inspect as sa_inspect

    preparer = database.engine.dialect.identifier_preparer
    table_name = preparer.quote(User.__tablename__)
    identity_column = preparer.quote(User.email_identity.name)
    dialect = database.engine.dialect.name
    add_column_if_missing = " IF NOT EXISTS" if dialect == "postgresql" else ""
    alter_statement = database.text(
        f"ALTER TABLE {table_name} ADD COLUMN{add_column_if_missing} {identity_column} VARCHAR(150)"
    )
    for attempt in range(5):
        try:
            database.session.execute(alter_statement)
            database.session.commit()
            return
        except (OperationalError, ProgrammingError):
            database.session.rollback()
            columns = {column["name"] for column in sa_inspect(database.engine).get_columns(User.__tablename__)}
            if User.email_identity.name in columns:
                return
            if attempt == 4:
                raise
            sleep(0.05 * (attempt + 1))


def _create_user_email_identity_index(User) -> None:
    """Create the email identity index safely when application workers start together."""
    from time import sleep

    from sqlalchemy import inspect as sa_inspect

    email_index = next(index for index in User.__table__.indexes if index.name == "ix_user_email_identity")
    for attempt in range(5):
        try:
            email_index.create(bind=database.engine, checkfirst=True)
            database.session.commit()
            return
        except SQLAlchemyError:
            database.session.rollback()
            index_names = {index["name"] for index in sa_inspect(database.engine).get_indexes(User.__tablename__)}
            if email_index.name in index_names:
                return
            if attempt == 4:
                raise
            sleep(0.05 * (attempt + 1))


def _backfill_user_email_identity(User) -> None:
    """Fill canonical identity keys in batches without overwriting concurrent edits.

    A blank key marks a legacy address containing only whitespace. It cannot
    match normalized form input and lets the backfill finish without rewriting
    the original legacy value.
    """
    from sqlalchemy import bindparam, select, update

    from cacao_accounting.email_identity import normalize_user_email
    from cacao_accounting.internal_control_service import user_email_identity_backfill

    user_table = User.__table__
    update_statement = (
        update(user_table)
        .where(
            user_table.c.id == bindparam("email_identity_user_id"),
            user_table.c.e_mail == bindparam("email_identity_source"),
            user_table.c.email_identity.is_(None),
        )
        .values(email_identity=bindparam("email_identity_value"))
    )
    while True:
        criteria = [
            user_table.c.email_identity.is_(None),
            user_table.c.e_mail.is_not(None),
        ]
        rows = database.session.execute(
            select(user_table.c.id, user_table.c.e_mail).where(*criteria).order_by(user_table.c.id).limit(500)
        ).all()
        if not rows:
            break
        updates = [
            {
                "email_identity_user_id": user_id,
                "email_identity_source": email,
                "email_identity_value": normalize_user_email(email) or "",
            }
            for user_id, email in rows
        ]
        user_ids = tuple(str(values["email_identity_user_id"]) for values in updates)
        with user_email_identity_backfill(*user_ids):
            database.session.execute(update_statement, updates)
        database.session.commit()


def _ensure_purchase_line_version_columns() -> None:
    """Agrega columnas append-only a líneas de compras en esquemas existentes."""
    try:
        from sqlalchemy import inspect as sa_inspect

        from cacao_accounting.database import PurchaseEconomicEvent, PurchaseInvoiceItem, PurchaseReceiptItem

        dialect = database.engine.dialect.name
        boolean_default = "FALSE" if dialect == "postgresql" else "0"
        definitions = (
            (PurchaseReceiptItem.__tablename__, "is_superseded", f"BOOLEAN NOT NULL DEFAULT {boolean_default}"),
            (PurchaseInvoiceItem.__tablename__, "is_superseded", f"BOOLEAN NOT NULL DEFAULT {boolean_default}"),
            (PurchaseEconomicEvent.__tablename__, "idempotency_key", "VARCHAR(255)"),
        )
        inspector = sa_inspect(database.engine)
        for table_name, column_name, definition in definitions:
            if not inspector.has_table(table_name):
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if column_name not in columns:
                database.session.execute(database.text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
        if inspector.has_table(PurchaseEconomicEvent.__tablename__):
            database.session.execute(
                database.text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_purchase_economic_event_idempotency "
                    "ON purchase_economic_event (idempotency_key)"
                )
            )
        database.session.commit()
    except (OperationalError, ProgrammingError, InterfaceError):
        database.session.rollback()
    except Exception as exc:
        database.session.rollback()
        log.warning("Could not ensure purchase line version columns during initialization: {}", exc)


def _ensure_file_sha256_column() -> None:
    """Suple idempotentemente ``file.sha256`` en esquemas existentes.

    La integridad de los adjuntos se verifica contra el hash persistido en
    ``File``. ``create_all`` crea la columna en esquemas nuevos y esta rutina
    la agrega, junto con su índice, en bases existentes sin migración formal.
    Las filas históricas quedan con ``NULL`` y se aceptan como tales hasta un
    backfill controlado.
    """
    try:
        from sqlalchemy import inspect as sa_inspect

        from cacao_accounting.database import File

        inspector = sa_inspect(database.engine)
        if not inspector.has_table(File.__tablename__):
            return
        columns = {column["name"] for column in inspector.get_columns(File.__tablename__)}
        if "sha256" not in columns:
            database.session.execute(database.text("ALTER TABLE file ADD COLUMN sha256 VARCHAR(64)"))
            log.info("Columna sha256 agregada a file.")
        database.session.execute(database.text("CREATE INDEX IF NOT EXISTS ix_file_sha256 ON file (sha256)"))
        database.session.commit()
    except (OperationalError, ProgrammingError, InterfaceError):
        database.session.rollback()
    except Exception as exc:
        database.session.rollback()
        log.warning("Could not ensure file.sha256 during initialization: {}", exc)


def _ensure_bank_transaction_import_reference_column() -> None:
    """Suple idempotentemente ``bank_transaction.import_reference`` (#1262).

    Identifica la procedencia de importación de movimientos sin referencia
    bancaria. ``create_all`` la crea en esquemas nuevos; esta rutina la agrega
    en bases existentes. Las filas históricas quedan con ``NULL`` y conservan
    su identidad previa.
    """
    from sqlalchemy import inspect as sa_inspect

    from cacao_accounting.database import BankTransaction

    try:
        inspector = sa_inspect(database.engine)
        if not inspector.has_table(BankTransaction.__tablename__):
            return
        columns = {column["name"] for column in inspector.get_columns(BankTransaction.__tablename__)}
        if "import_reference" not in columns:
            database.session.execute(database.text("ALTER TABLE bank_transaction ADD COLUMN import_reference VARCHAR(120)"))
            log.info("Columna import_reference agregada a bank_transaction.")
        database.session.execute(
            database.text(
                "CREATE INDEX IF NOT EXISTS ix_bank_transaction_import_reference ON bank_transaction (import_reference)"
            )
        )
        database.session.commit()
    except (OperationalError, ProgrammingError, InterfaceError):
        database.session.rollback()
    except Exception as exc:
        database.session.rollback()
        log.warning("Could not ensure bank_transaction.import_reference during initialization: {}", exc)


def _ensure_monthly_close_run_unique_constraint() -> None:
    """Install the company/period uniqueness guard without rewriting old rows.

    New schemas get the constraint from SQLAlchemy metadata. Existing schemas
    receive an equivalent unique index after duplicate keys have been checked.
    Ambiguous historical runs are preserved and block this schema update so a
    person can resolve them without an automated business choice.
    """
    engine = database.engine
    from cacao_accounting.database import PeriodCloseRun

    if not sa_inspect(engine).has_table(PeriodCloseRun.__tablename__):
        return

    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                _create_monthly_close_unique_guard(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return

    try:
        with engine.begin() as connection:
            _create_monthly_close_unique_guard(connection)
    except SQLAlchemyError:
        if _monthly_close_unique_guard_exists(engine):
            return
        raise


def _monthly_close_unique_guard_exists(bind: Engine | Connection) -> bool:
    """Validate the canonical unique object and its protected columns."""
    from cacao_accounting.database import PeriodCloseRun

    table_name = PeriodCloseRun.__tablename__
    index_name = "uq_period_close_run_company_period"
    expected_columns = ["company", "period_id"]
    inspector = sa_inspect(bind)
    if not inspector.has_table(table_name):
        return False

    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("name") == index_name:
            if constraint.get("column_names") == expected_columns:
                return True
            raise RuntimeError(f"El constraint {index_name} no protege company y period_id.")

    for index in inspector.get_indexes(table_name):
        if index.get("name") == index_name:
            if index.get("unique") and index.get("column_names") == expected_columns:
                return True
            raise RuntimeError(f"El índice {index_name} no protege company y period_id de forma única.")
    return False


def _create_monthly_close_unique_guard(connection: Connection) -> None:
    """Create the guard on an open connection after checking historical rows."""
    from cacao_accounting.database import PeriodCloseRun

    index_name = "uq_period_close_run_company_period"
    if _monthly_close_unique_guard_exists(connection):
        return

    duplicate = connection.execute(
        select(PeriodCloseRun.company, PeriodCloseRun.period_id, func.count())
        .group_by(PeriodCloseRun.company, PeriodCloseRun.period_id)
        .having(func.count() > 1)
        .limit(1)
    ).first()
    if duplicate is not None:
        message = _(
            "No se puede aplicar la unicidad de cierres mensuales: hay varias corridas "
            "para compañía %(company)s y período %(period)s. Los registros existentes se conservaron."
        ) % {"company": duplicate.company, "period": duplicate.period_id}
        raise RuntimeError(message)

    Index(index_name, PeriodCloseRun.company, PeriodCloseRun.period_id, unique=True).create(
        bind=connection,
        checkfirst=False,
    )


def _ensure_bank_transaction_identity_unique() -> None:
    """Instala la unicidad de ``bank_transaction.identity_key`` en bases previas.

    Las bases nuevas reciben el constraint desde el modelo. Las existentes
    reciben un índice único equivalente; si ya contienen identidades repetidas,
    la actualización falla de forma explícita y conserva las filas para revisión
    humana, porque dos movimientos con la misma identidad son evidencia
    ambigua y no se consolidan automáticamente.
    """
    from cacao_accounting.database import BankTransaction

    _ensure_unique_index(
        table=BankTransaction.__table__,
        index_name="uq_bank_transaction_identity",
        column_names=("identity_key",),
        deduplicate=_reject_duplicate_bank_transaction_identities,
    )


def _reject_duplicate_bank_transaction_identities(connection: Connection, table, column_names: tuple[str, ...]) -> None:
    """Bloquea la migración si existen identidades bancarias repetidas."""
    duplicate = connection.execute(
        select(table.c.identity_key, func.count()).group_by(table.c.identity_key).having(func.count() > 1).limit(1)
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            _(
                "No se puede aplicar la unicidad de movimientos bancarios: la identidad "
                "%(identity)s se repite. Los registros existentes se conservaron."
            )
            % {"identity": duplicate.identity_key}
        )


def _ensure_user_auth_version_column() -> None:
    """Añade `user.auth_version` a esquemas existentes (P3, #1355).

    La columna se agregó al modelo cuando se retiraron las migraciones
    incrementales; sin ella, cargar `User` en una base previa falla y el login
    queda inutilizable. El valor por defecto 0 permite emitir nuevas sesiones.
    """
    from cacao_accounting.database import User

    engine = database.engine
    if not sa_inspect(engine).has_table(User.__tablename__):
        return
    columns = {column["name"] for column in sa_inspect(engine).get_columns(User.__tablename__)}
    if "auth_version" in columns:
        return
    table_name = database.engine.dialect.identifier_preparer.quote(User.__tablename__)
    try:
        database.session.execute(database.text(f"ALTER TABLE {table_name} ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0"))
        database.session.commit()
        log.info("Columna user.auth_version agregada al esquema existente.")
    except SQLAlchemyError:
        database.session.rollback()
        raise


def _ensure_user_api_token_hash_column() -> None:
    """Añade `user.api_token_hash` a esquemas existentes (#2270).

    La huella persistida sustituye a la caché como autoridad para validar el JWT
    cuando Redis no está disponible. Se agrega sin valor por defecto y sin
    backfill: en pre alpha los tokens anteriores se rechazan hasta un nuevo
    inicio de sesión.
    """
    from cacao_accounting.database import User

    engine = database.engine
    if not sa_inspect(engine).has_table(User.__tablename__):
        return
    columns = {column["name"] for column in sa_inspect(engine).get_columns(User.__tablename__)}
    if "api_token_hash" in columns:
        return
    table_name = engine.dialect.identifier_preparer.quote(User.__tablename__)
    try:
        database.session.execute(database.text(f"ALTER TABLE {table_name} ADD COLUMN api_token_hash VARCHAR(64)"))
        database.session.commit()
        log.info("Columna user.api_token_hash agregada al esquema existente.")
    except SQLAlchemyError:
        database.session.rollback()
        raise


def _ensure_document_flow_lock_table() -> None:
    """Crea la tabla de bloqueo del flujo documental en esquemas existentes.

    `create_all` solo crea tablas nuevas al inicializar la base; una base ya
    operativa necesita esta tabla para serializar el consumo de líneas
    documentales (P6). La creación es idempotente y no toca datos.
    """
    from cacao_accounting.database import DocumentFlowLock

    try:
        DocumentFlowLock.__table__.create(bind=database.engine, checkfirst=True)
    except SQLAlchemyError as exc:
        log.warning("No se pudo asegurar la tabla document_flow_lock: {}", exc)


def _ensure_party_tax_id_key_column() -> None:
    """Instala y rellena la clave fiscal normalizada en esquemas existentes.

    Los duplicados históricos no se fusionan: se dejan con clave nula y se
    registran sus IDs para resolución manual; el índice único protege las
    identidades que sí quedan determinadas (#1051).
    """
    from cacao_accounting.database import Party

    engine = database.engine
    inspector = sa_inspect(engine)
    if not inspector.has_table(Party.__tablename__):
        return
    columns = {column["name"] for column in inspector.get_columns(Party.__tablename__)}
    if "tax_id_key" not in columns:
        try:
            database.session.execute(database.text("ALTER TABLE party ADD COLUMN tax_id_key VARCHAR(50)"))
            database.session.commit()
        except SQLAlchemyError:
            database.session.rollback()
            if "tax_id_key" not in {column["name"] for column in sa_inspect(engine).get_columns(Party.__tablename__)}:
                raise

    from cacao_accounting.party_identity import normalize_tax_id

    with engine.begin() as connection:
        rows = connection.execute(select(Party.id, Party.tax_id)).all()
        grouped: dict[str, list[str]] = {}
        for party_id, tax_id in rows:
            key = normalize_tax_id(tax_id)
            if key:
                grouped.setdefault(key, []).append(str(party_id))
        for key, ids in grouped.items():
            if len(ids) == 1:
                connection.execute(Party.__table__.update().where(Party.id == ids[0]).values(tax_id_key=key))
            else:
                connection.execute(Party.__table__.update().where(Party.id.in_(ids)).values(tax_id_key=None))
                log.warning(
                    "Identidad fiscal {} duplicada en party; se dejan sin clave para revisión: {}",
                    key,
                    ", ".join(sorted(ids)),
                )

    _ensure_unique_index(
        table=Party.__table__,
        index_name="uq_party_tax_id_key",
        column_names=("tax_id_key",),
        deduplicate=lambda connection, table, column_names: None,
    )


def _ensure_purchase_invoice_supplier_key() -> None:
    """Rellena la clave de duplicidad de facturas de compra heredadas (#1433).

    El listener solo cubre altas y actualizaciones; una fila histórica con
    clave nula no colisiona con el índice único. Se rellena solo cuando la
    combinación proveedor/número es inequívoca; los duplicados históricos se
    dejan en nulo y se auditan para revisión manual.
    """
    from cacao_accounting.database import PurchaseInvoice

    engine = database.engine
    inspector = sa_inspect(engine)
    if not inspector.has_table(PurchaseInvoice.__tablename__):
        return
    columns = {column["name"] for column in inspector.get_columns(PurchaseInvoice.__tablename__)}
    if "supplier_invoice_key" not in columns:
        return

    with engine.begin() as connection:
        rows = connection.execute(
            select(
                PurchaseInvoice.id,
                PurchaseInvoice.supplier_id,
                PurchaseInvoice.supplier_invoice_no,
                PurchaseInvoice.supplier_invoice_key,
                PurchaseInvoice.docstatus,
            )
        ).all()
        grouped: dict[tuple[str | None, str], list[tuple[str, str | None]]] = {}
        for invoice_id, supplier_id, supplier_invoice_no, supplier_invoice_key, docstatus in rows:
            number = str(supplier_invoice_no or "").strip()
            if docstatus == 2 or not number:
                continue
            grouped.setdefault((supplier_id, number), []).append((str(invoice_id), supplier_invoice_key))
        for (_supplier_id, number), members in grouped.items():
            if len(members) == 1 and members[0][1] is None:
                connection.execute(
                    PurchaseInvoice.__table__.update()
                    .where(PurchaseInvoice.id == members[0][0])
                    .values(supplier_invoice_key=number)
                )
            elif len(members) > 1 and any(key is None for _id, key in members):
                log.warning(
                    "Facturas de compra históricas con número {} duplicado; se dejan sin clave para revisión: {}",
                    number,
                    ", ".join(sorted(invoice_id for invoice_id, _key in members)),
                )


def _ensure_cacao_config_key_unique() -> None:
    """Instala la unicidad de `CacaoConfig.key` en esquemas existentes.

    Las bases nuevas reciben el constraint desde el modelo. En bases creadas
    antes, el upsert de configuración necesita un índice único equivalente;
    los duplicados históricos se consolidan conservando la fila de ULID mayor
    (la más reciente) y se registra la intervención (#1697, QA2 B-1).
    """
    from cacao_accounting.database import CacaoConfig

    _ensure_unique_index(
        table=CacaoConfig.__table__,
        index_name="uq_cacao_config_key",
        column_names=("key",),
        deduplicate=_dedupe_cacao_config_keys,
    )


def _ensure_roles_user_unique() -> None:
    """Instala la unicidad de `(user_id, role_id)` en esquemas existentes.

    Conserva la asignación activa cuando existe y consolida las filas
    duplicadas con el ULID mayor; registra la intervención (#1682, QA2 B-1).
    """
    from cacao_accounting.database import RolesUser

    _ensure_unique_index(
        table=RolesUser.__table__,
        index_name="uq_roles_user",
        column_names=("user_id", "role_id"),
        deduplicate=_dedupe_roles_user_assignments,
    )


def _unique_index_exists(bind: Engine | Connection, table_name: str, index_name: str, column_names: tuple[str, ...]) -> bool:
    """Comprueba que el índice único canónico existe con sus columnas."""
    inspector = sa_inspect(bind)
    if not inspector.has_table(table_name):
        return False
    expected = list(column_names)
    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("name") == index_name:
            if constraint.get("column_names") == expected:
                return True
            raise RuntimeError(f"El constraint {index_name} no protege {', '.join(expected)}.")
    for index in inspector.get_indexes(table_name):
        if index.get("name") == index_name:
            if index.get("unique") and index.get("column_names") == expected:
                return True
            raise RuntimeError(f"El índice {index_name} no protege {', '.join(expected)} de forma única.")
    return False


def _ensure_unique_index(
    *,
    table,
    index_name: str,
    column_names: tuple[str, ...],
    deduplicate,
) -> None:
    """Crea un índice único idempotente tras consolidar duplicados históricos."""
    engine = database.engine
    if not sa_inspect(engine).has_table(table.name):
        return

    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                if not _unique_index_exists(connection, table.name, index_name, column_names):
                    deduplicate(connection, table, column_names)
                    _create_unique_index_sql(connection, table, index_name, column_names)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return

    try:
        with engine.begin() as connection:
            if not _unique_index_exists(connection, table.name, index_name, column_names):
                deduplicate(connection, table, column_names)
                _create_unique_index_sql(connection, table, index_name, column_names)
    except SQLAlchemyError:
        if _unique_index_exists(engine, table.name, index_name, column_names):
            return
        raise


def _create_unique_index_sql(connection: Connection, table, index_name: str, column_names: tuple[str, ...]) -> None:
    """Crea el índice con DDL sin mutar el metadata global de SQLAlchemy."""
    preparer = connection.dialect.identifier_preparer
    quoted_table = preparer.format_table(table)
    quoted_index = preparer.quote(index_name)
    quoted_columns = ", ".join(preparer.quote(name) for name in column_names)
    connection.exec_driver_sql(f"CREATE UNIQUE INDEX {quoted_index} ON {quoted_table} ({quoted_columns})")


def _dedupe_cacao_config_keys(connection: Connection, table, column_names: tuple[str, ...]) -> None:
    """Conserva una fila por clave y elimina el resto, dejando registro."""
    key_column = table.c[column_names[0]]
    rows = connection.execute(select(table.c.id, key_column).order_by(table.c.id)).all()
    keep: dict[str, str] = {}
    for row in rows:
        keep[str(row[1])] = str(row[0])
    removed = [str(row[0]) for row in rows if str(row[0]) != keep.get(str(row[1]))]
    if removed:
        connection.execute(delete(table).where(table.c.id.in_(removed)))
        log.warning(
            "Se consolidaron {} filas duplicadas de cacao_config conservando la más reciente. IDs: {}",
            len(removed),
            ", ".join(sorted(removed)),
        )


def _dedupe_roles_user_assignments(connection: Connection, table, column_names: tuple[str, ...]) -> None:
    """Conserva una asignación por usuario/rol, prefiriendo la activa."""
    user_column = table.c[column_names[0]]
    role_column = table.c[column_names[1]]
    rows = connection.execute(select(table.c.id, user_column, role_column, table.c.active).order_by(table.c.id)).all()
    groups: dict[tuple[str, str], list] = {}
    for row in rows:
        groups.setdefault((str(row[1]), str(row[2])), []).append(row)
    removed: list[str] = []
    for group in groups.values():
        active_rows = [row for row in group if bool(row[3])]
        keep_row = max(active_rows or group, key=lambda row: str(row[0]))
        removed.extend(str(row[0]) for row in group if str(row[0]) != str(keep_row[0]))
    if removed:
        connection.execute(delete(table).where(table.c.id.in_(removed)))
        log.warning(
            "Se consolidaron {} asignaciones duplicadas de roles_user. IDs: {}",
            len(removed),
            ", ".join(sorted(removed)),
        )


def _ensure_audit_trail_hash_version_column() -> None:
    """Suple idempotentemente ``audit_trail.hash_version`` en esquemas existentes.

    La cadena de hashes de auditoría v2 ata la identidad de la fila al
    payload; ``create_all`` crea la columna en esquemas nuevos y esta rutina
    la agrega sin migración formal en bases existentes, dejando ``NULL`` en
    las filas heredadas que se verifican con el formato v1.
    """
    try:
        from sqlalchemy import inspect as sa_inspect

        from cacao_accounting.database import AuditTrail

        inspector = sa_inspect(database.engine)
        if not inspector.has_table(AuditTrail.__tablename__):
            return
        columns = {column["name"] for column in inspector.get_columns(AuditTrail.__tablename__)}
        if "hash_version" in columns:
            return
        database.session.execute(database.text("ALTER TABLE audit_trail ADD COLUMN hash_version INTEGER"))
        database.session.commit()
        log.info("Columna hash_version agregada a audit_trail.")
    except (OperationalError, ProgrammingError, InterfaceError):
        database.session.rollback()
    except Exception as exc:
        database.session.rollback()
        log.warning("Could not ensure audit_trail.hash_version during initialization: {}", exc)
