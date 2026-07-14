# cacaoctl — CLI de administración

`cacaoctl` es la interfaz de línea de comandos oficial de Cacao Accounting.
Está construida con [Click](https://click.palletsprojects.com/) y organiza los
comandos por áreas: base de datos, servidor, desarrollo y sistema.

## Instalación

`cacaoctl` se instala automáticamente al instalar el paquete:

```bash
pip install cacao-accounting
```

O desde fuentes:

```bash
pip install -e .
```

Para verificar que está disponible:

```bash
cacaoctl version
```

## Uso básico

```bash
cacaoctl [opciones globales] <comando> [subcomando] [opciones]
```

Ejecutado sin argumentos muestra el banner y la ayuda general:

```bash
cacaoctl
```

## Opciones globales

| Opción        | Descripción                                       |
|---------------|---------------------------------------------------|
| `--env`       | Entorno de ejecución (`dev`, `test`, `prod`).     |
| `--verbose`   | Información detallada de la ejecución.            |
| `--quiet`     | Reduce la salida de la herramienta.               |
| `--version`   | Muestra la versión instalada.                     |
| `-h`, `--help`| Muestra la ayuda del comando.                     |

## Comandos disponibles

### Base de datos (`db`)

```
cacaoctl db <subcomando> [opciones]
```

| Subcomando  | Descripción                                          |
|-------------|------------------------------------------------------|
| `init`      | Crea una nueva base de datos.                        |
| `reset`     | Recrea completamente la base de datos.               |
| `clean`     | Elimina la base de datos (solo desarrollo).          |
| `seed`      | Inserta datos de ejemplo en la base de datos.        |

#### `db init`

Crea el esquema de base de datos e inserta los datos base.

```bash
# Crear base de datos con valores predeterminados
cacaoctl db init

# Forzar recreación si ya existe
cacaoctl db init --force

# Crear e insertar datos de ejemplo
cacaoctl db init --seed

# Combinar opciones
cacaoctl db init --force --seed
```

Opciones:

- `--force`: Elimina una base existente antes de crear la nueva.
- `--seed`: Inserta datos de ejemplo después de crear la base.

#### `db reset`

Elimina y vuelve a crear toda la base de datos. Solicita confirmación
interactiva a menos que se use `--force`.

```bash
cacaoctl db reset
cacaoctl db reset --force
cacaoctl db reset --seed
```

Opciones:

- `--force`: Omite la confirmación de la operación destructiva.
- `--seed`: Inserta datos de ejemplo después de recrear la base.

#### `db clean`

Elimina toda la base de datos. Solo disponible en entornos de desarrollo
a menos que se use `--force`.

```bash
cacaoctl db clean
cacaoctl db clean --force
```

Opciones:

- `--force`: Omite la confirmación y permite ejecutarlo fuera de desarrollo.

#### `db seed`

Carga datos de ejemplo en una base de datos existente.

```bash
cacaoctl db seed
```

### Servidor

#### `run`

Inicia el servidor de desarrollo de Flask.

```bash
cacaoctl run
cacaoctl run --host 0.0.0.0 --port 5000
cacaoctl run --no-debug
```

Opciones:

| Opción             | Por defecto   | Descripción                              |
|--------------------|---------------|------------------------------------------|
| `--host`           | `127.0.0.1`   | Dirección de escucha.                    |
| `--port`           | *config*      | Puerto de escucha.                       |
| `--debug/--no-debug`| `True`       | Activa el depurador de Werkzeug.         |

#### `serve`

Inicia el servidor de producción con Waitress como servidor WSGI.

```bash
cacaoctl serve
```

### Desarrollo

#### `shell`

Abre una consola interactiva de Python con el contexto de la aplicación
ya activo. Si IPython está disponible, lo utiliza; de lo contrario usa
la shell estándar de Python.

```bash
cacaoctl shell
```

Dentro de la consola están disponibles:

- `app`: La aplicación Flask.
- `db`: La instancia de SQLAlchemy.

#### `routes`

Lista todas las rutas registradas en la aplicación con sus métodos HTTP.

```bash
cacaoctl routes
```

### Sistema

#### `version`

Muestra la versión instalada de Cacao Accounting.

```bash
cacaoctl version
```

#### `status`

Muestra el estado general del sistema: aplicación, versión, conexión a
base de datos, Redis, entorno y servidor.

```bash
cacaoctl status
```

Ejemplo de salida:

```
Application  : Cacao Accounting
Version      : 2026.07.13
Database     : Conectada
Redis        : No configurado
Environment  : development
Server       : Waitress
```

#### `config`

Muestra un resumen de la configuración activa del sistema.

```bash
cacaoctl config
```

Ejemplo de salida:

```
Environment  : development
Database     : sqlite
Debug        : True
Host         : 0.0.0.0
Port         : 5000
Threads      : 4
Cache        : DummyCache
```

## Autocompletado para el shell

`cacaoctl` soporta autocompletado para bash, zsh y fish gracias a Click
8.x.

### bash

Agrega la siguiente línea a tu `~/.bashrc`:

```bash
eval "$(_CACAOCTL_COMPLETE=bash_source cacaoctl)"
```

Vuelve a cargar la configuración:

```bash
source ~/.bashrc
```

### zsh

Agrega la siguiente línea a tu `~/.zshrc`:

```zsh
eval "$(_CACAOCTL_COMPLETE=zsh_source cacaoctl)"
```

Vuelve a cargar la configuración:

```zsh
source ~/.zshrc
```

### fish

Agrega la siguiente línea a
`~/.config/fish/completions/cacaoctl.fish`:

```fish
_CACAOCTL_COMPLETE=fish_source cacaoctl | source
```

### Comando `completion`

También puedes usar el comando interno de `cacaoctl` para ver las
instrucciones:

```bash
cacaoctl completion bash
cacaoctl completion zsh
cacaoctl completion fish
```
