
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
wget https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/main/cacao_accounting/misc/ejemplos/cacao-accounting.unit
mkdir -p .config/systemd/user/
mv cacao-accounting.unit .config/systemd/user/cacao-accounting.service
```

Edite la plantilla, es importante que el Unit file apunte a la ubicación correcta del ejecutable "cacaoctl"


```
 cat .config/systemd/user/cacao-accounting.service
# Se debe colocar en: /etc/systemd/system/cacao-accounting.service
[Unit]
Description=Cacao Accounting WSGI server
After=syslog.target network.target

[Service]
Type=simple
Restart=always
RestartSec=1
PIDFile=/run/cacaoctl.pid
# Ajustar de acuerdo a la ruta de su entorno virtual
ExecStart=/home/wmoreno/Documentos/repositorios/cacao/venv/bin/cacaoctl serve
# Utilizar esta ruta si la aplicación esta instalada a nivel de sistema
# ExecStart=/usr/bin/cacaoctl serve
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s QUIT $MAINPID

[Install]
WantedBy=multi-user.target

vi .config/systemd/user/cacao-accounting.service
```

La linea importante es indicarle a systemd el archivo executable correcto, en mi caso:

```
ExecStart=/home/ubuntu/cacao-accounting/venv/bin/cacaoctl serve
```


Puede administrar el servicio con:

```
systemctl --user daemon-reload
systemctl --user enable --now cacao-accounting

 systemctl --user status cacao-accounting
● cacao-accounting.service - Cacao Accounting WSGI server
     Loaded: loaded (/home/ubuntu/.config/systemd/user/cacao-accounting.service; enabled; vendor preset: enabled)
     Active: active (running) since Sun 2021-09-26 20:58:14 UTC; 1min 11s ago
   Main PID: 30482 (cacaoctl)
     CGroup: /user.slice/user-1001.slice/user@1001.service/cacao-accounting.service
             └─30482 /home/ubuntu/cacao-accounting/venv/bin/python3 /home/ubuntu/cacao-accounting/venv/bin/cacaoctl serve

Sep 26 20:58:14 erpnext systemd[19701]: Started Cacao Accounting WSGI server.
Sep 26 20:58:15 erpnext cacaoctl[30482]: 2021-09-26 20:58:15.631 | WARNING  | cacao_accounting.config:<module>:122 - No s>
Sep 26 20:58:15 erpnext cacaoctl[30482]: 2021-09-26 20:58:15.631 | WARNING  | cacao_accounting.config:<module>:123 - Util>
Sep 26 20:58:15 erpnext cacaoctl[30482]: 2021-09-26 20:58:15.951 | INFO     | cacao_accounting.server:server:32 - Inician>
Sep 26 20:58:15 erpnext cacaoctl[30482]: 2021-09-26 20:58:15.951 | INFO     | cacao_accounting.database.helpers:verifica_>
Sep 26 20:58:15 erpnext cacaoctl[30482]: 2021-09-26 20:58:15.986 | INFO     | cacao_accounting.database.helpers:verifica_>
Sep 26 20:58:15 erpnext cacaoctl[30482]: 2021-09-26 20:58:15.988 | INFO     | cacao_accounting.server:server:49 - Inician>
```

Puede verificar que el servicio se esta ejecutando localmente con curl:

```
curl 127.0.0.1:8080
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<title>Redirecting...</title>
```

Si desea finalizar el servicio ejecute:

```
systemctl --user stop cacao-accounting
```