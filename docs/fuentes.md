Para instalar Cacao Accounting desde las fuentes se pueden seguir los siguientes pasos: 

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

## Uso de un proxy inverso

Cacao Accounting utiliza [waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/index.html) como servidor WSGI por defecto, las razones por la que se seleccion
como servidor Waitress son:

 - Es una implementación en 100% Python
 - Funciona tanto en Windows como en Linux
 - Presenta un desempeño aceptable

Si bien no se recomienda exponer al servidor WSGI a la Internet, este articulo en ingles explica con bastante detalle porque no se debe exponer un servidor WSGI a la internet: https://rushter.com/blog/gunicorn-and-low-and-slow-attacks/

### Utilizando NGINX como servidor proxy

NGINX es un popular servidor web de código abierto que suele utilizarse como servidor proxy.

#### Ubuntu 

Para utilizar NGINX como proxy inverso en Ubuntu utilizar:

```
sudo apt update
sudo apt install nginx
sudo ufw allow 'Nginx HTTPS'
```

Debe crear el archivo de configuración en:

```
sudo vi /etc/nginx/sites-available/cacao
```

Y agregue el siguiente contenido:

```
server {
    listen 8443;
    server_name cacao;

location / {
  include proxy_params;
  proxy_set_header Host $host;
  proxy_pass proxy_pass http:s//127.0.0.1:8000;
    }
}
```

Ejecute:

```
sudo systemctl restart nginx
```

