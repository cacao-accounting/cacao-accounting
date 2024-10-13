# Configuración de la base de datos.

Cacao Accounting requiere acceso a una base de datos para almacencer los registros que se ingresan
en la aplicacion, la configuración de una linea de conección es la principal opción de configuración
que requiere el sistema.

En general configurar la base de datos para uso en Cacao Accounting requiere:

1. Instalar e iniciar el motor de base de datos seleccionado.
2. Crear un usuario distinto del usuario principal para acceder a la base de datos.
3. Crear una base de datos.
4. Dar acceso al usuario especificado a la base datos que acabamos de crear.

En los ejemplos siguientes recomendamos utilizar nombres y contraseñas distintos a los usados de ejemplo,
en depedencia de su configuración puede que el servidor de base de datos se encuentre en hospedado en una
ubicación distinta a la aplicacion, es necesario tomar medidas de seguridad para evitar que terceros mal
intencionados accedan a la base de datos del sistema, utilizar nombre de usuario y contraseñas seguras es
un paso importante de seguridad, una contraseña es menos segura si utilizas "user" o "admin" como usuario
de la base de datos.

## Bases de datos soportadas.

### SQLite

No se requieren pasos previos para utilizar [SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
como motor de base de datos.

La ruta de acceso configurada debe apuntar al archivo fisico de la base de datos:

```
"sqlite:///path/to/cacaoaccounting.db"
```

Para el desarrollo de Cacao Accounting se utiliza SQLite por defecto, al igual que en la [distribución para escritorio](https://github.com/cacao-accounting/cacao-accounting-desktop).

### MySQL:

Una vez instalado [MySQL](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) puede ejecutar las
siguientes sentencias SQL para crear la base de datos:

```sql
CREATE DATABASE IF NOT EXISTS cacao;
CREATE USER IF NOT EXISTS 'cacao' IDENTIFIED BY 'cacao';
GRANT ALL PRIVILEGES ON cacao.* TO 'cacao';
FLUSH PRIVILEGES;
```

El formato de clave de conexión correcta para utilizar con MySQL es:

```
mysql+pymysql://<username>:<password>@<host>/<dbname>
```

### Postgresql:

Una vez instalado [Postgresql](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) puede
ejecutar las siguientes sentencias SQL para crear la base de datos:

```sql
CREATE DATABASE cacao;
CREATE USER cacao WITH PASSWORD 'cacao';
GRANT ALL PRIVILEGES ON DATABASE cacao TO cacao;
```

Se puede utilizar tanto PG800 (Pure Python Driver) como psycopg2 (Compiled Driver), el formato de
clave de conexión correcta para utilizar con Postgresql es:

PG8000:

```
postgresql+pg8000://user:password@host:port/dbname
```

PSYCOPG2:

```
postgresql+psycopg2://user:password@host:port/dbname
```

Al estar escrito completamente en Python PG8000 puede ser un poco mas lento que psycopg2 el cual utiliza
codigo en para ser eficiente, ambas son opciones validas y el usuario puede seleccionar la opción que mas
se adapta en sus necesidades ya que para utilizar psycopg2 debe tener disponibles la librerias necesarias
para compilar el driver versus postgresql, en cambio pg8000 puede instalarse sin requerir de depencias
adicionales para su instalación y funcionamiento.

Ambos drivers se incluyen en la [imagen OCI](https://quay.io/repository/cacaoaccounting/cacaoaccounting) de
Cacao Accounting.

## Otras bases de datos.

### Mariadb

No se realizan pruebas automaticas versus [MariaDB](https://docs.sqlalchemy.org/en/20/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mariadbconnector) pero Cacao Accounting debería funcionar sin modificaciones utilizando
la url de conexión correcta ya que Cacao Accounting no utiliza funciones especificas de MariaDB para su operación:

```
mariadb+mariadbconnector://<user>:<password>@<host>[:<port>]/<dbname>
```

La [imagen OCI](https://quay.io/repository/cacaoaccounting/cacaoaccounting) de Cacao Accounting no incluye el Driver official de MariaDB
