# Configuración de la base de datos.

Cacao Accounting requiere acceso a una base de datos para almacencer los registros que se ingresan en la 
aplicacion, la configuración de una linea de conección en la principal opción de configuración que requiere
el sistema.

En general configurar la base de datos para uso en Cacao Accounting requiere:

1. Instalar e iniciar el motor de base de datos seleccionado.
2. Crear un usuario distinto del usuario principal para acceder a la base de datos.
3. Crear una base de datos.
4. Dar acceso al usuario especificado a la base datos que acabamos de crear.

En los ejemplos siguientes recomendamos utilizar nombres y contraseñas distintos a los usados de ejemplo.

## SQLite

No se requiere pasos previos para utilizar SQLite como motor de base de datos.

## MySQL:

Una vez instalado MySQL puede ejecutar las siguientes sentencias SQL para crear la base de datos:

```sql
CREATE DATABASE IF NOT EXISTS cacao;
CREATE USER IF NOT EXISTS 'cacao' IDENTIFIED BY 'cacao';
GRANT ALL PRIVILEGES ON cacao.* TO 'cacao';
FLUSH PRIVILEGES;
```

## Postgresql:

Una vez instalado Postgresql puede ejeutar las siguientes sentencias SQL para crear la base de datos:

```sql
CREATE DATABASE cacao;
CREATE USER cacao WITH PASSWORD 'cacao';
GRANT ALL PRIVILEGES ON DATABASE cacao TO cacao;
```

## MS SQL Server

Una vez instalado MS SQL Server puede ejecitar las siguientes setencias SQL para crear la base de datos:

```sql
USE master;
GO
CREATE DATABASE cacao;
GO
CREATE LOGIN cacao WITH PASSWORD = 'cacao';
GO
CREATE USER cacaouser login cacao;
GO
USE cacao;
GO
GRANT ALL ON dbo.cacao TO cacaouser;
GO  
```
