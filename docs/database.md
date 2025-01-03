# Manual database setup.

Manual instructions to create a database for your Cacao Accounting setup.

!!! warning

    Always use custom password and users to setup your database credentials, generic users and password in this guide
    do not must be used in production enviroments.

!!! info

    Container based deployment do not requieres manual database setup because OCI images for mayor database services includes
    apropiate scritps to create the database at the first run.

## Supported databases.

This database systems are fully tested as part of the Cacao Accounting Development.

### SQLite

There is not aditional steps to use [SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)

Example connection string:

```
sqlite:///path/to/cacaoaccounting.db
```

!!! warning

    Never uses SQLIte in continer based deplyment since SQLite files are stored in the container file system and always the
    container file system is ephemeral and all the data stored in it will destroyed in the next deployment.

!!! info

    SQLite is the database engine that powers the [desktop version](https://github.com/cacao-accounting/cacao-accounting-desktop)
    of Cacao Accounting.

### Postgresql:

Once installed [Postgresql](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) you can setup a
new database with:

```sql
CREATE DATABASE cacaoaccountingdatabase;
CREATE USER cacaosystemuser WITH PASSWORD 'cacao123+';
GRANT ALL PRIVILEGES ON DATABASE cacaoaccountingdatabase TO cacaosystemuser;
```

You can use the PG800 (Pure Python Driver) and psycopg2 (Compiled Driver), those are the examples connection strings:

PG8000:

```
postgresql+pg8000://user:password@host:port/dbname
```

PSYCOPG2:

```
postgresql+psycopg2://user:password@host:port/dbname
```

### MySQL:

Once installed [MySQL](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) you can setup a database for your Cacao Accounting
setup with

```sql
CREATE DATABASE IF NOT EXISTS cacaoaccounting;
CREATE USER IF NOT EXISTS 'cacaodbuser' IDENTIFIED BY 'cacaopswd';
GRANT ALL PRIVILEGES ON cacaoaccounting.* TO 'cacaodbuser';
FLUSH PRIVILEGES;
```

MySQL Connection string example:

```
mysql+pymysql://<username>:<password>@<host>/<dbname>
```

!!! info

    Cacao Accounting is tested with MySQL version 8.
