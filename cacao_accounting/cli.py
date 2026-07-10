# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Interfaz de linea de comandos para administrar Cacao Accounting.

La herramienta ``cacaoctl`` es la interfaz oficial de administración del sistema,
oculta la implementación interna basada en Flask y organiza los comandos por
áreas (base de datos, servidor, desarrollo y sistema) siguiendo el estilo de
herramientas modernas como Git, Docker o Poetry.
"""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
import os
import sys

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
import click

# ---------------------------------------------------------------------------------------
# Recursos locales
# --------------------------------------------------------------------------------------
from cacao_accounting.logs import log
from cacao_accounting.version import APPNAME, VERSION

# <---------------------------------------------------------------------------------------------> #
# Constantes de presentación.
NOMBRE_PROGRAMA = "cacaoctl"
COLOR_EXITO = "green"
COLOR_ADVERTENCIA = "yellow"
COLOR_ERROR = "red"
COLOR_INFO = "cyan"
COLOR_TITULO = "bright_magenta"


class CacaoGroup(click.Group):
    """Grupo de comandos que organiza la ayuda por categorías."""

    ORDEN_GRUPOS = ["Database", "Server", "Development", "System"]

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Muestra los comandos agrupados bajo encabezados por categoría."""
        comandos = []
        for nombre in self.list_commands(ctx):
            cmd = self.get_command(ctx, nombre)
            if cmd is None or getattr(cmd, "hidden", False):
                continue
            comandos.append((nombre, cmd))

        if not comandos:
            return

        agrupados: dict[str | None, list[tuple[str, click.Command]]] = {}
        for nombre, cmd in comandos:
            grupo = getattr(cmd, "group", None)
            agrupados.setdefault(grupo, []).append((nombre, cmd))

        secciones: list[tuple[str | None, list[tuple[str, click.Command]]]] = []
        for grupo in self.ORDEN_GRUPOS:
            if grupo in agrupados:
                secciones.append((grupo, agrupados.pop(grupo)))
        for grupo, items in agrupados.items():
            secciones.append((grupo, items))

        limite = formatter.width - 6 - max(len(n) for n, _ in comandos)
        for grupo, items in secciones:
            filas = [(nombre, cmd.get_short_help_str(limite)) for nombre, cmd in items]
            encabezado = grupo if grupo else "Commands"
            with formatter.section(encabezado):
                formatter.write_dl(filas)

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Escribe el epílogo respetando los saltos de linea de los ejemplos."""
        if self.epilog:
            formatter.write_paragraph()
            for linea in self.epilog.split("\n"):
                if linea.strip():
                    formatter.write_text(linea)
                else:
                    formatter.write("")


def _mensaje_exito(mensaje: str) -> None:
    """Imprime un mensaje de éxito con formato visual."""
    click.secho(f"✓ {mensaje}", fg=COLOR_EXITO)


def _mensaje_advertencia(mensaje: str) -> None:
    """Imprime un mensaje de advertencia con formato visual."""
    click.secho(f"⚠ {mensaje}", fg=COLOR_ADVERTENCIA)


def _mensaje_error(mensaje: str) -> None:
    """Imprime un mensaje de error con formato visual."""
    click.secho(f"✗ {mensaje}", fg=COLOR_ERROR)


def _mensaje_info(mensaje: str) -> None:
    """Imprime un mensaje informativo con formato visual."""
    click.secho(f"ℹ {mensaje}", fg=COLOR_INFO)


def _obtener_aplicacion():
    """Construye la aplicación Flask con la configuración predeterminada.

    La aplicación se construye de forma perezosa para mantener rápida la
    invocación de comandos que no requieren el contexto completo, como
    ``--version``.
    """
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion

    return create_app(configuracion)


def _entorno_actual() -> str:
    """Devuelve el nombre del entorno de ejecución configurado."""
    if os.environ.get("CACAO_TEST"):
        return "test"
    if os.environ.get("FLASK_ENV") == "production":
        return "production"
    return "development"


# <---------------------------------------------------------------------------------------------> #
# Grupo principal de la interfaz de linea de comandos.
@click.group(
    cls=CacaoGroup,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="CLI oficial para administrar Cacao Accounting.",
    epilog=(
        "Ejemplos:\n\n"
        "  cacaoctl run\n"
        "  cacaoctl serve\n"
        "  cacaoctl db init\n"
        "  cacaoctl db reset\n"
        "  cacaoctl status\n"
        "  cacaoctl version\n"
    ),
)
@click.option(
    "--env",
    type=click.Choice(["dev", "test", "prod"], case_sensitive=False),
    default=None,
    help="Entorno de ejecución (dev, test, prod).",
)
@click.option("--verbose", is_flag=True, help="Muestra información detallada de la ejecución.")
@click.option("--quiet", is_flag=True, help="Reduce la salida de la herramienta.")
@click.version_option(version=VERSION, prog_name=NOMBRE_PROGRAMA, message="%(prog)s %(version)s")
@click.pass_context
def linea_comandos(ctx: click.Context, env: str | None, verbose: bool, quiet: bool) -> None:
    """Punto de entrada de la linea de comandos."""
    if verbose:
        log.remove()
        log.add(sys.stderr, level="DEBUG")
    elif quiet:
        log.remove()
        log.add(sys.stderr, level="WARNING")

    if env == "test":
        os.environ["CACAO_TEST"] = "True"
    elif env == "prod":
        os.environ["FLASK_ENV"] = "production"

    ctx.ensure_object(dict)
    ctx.obj["ENV"] = env or _entorno_actual()

    if ctx.invoked_subcommand is None:
        _mostrar_banner()
        click.echo(ctx.get_help())


def _mostrar_banner() -> None:
    """Imprime un encabezado visual para la herramienta."""
    click.secho(f"{APPNAME} CLI", fg=COLOR_TITULO, bold=True)
    click.secho("Administración del sistema", fg=COLOR_INFO)
    click.echo("")


# <---------------------------------------------------------------------------------------------> #
# Comandos de base de datos agrupados bajo el subcomando ``db``.
@click.group(help="Administración de la base de datos.")
def db() -> None:
    """Comandos relacionados con la base de datos."""


db.group = "Database"  # type: ignore[attr-defined,method-assign,assignment]
linea_comandos.add_command(db)


@db.command(name="init", help="Crea una nueva base de datos.")
@click.option("--force", is_flag=True, help="Elimina una base existente antes de crear la nueva.")
@click.option("--seed", is_flag=True, help="Inserta datos de ejemplo después de crear la base.")
def db_init(force: bool, seed: bool) -> None:
    """Crea el esquema de base de datos e inserta los datos base."""
    from cacao_accounting.database import database
    from cacao_accounting.database.helpers import (
        entidades_creadas,
        inicia_base_de_datos,
        usuarios_creados,
    )

    app = _obtener_aplicacion()
    with app.app_context():
        existe = entidades_creadas() or usuarios_creados()
        if force and existe:
            _mensaje_advertencia("La base de datos existente será reemplazada.")
            database.drop_all()
        elif existe and not force:
            _mensaje_error("La base de datos ya existe, use --force para sobrescribirla.")
            raise click.exceptions.Exit(1)

        usuario = os.environ.get("CACAO_USER") or "cacao"
        contrasena = os.environ.get("CACAO_PSWD") or "cacao"
        if inicia_base_de_datos(app=app, user=usuario, passwd=contrasena, with_examples=seed):
            _mensaje_exito("Base de datos creada.")
        else:
            _mensaje_error("No fue posible crear la base de datos.")
            raise click.exceptions.Exit(1)


@db.command(name="reset", help="Recrea completamente la base de datos.")
@click.option("--force", is_flag=True, help="Omite la confirmación de la operación destructiva.")
@click.option("--seed", is_flag=True, help="Inserta datos de ejemplo después de recrear la base.")
def db_reset(force: bool, seed: bool) -> None:
    """Elimina y vuelve a crear toda la base de datos."""
    from cacao_accounting.database import database
    from cacao_accounting.database.helpers import (
        entidades_creadas,
        inicia_base_de_datos,
        usuarios_creados,
    )

    app = _obtener_aplicacion()
    with app.app_context():
        existe = entidades_creadas() or usuarios_creados()

    if existe and not force:
        click.echo("Esta operación eliminará toda la base de datos.")
        if not click.confirm("¿Desea continuar?"):
            _mensaje_advertencia("Operación cancelada por el usuario.")
            raise click.exceptions.Exit(1)

    with app.app_context():
        database.drop_all()
        _mensaje_advertencia("Base de datos eliminada.")
        usuario = os.environ.get("CACAO_USER") or "cacao"
        contrasena = os.environ.get("CACAO_PSWD") or "cacao"
        if inicia_base_de_datos(app=app, user=usuario, passwd=contrasena, with_examples=seed):
            _mensaje_exito("Base de datos recreada correctamente.")
        else:
            _mensaje_error("No fue posible recrear la base de datos.")
            raise click.exceptions.Exit(1)


@db.command(name="clean", help="Elimina la base de datos (solo desarrollo).")
@click.option("--force", is_flag=True, help="Omite la confirmación y permite ejecutarlo fuera de desarrollo.")
def db_clean(force: bool) -> None:
    """Elimina toda la base de datos; disponible principalmente para desarrollo."""
    from cacao_accounting.config import TESTING_MODE
    from cacao_accounting.database import database
    from cacao_accounting.database.helpers import (
        entidades_creadas,
        usuarios_creados,
    )

    if not TESTING_MODE and not force:
        _mensaje_error("Este comando solo está disponible en entornos de desarrollo o con --force.")
        raise click.exceptions.Exit(1)

    app = _obtener_aplicacion()
    with app.app_context():
        existe = entidades_creadas() or usuarios_creados()

    if existe and not force:
        click.echo("Esta operación eliminará toda la base de datos.")
        if not click.confirm("¿Desea continuar?"):
            _mensaje_advertencia("Operación cancelada por el usuario.")
            raise click.exceptions.Exit(1)

    with app.app_context():
        database.drop_all()
        _mensaje_exito("Base de datos eliminada.")


@db.command(name="seed", help="Inserta datos de ejemplo en la base de datos.")
def db_seed() -> None:
    """Carga datos de ejemplo en una base de datos existente."""
    from cacao_accounting.datos.dev import dev_data

    app = _obtener_aplicacion()
    with app.app_context():
        try:
            dev_data()
            _mensaje_exito("Datos de ejemplo insertados.")
        except Exception as exc:  # noqa: BLE001
            log.exception("Error al insertar datos de ejemplo.")
            _mensaje_error(f"No fue posible insertar los datos de ejemplo: {exc}")
            raise click.exceptions.Exit(1)


# <---------------------------------------------------------------------------------------------> #
# Comandos de servidor.
@linea_comandos.command(name="run", help="Inicia el servidor de desarrollo.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Dirección de escucha.")
@click.option("--port", default=None, help="Puerto de escucha (por defecto el de configuración).")
@click.option("--debug/--no-debug", default=True, help="Activa el depurador de Werkzeug.")
def run(host: str, port: str | None, debug: bool) -> None:
    """Ejecuta el servidor de desarrollo de Flask."""
    from cacao_accounting.config import PORT

    app = _obtener_aplicacion()
    puerto = int(port) if port else int(PORT)
    _mensaje_info(f"Iniciando servidor de desarrollo en http://{host}:{puerto}")
    app.run(host=host, port=puerto, debug=debug, use_reloader=debug, use_debugger=debug)


run.group = "Server"  # type: ignore[attr-defined]


@linea_comandos.command(name="serve", help="Inicia el servidor de producción (Waitress).")
def serve() -> None:
    """Ejecuta la aplicación con Waitress como servidor WSGI."""
    from cacao_accounting.server import server

    try:
        server()
    except Exception as exc:  # noqa: BLE001
        _mensaje_error(f"No fue posible iniciar el servidor: {exc}")
        raise click.exceptions.Exit(1)


serve.group = "Server"  # type: ignore[attr-defined]


# <---------------------------------------------------------------------------------------------> #
# Comandos de desarrollo.
@linea_comandos.command(
    name="shell",
    help="Abre una consola interactiva con el contexto de la aplicación.",
)
def shell() -> None:
    """Abre una shell de Python con la aplicación ya en contexto."""
    app = _obtener_aplicacion()
    ctx = app.app_context()
    ctx.push()
    namespace = {"app": app, "db": _base_datos()}
    banner = f"Consola interactiva de {APPNAME}. El contexto de la aplicación está activo."
    try:
        from IPython import embed  # type: ignore[import-untyped]

        embed(banner1=banner, user_ns=namespace)
    except ImportError:
        import code

        code.interact(banner, local=namespace)
    finally:
        ctx.pop()


def _base_datos():
    """Devuelve la instancia de SQLAlchemy para la consola interactiva."""
    from cacao_accounting.database import database

    return database


shell.group = "Development"  # type: ignore[attr-defined]


@linea_comandos.command(
    name="routes",
    help="Lista las rutas registradas en la aplicación.",
)
def routes() -> None:
    """Muestra la tabla de rutas de la aplicación."""
    from cacao_accounting.database.helpers import db_version

    app = _obtener_aplicacion()
    with app.app_context():
        ancho = 0
        reglas = list(app.url_map.iter_rules())
        if reglas:
            ancho = max(len(str(r.rule)) for r in reglas)
        for regla in sorted(reglas, key=lambda r: str(r.rule)):
            metodos = ",".join(sorted(m for m in regla.methods if m not in ("HEAD", "OPTIONS")))
            click.echo(f"{str(regla.rule).ljust(ancho)}  {metodos}")
        try:
            click.echo("")
            click.secho(f"Motor: {db_version()}", fg=COLOR_INFO)
        except Exception:  # noqa: BLE001
            pass


routes.group = "Development"  # type: ignore[attr-defined]


# <---------------------------------------------------------------------------------------------> #
# Comandos de sistema.
@linea_comandos.command(name="version", help="Muestra la versión instalada.")
def version() -> None:
    """Imprime la versión de la aplicación."""
    click.echo(VERSION)


version.group = "System"  # type: ignore[attr-defined]


@linea_comandos.command(name="status", help="Muestra el estado general del sistema.")
def status() -> None:
    """Reporta el estado de la aplicación y sus dependencias."""
    from cacao_accounting.config import configuracion
    from cacao_accounting.database.helpers import verifica_coneccion_db

    base_datos = "Desconectada"
    app = _obtener_aplicacion()
    with app.app_context():
        if verifica_coneccion_db(app):
            base_datos = "Conectada"

    redis = "No configurado"
    if str(configuracion.get("CACHE_TYPE", "")).lower() == "rediscache":
        redis = "Conectado"

    filas = [
        ("Application", APPNAME),
        ("Version", VERSION),
        ("Database", base_datos),
        ("Redis", redis),
        ("Environment", _entorno_actual()),
        ("Server", "Waitress"),
    ]
    for etiqueta, valor in filas:
        click.echo(f"{etiqueta.ljust(12)} : {valor}")


status.group = "System"  # type: ignore[attr-defined]


@linea_comandos.command(name="config", help="Muestra la configuración activa.")
def config() -> None:
    """Imprime un resumen de la configuración actual del sistema."""
    from cacao_accounting.config import (
        PORT,
        TESTING_MODE,
        THREADS,
        configuracion,
    )

    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    motor = uri.split("://")[0] if "://" in uri else "desconocido"
    depuracion = "True" if TESTING_MODE else "False"

    filas = [
        ("Environment", _entorno_actual()),
        ("Database", motor),
        ("Debug", depuracion),
        ("Host", "0.0.0.0"),
        ("Port", str(PORT)),
        ("Threads", str(THREADS)),
        ("Cache", str(configuracion.get("CACHE_TYPE", ""))),
    ]
    for etiqueta, valor in filas:
        click.echo(f"{etiqueta.ljust(12)} : {valor}")


config.group = "System"  # type: ignore[attr-defined]


def linea_comandos_main(as_module: bool = False) -> None:  # pragma: no cover
    """Ejecuta la linea de comandos con identidad propia de Cacao Accounting."""
    linea_comandos.main(prog_name=NOMBRE_PROGRAMA, args=sys.argv[1:])
