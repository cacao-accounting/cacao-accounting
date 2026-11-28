# Cacao Accounting setup:

Following the [the twelve factor app](https://12factor.net/config) recommendations Cacao Accounting can be configured with enviroment variables.

This is a list of available options.
es:

## Required

| Option    |          Description          |                            Examples / Comments |
| --------- | :---------------------------: | ---------------------------------------------: |
| CACAO_DB  |  Database connection string.  |                             See examples above |
| CACAO_KEY | Unique key to secure cookies. | Must contains uppercase, lowercase and numbers |

## Optional

| Option           |            Description             |               Examples / Comments |
| ---------------- | :--------------------------------: | --------------------------------: |
| CACAO_THREADS    |        CPU threads to use.         |                         Default 4 |
| CACAO_PORT       | POrt for the WSGI server to listen |                      Default 8080 |
| PYTHON_CPU_COUNT |        Max CPU unit to use         |                    Container only |
| CACHE_REDIS_URL  | Redis URL for application cache (database 2) | Example: redis://localhost:6379/2 |
| RATELIMIT_STORAGE_URI | Redis URL for rate limiting (database 0) | Example: redis://localhost:6379/0 |

## Initial Setup

The first time your run Cacao Accounting the following variables are used to set a custom master user, if not available
default options will be used.

| Option     |      Description       | Examples / Comments |
| ---------- | :--------------------: | ------------------: |
| CACAO_USER |    Master user `id`    |     Default `cacao` |
| CACAO_PSWD | Master user `password` |     Default `cacao` |

!!! warning

    Default user and password are available in the app source code so it is advised always use custom user and password for
    the system master user.

## Setup enviroment variables:

### Linux

```bash
export CACAO_DB=DATABASE_CONNECTION_URI
export CACAO_KEY=SECRETKEY
```

### Windows:

```powershell
setx CACAO_DB "DATABASE_CONNECTION_URI"
setx CACAO_KEY "SECRETKEY"
```

### Dockerfile

```dockerfile
ENV CACAO_DB=DATABASE_CONNECTION_URI
ENV CACAO_KEY=SECRETKEY
```

## Database Connection String

!!! info

    Cacao Accounting is tested with SQLite, Postgresql and MySQL8, the system should work with MariaDB without changes but
    support for MariaDB must be considered experimental and not fully tested.

### Postgresql :simple-postgresql::

#### psycopg (v3)

psycopg 3 is the default Postgresql driver. It is a compiled driver: the OCI image compiles its C extension
against `libpq` during the build, so `pg_config` (from `libpq-devel`) is required at build time and `libpq` at
runtime.

A plain URL without an explicit driver (`postgresql://` or `postgres://`) is resolved to this driver
automatically:

```
postgresql://usuario:contraseña@servidor:puerto/database

postgresql+psycopg://cacao:cacao@localhost:5432/cacao
```

### MySQL :simple-mysql::

Examples:

```
mysql+pymysql://ususario:contraseña@servidor:puerto/database

mysql+pymysql://cacao:cacao@localhost:3306/cacao
```

!!! note

    The `pymysql` driver requieres the `pyca/cryptography` library to be available to connect to the database server, the required libraries
    are incluyed by default in the OCI image, most of the time the `pip` with install the `cryptography` package apropiate for your
    system you can check the [installation documentarion](https://cryptography.io/en/latest/installation/) for a list of all supported
    platforms.

### SQLite :simple-sqlite::

!!! warning

    Never uses SQLIte in continer based deplyment since SQLite files are stored in the container file system and always the
    container file system is ephemeral and all the data stored in it will destroyed in the next deployment.

```
sqlite://cacaoaccounting.db
```
