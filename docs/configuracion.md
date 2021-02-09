# Configuración de la aplicación:

Siguienda las recomendaciones en [the twelve factor app](https://12factor.net/config) Cacao Accounting puede leer la configuración desde variables del entorno:

## Establecer varaibles del entorno requeridas:

En Linux se puede configurar Cacao Accounting ejecutando:
```bash
# Para configurar Cacao Accounting en Linux ejecutar:
export CACAO_ACCOUNTING=True
export CACAO_DB=DATABASE_CONNECTION_URI
# Ejemplos
# SQLITE = "sqlite:///cacaoaccounting.db"
# MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
# POSTGRESQL = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"
# MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"
```

En Windows ejecutar:
```powershell
setx CACAO_ACCOUNTING "True"
setx CACAO_DB "DATABASE_CONNECTION_URI"
```

En un Dockerfile o en un archivo Docker compose se pueden configurar de la siguiente forma:
```dockerfile
ENV CACAO_ACCOUNTING=True
ENV CACAO_DB=DATABASE_CONNECTION_URI
```