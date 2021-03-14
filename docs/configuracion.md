# Configuración de la aplicación:

Siguiendo las recomendaciones en [the twelve factor app](https://12factor.net/config) Cacao Accounting puede leer la configuración desde variables del entorno, la configuración requerida
es:

```bash
$CACAO_ACCOUNTING  # Indica a la aplicación a cargar la configuración desde variables del entorno.
$CACAO_DB          # URI para conectarse a la base de datos.
$CACAO_KEY         # Llave única para una ejecución segura.
```

## Establecer variables del entorno requeridas:

En Linux se puede configurar Cacao Accounting ejecutando:
```bash
# Para configurar Cacao Accounting en Linux ejecutar:
export CACAO_ACCOUNTING=True
export CACAO_DB=DATABASE_CONNECTION_URI
export CACAO_KEY=SECRETKEY
```

En Windows ejecutar:
```powershell
setx CACAO_ACCOUNTING "True"
setx CACAO_DB "DATABASE_CONNECTION_URI"
setx CACAO_KEY "SECRETKEY"
```

En un Dockerfile o en un archivo Docker compose se pueden configurar de la siguiente forma:
```dockerfile
ENV CACAO_ACCOUNTING=True
ENV CACAO_DB=DATABASE_CONNECTION_URI
ENV CACAO_KEY=SECRETKEY
```

## Conexion a la base de datos

Cacao Accounting puede funcionar con SQLite, MySQL, Postgresql y MS SQL Server:

### SQLite:
No se requiere software adicional para trabajar con SQLite, sin embargo no se recomienda para
entornos multi usuarios:

La linea de conección es por ejemplo:

```
sqlite://cacaoaccounting.db
```
### MySQL:

Para funcionar con MySQL asegurece de tener instalado el driver apropiado:

```bash
pip install cryptography pymysql
```

La linea de conección es por ejemplo:

```
mysql+pymysql://ususario:contraseña@servidor:puerto/database

mysql+pymysql://cacao:cacao@localhost:3306/cacao
```

### Postgresql:

Para funcionar con Postgresql asegurece de tener instalado el driver apropiado:

```bash
pip install psycopg2-binary
```

La linea de conección es por ejemplo:

```
postgresql+psycopg2://usuario:contraseña@servidor:puerto/database

postgresql+psycopg2://cacao:cacao@localhost:5432/cacao
```

### MS SQL Server:

Para funcionar con MS SQL Server asegurece de tener instalado el [driver de python](https://pypi.org/project/pyodbc/) apropiado, adicionalmente debe configurar el cliente de [ODBC para su sistema operativo](https://docs.microsoft.com/en-us/sql/connect/python/pyodbc/python-sql-driver-pyodbc?view=sql-server-ver15).

```bash
pip install pyodbc
```

La linea de conección es por ejemplo:

```
mssql+pyodbc://usuario:contraseña@servidor:puerto/database?driver=DRIVER

mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server
```

En el ejemplo anterior se usa la [version 17 del cliente ODBS para SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver15)
