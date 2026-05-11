# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Funciones auxiliares relacionadas a la base de datos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date
from os import environ
from typing import Optional

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Flask
from sqlalchemy.exc import OperationalError, InterfaceError, ProgrammingError

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import database
from cacao_accounting.logs import log

MAXIMO_RESULTADOS_EN_CONSULTA_PAGINADA = 10
DB_CONNECTION_FAILED = "No se pudo establecer conexion a la base de datos."
DB_RETRYING_CONNECTION = "Reintentando conectar a la base de datos."

# <---------------------------------------------------------------------------------------------> #
# Herramientas auxiliares para verificar la ejecución de la base de datos.

if environ.get("CACAO_TEST", None):  # pragma: no cover
    TIEMPO_ESPERA = 0
else:
    TIEMPO_ESPERA = 20


def verifica_coneccion_db(app):  # pragma: no cover
    """Verifica si es posible conentarse a la base de datos."""
    import time

    with app.app_context():
        __inicio = time.time()
        while (time.time() - __inicio) < TIEMPO_ESPERA:
            log.info("Verificando conexión a la base de datos.")
            try:
                from cacao_accounting.database import User

                QUERY = database.session.execute(database.select(User))

                if QUERY:
                    DB_CONN = True
                    log.info("Conexión a la base de datos exitosa.")
                break
            except OperationalError:
                DB_CONN = False
                log.warning(DB_CONNECTION_FAILED)
                log.info(DB_RETRYING_CONNECTION)
            except InterfaceError:
                DB_CONN = False
                log.warning(DB_CONNECTION_FAILED)
                log.info(DB_RETRYING_CONNECTION)
            except ProgrammingError:
                DB_CONN = False
                log.warning(DB_CONNECTION_FAILED)
                log.info(DB_RETRYING_CONNECTION)

            if not environ.get("CACAO_TEST", None):
                time.sleep(2)

        try:
            if not DB_CONN:
                log.warning("No fue imposible establecer una conexión con la base de datos.")
            return DB_CONN
        except UnboundLocalError:
            return False


def entidades_creadas():
    """Verifica si al menos una entidad ha sido creado en el sistema."""
    from cacao_accounting.database import Entity

    try:
        CONSULTA = database.session.execute(database.select(Entity)).first()

        if CONSULTA:
            return True
        else:
            return False

    except Exception:  # noqa: BLE001
        return False


def usuarios_creados():
    """Verifica si al menos un usuario ha sido creado en el sistema."""
    from cacao_accounting.database import User

    try:
        CONSULTA = database.session.execute(database.select(User)).first()

        if CONSULTA is not None:
            return True
        else:
            return False

    except OperationalError:
        return False

    except TypeError:
        return False

    except InterfaceError:
        return False

    except ProgrammingError:
        return False


def inicia_base_de_datos(app: Flask, user: str, passwd: str, with_examples: bool) -> bool:  # pragma: no cover
    """Inicia esquema de base datos."""
    from cacao_accounting.datos import base_data, dev_data

    if entidades_creadas():
        return True

    log.info("Intentando inicializar base de datos.")

    with app.app_context():
        try:
            database.create_all()
            log.info("Esquema de base de datos creado correctamente.")
            if with_examples:
                log.trace("Creando datos de prueba.")
                base_data(user, passwd, carga_rapida=False)
                dev_data()
            else:
                base_data(user, passwd, carga_rapida=True)
            DB_ESQUEMA = True
        except Exception:
            log.exception("No se pudo inicializar esquema de base de datos.")
            DB_ESQUEMA = False

        if DB_ESQUEMA and not with_examples:
            from cacao_accounting.database import CacaoConfig as Config

            config = Config(
                key="SETUP_COMPLETE",
                value="False",
            )

            database.session.add(config)
            database.session.commit()

    return DB_ESQUEMA


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


def obtener_id_usuario_por_nombre(usuario: str | None) -> str | None:
    """Devuelve el UUID de un usuario en base a su id."""
    if usuario:
        from cacao_accounting.database import User

        USUARIO = User.query.filter_by(user=usuario).first()
        return USUARIO.id
    else:
        return None


def db_version():  # pragma: no cover
    """Return database version as text."""
    from flask import current_app
    from cacao_accounting.database import database
    from sqlalchemy.sql import text

    with current_app.app_context():
        DABATASE_URI = current_app.config.get("SQLALCHEMY_DATABASE_URI")

        if DABATASE_URI.startswith("mysql+pymysql"):
            Q = database.session.execute(text("SELECT version();"))
            for i in Q:
                db_version = str(i)
        elif DABATASE_URI.startswith("postgresql+pg8000"):
            Q = database.session.execute(text("SELECT VERSION();"))
            for i in Q:
                db_version = str(i)
        else:
            Q = database.session.execute(text("select sqlite_version();"))
            for i in Q:
                db_version = str(i)

    return db_version


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


