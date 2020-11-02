

Docker
======

Existe una imagen de imagen de contenedor disponible para ejecutar la aplicación en:

https://hub.docker.com/r/cacaoaccounting/cacaoaccounting

En este ejemplo usaremos podman pero los comandos son equivalentes usando moby (docker):

podman pull cacaoaccounting/cacaoaccounting

podman images
REPOSITORY                                 TAG     IMAGE ID      CREATED       SIZE
docker.io/cacaoaccounting/cacaoaccounting  latest  a25d0896a2ab  22 hours ago  193 MB


podman run -name cacao -d -p 8080:8080 cacaoaccounting/cacaoaccountin

podman ps
CONTAINER ID  IMAGE                                             COMMAND               CREATED         STATUS             PORTS                   NAMES
e70999f0cd83  docker.io/cacaoaccounting/cacaoaccounting:latest  /app/entrypoint.s...  28 seconds ago  Up 28 seconds ago  0.0.0.0:8070->8080/tcp  cacao

Systemd
=======

En sistemmas Linux systemd se ha vuelto la implementación predominante para
el arranque del sistema, systemd utiliza archivos .unit para describir los 
procesos a iniciar en el arranque del sistema operativa.

Para su conveniencia proveemos una plantilla de archivo .unit para utilizarla
en el despliegue de Cacao Accounting.

El archivo .unit se debe colocar en:

/etc/systemd/system/cacao-accounting.service

Es importante editar las rutas al ejecutable cacaoctl, al aplicación se puede
administrar con:

systemctl daemon-reload
systemctl enable cacao-accounting.service --now


Usando el unit file sin permisos de root
----------------------------------------

Si no tiene acceso de administrador al sistema aun puede utilizar systemd para
administrar Cacoa Accounting, debe colocar en archivo .unit en:

~/.config/systemd/user/cacao-accounting.service

Puede administrar el servicio con:

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
