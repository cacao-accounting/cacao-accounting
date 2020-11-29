# Instalacion

Existen varias formas de desplegar Cacao Accounting, basicamente Cacao Accounting es una
aplicación WEB creada utilizando [flask](flask.palletsprojects.com) como base, las aplicaciones
desarrolladas con flask son compatibles con el estandar [wsgi](flask.palletsprojects.com) por lo
que para instalar Cacao Accounting se requiere:

1. Un servidor WSGI, [gunicorn]() y [waitress]() son las opciones recomendadas.
2. Un servidor web, [nginx]() es la opción recomendada.
3. Un servidor de bases de datos, [postgresql](https://www.postgresql.org/), 
[MySQL](https://www.mysql.com/), [MariaDB](https://mariadb.org/) y [SQLite](https://www.sqlite.org/index.html) son oficialmente soportadas.

## Entorno Virtual de Python

Para instalar Cacao Accounting desde las fuentes requiere [git](https://git-scm.com/), [yarn](https://yarnpkg.com/lang/en/) y [python](https://www.python.org/downloads/). 

```bash
git clone https://github.com/cacao-accounting/cacao-accounting.git
cd cacao-accounting
python3 -m venv venv
# Windows:
.\venv\Scripts\activate.bat
# Linux y MAC: 
source venv/bin/activate 
python -m pip install -r requirements.txt
python setup.py install
yarn
```

Se puede verificar si la instalación fue correcta ejecutando:

```bash
cacaoctl
Usage: python -m flask [OPTIONS] COMMAND [ARGS]...

  Interfaz de linea de comandos para la administración de        
  Cacao Accounting.

Options:
  --version  Show the flask version
  --help     Show this message and exit.

Commands:
  cleandb  Elimina la base de datos, solo disponible para...     
  db       Perform database migrations.
  initdb   Crea el esquema de la base de datos.
  routes   Show the routes for the app.
  run      Run a development server.
  serve    Inicio la aplicacion con waitress como servidor...    
  shell    Run a shell in the app context.
```

Existe una entrada en [pypi](https://pypi.org/project/cacao-accounting/) para el
proyecto donde periodicamente se publican los avances del proyecto.

Cacao Accounting es software en desarrollo no apto aún para su uso en producción.

## Docker

Existe una imagen de imagen de contenedor disponible para ejecutar la aplicación en:

```bash
https://quay.io/repository/cacaoaccounting/cacaoaccounting
```

En este ejemplo usaremos podman pero los comandos son equivalentes usando moby (docker):

```bash
podman pull quay.io/cacaoaccounting/cacaoaccounting

podman images
REPOSITORY                                 TAG     IMAGE ID      CREATED       SIZE
docker.io/cacaoaccounting/cacaoaccounting  latest  a25d0896a2ab  22 hours ago  193 MB

podman run -name cacao -d -p 8080:8080 cacaoaccounting/cacaoaccountin

podman ps
CONTAINER ID  IMAGE                                             COMMAND               CREATED         STATUS             PORTS                   NAMES
e70999f0cd83  docker.io/cacaoaccounting/cacaoaccounting:latest  /app/entrypoint.s...  28 seconds ago  Up 28 seconds ago  0.0.0.0:8070->8080/tcp  cacao
```

Hay una plantilla de [docker-compose](https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/development/docker-compose.yml)
disponible para apoyar al despliegue de la aplicacion con
contenedores.

## Systemd


En sistemas Linux systemd se ha vuelto la implementación predominante para
el arranque del sistema operativo, systemd utiliza archivos .unit para describir
los procesos a iniciar en el arranque del sistema operativa.

Para su conveniencia proveemos una plantilla de [archivo .unit](https://github.com/cacao-accounting/cacao-accounting/blob/development/cacao_accounting/misc/ejemplos/cacao-accounting.unit)
para utilizarla en el despliegue de Cacao Accounting.

El archivo .unit se debe colocar en:

```bash
/etc/systemd/system/cacao-accounting.service
```

Es importante editar las rutas al ejecutable cacaoctl, al aplicación se puede
administrar con:

```bash
systemctl daemon-reload
systemctl enable cacao-accounting.service --now
```

### Usando el unit file sin permisos de root

Si no tiene acceso de administrador al sistema aun puede utilizar systemd para
administrar Cacoa Accounting, debe colocar en archivo .unit en:

```
~/.config/systemd/user/cacao-accounting.service
```

Puede administrar el servicio con:

```
systemctl --user daemon-reload
systemctl --user start cacao-accounting

systemctl --user status cacao-accounting
● cacao-accounting.service - Cacao Accounting WSGI server
     Loaded: loaded (/home/wmoreno/.config/systemd/user/cacao-accounting.service; disabled; vendor preset: disabled)
     Active: active (running) since Sun 2020-11-01 15:12:52 CST; 5s ago
   Main PID: 5471 (cacaoctl)
      Tasks: 5 (limit: 3991)
     Memory: 44.2M
        CPU: 656ms
     CGroup: /user.slice/user-1000.slice/user@1000.service/cacao-accounting.service
             └─5471 /home/wmoreno/Documentos/repositorios/cacao/venv/bin/python /home/wmoreno/Documentos/repositorios/cacao/venv/bin/cacaoctl serve

nov 01 15:12:52 thanos systemd[2002]: Started Cacao Accounting WSGI server.
nov 01 15:12:53 thanos cacaoctl[5471]: 2020-11-01 15:12:53.798 | INFO     | cacao_accounting.__main__:run:34 - Iniciando servidor WSGI en puerto 8080
nov 01 15:12:53 thanos cacaoctl[5471]: 2020-11-01T15:12:53.798290-0600 INFO Iniciando servidor WSGI en puerto 8080

systemctl --user stop cacao-accounting
```

## Configurar un servidor web

Cacao Accounting utiliza [waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/)
como servidor WSGI, no es recomendable exponer el servidor de aplicaciones directamente a la WEB,
waitress puede ser utilizado en redes privadas con pocos usuarios, para servir a un gran número de
usuarios o utilizar en un servidor público se recomienda utilizar [nginx](https://nginx.org/en/)
como proxy y para servir contenido estatico a los usuarios.
