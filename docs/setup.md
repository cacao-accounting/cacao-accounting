# Instalacion

Existen varias formas para instalar Cacao Accounting, basicamente Cacao Accounting es una app Web
creada utilizando [flask](flask.palletsprojects.com) como base, las aplicaciones desarrolladas con
flask son compatibles con el estandar [wsgi](flask.palletsprojects.com) por lo que para instalar
Cacao Accounting se requiere:

1. Un servidor WSGI, [gunicorn]() y [waitress]() son las opciones recomendadas, waitress funciona
   en servidores Windows y Linux es la opción utilizada por defecto, la imagen de contenedor de
   Cacao Accounting tambíen utiliza waitress como servidor WSGI.

2. Un servidor web, [nginx]() es la opción recomendada, no es recomendable exponer el servidor WSGI
   directamente a la Internet, es recomendable utilizar NGINX para tareas como servir el contenido
   contenido estatico y dejar al servidor WSGI para administrar la logica de la aplicación.

3. Un servidor de bases de datos, los motores de base de datos soportados son:
   [SQLite](https://www.sqlite.org/index.html),
   [Postgresql](https://www.postgresql.org/),
   [MySQL](https://www.mysql.com/),
   [MS SQL Server](https://www.microsoft.com/es-mx/sql-server/sql-server-downloads).