def get_next_sequence_value(sequence_id: str) -> int:
    """Obtiene y reserva el siguiente valor de una secuencia.

    Operacion atomica — incrementa el contador y devuelve el nuevo valor.
    Soporta politica de reset: never, yearly, monthly.

    Args:
        sequence_id: ID de la secuencia (PK de la tabla sequence)

    Returns:
        Entero con el siguiente valor disponible de la secuencia.

    Raises:
        ValueError: Si la secuencia no existe.
    """
    from cacao_accounting.database import Sequence

    seq = database.session.execute(database.select(Sequence).filter_by(id=sequence_id)).scalar_one_or_none()

    if seq is None:
        raise ValueError(f"Secuencia con id '{sequence_id}' no encontrada.")

    seq.current_value = (seq.current_value or 0) + seq.increment
    database.session.flush()

    return int(seq.current_value)


def format_sequence_value(value: int, padding: int) -> str:
    """Formatea un valor de secuencia con el padding indicado.

    Args:
        value: Valor entero de la secuencia.
        padding: Cantidad de dígitos con cero a la izquierda.

    Returns:
        Cadena formateada. Ejemplo: value=5, padding=5 → '00005'
    """
    return str(value).zfill(padding)


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

    if naming_series_id:
        series = database.session.execute(database.select(NamingSeries).filter_by(id=naming_series_id)).scalar_one_or_none()

        if series is None:
            raise ValueError(f"NamingSeries con id '{naming_series_id}' no encontrada.")

        prefix = resolve_naming_series_prefix(series.prefix_template, posting_date, company)

    if sequence_id:
        seq = database.session.execute(database.select(Sequence).filter_by(id=sequence_id)).scalar_one_or_none()

        if seq is None:
            raise ValueError(f"Sequence con id '{sequence_id}' no encontrada.")

        if should_reset_sequence(sequence_id, posting_date):
            reset_sequence(sequence_id)
        next_val = get_next_sequence_value(sequence_id)
        suffix = format_sequence_value(next_val, seq.padding)
        full_identifier = f"{prefix}{suffix}"
    else:
        full_identifier = prefix or entity_id

    log_entry = GeneratedIdentifierLog(
        entity_type=entity_type,
        entity_id=entity_id,
        full_identifier=full_identifier,
        sequence_id=sequence_id,
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


def should_reset_sequence(sequence_id: str, posting_date: date) -> bool:
    """Determina si una secuencia debe reiniciarse segun su politica.

    Politicas soportadas:
    - 'never': nunca se reinicia
    - 'yearly': se reinicia al inicio de cada anio
    - 'monthly': se reinicia al inicio de cada mes

    Args:
        sequence_id: ID de la secuencia a evaluar
        posting_date: Fecha contable del documento actual

    Returns:
        True si la secuencia debe reiniciarse, False en caso contrario.
    """
    from cacao_accounting.database import GeneratedIdentifierLog, Sequence

    seq = database.session.execute(database.select(Sequence).filter_by(id=sequence_id)).scalar_one_or_none()

    if seq is None or seq.reset_policy == "never":
        return False

    last_log = database.session.execute(
        database.select(GeneratedIdentifierLog)
        .filter_by(sequence_id=sequence_id)
        .order_by(GeneratedIdentifierLog.generated_at.desc())
    ).scalar_one_or_none()

    if last_log is None or last_log.posting_date is None:
        return False

    if seq.reset_policy == "yearly":
        return posting_date.year != last_log.posting_date.year

    if seq.reset_policy == "monthly":
        return posting_date.year != last_log.posting_date.year or posting_date.month != last_log.posting_date.month

    return False


def reset_sequence(sequence_id: str) -> None:
    """Reinicia el contador de una secuencia a cero.

    Usado por should_reset_sequence cuando se detecta un cambio de periodo.

    Args:
        sequence_id: ID de la secuencia a reiniciar.

    Raises:
        ValueError: Si la secuencia no existe.
    """
    from cacao_accounting.database import Sequence

    seq = database.session.execute(database.select(Sequence).filter_by(id=sequence_id)).scalar_one_or_none()

    if seq is None:
        raise ValueError(f"Secuencia con id '{sequence_id}' no encontrada.")

    seq.current_value = 0
    database.session.flush()
