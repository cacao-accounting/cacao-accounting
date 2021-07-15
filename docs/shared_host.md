# Instalación de Cacao Accounting en servicios de Hospedaje Compartido.

Es posible instalar Cacao Accounting en servicios de hospedaje compartido, siempre que el 
servicio cumpla los siguientes requisitos:

1. Python3, al menos [Python 3.7](https://www.python.org/downloads/release/python-370/)
1. [Apache MOD CGI](https://httpd.apache.org/docs/current/mod/mod_cgi.html)
1. Acceso ssh al servidor.

Normalmente la aplicación se instala en un sub dominio dejando el dominio principal para el sitio web
principal de la empresa.

## Iniciar sesión en el servidor virtual y crear un entorno virtual.

```bash
# Verificamos que estamos en la raiz del sub dominio.
 $pwd
/home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html

# Creamos un directorio cgi-bin
$mkdir cgi-bin
$cd cgi-bin

# Verificamos la versión de Python.
$python3 --version
Python 3.7.9

# Creamos y ejecutamos un entorno virtual de Python.
$python3 -m venv venv
$source venv/bin/activate

# Clonamos el repositorio del proyecto.
$git clone https://github.com/cacao-accounting/cacao-accounting.git
$cd cacao-accounting/
$python3 -m pip install -r requirements.txt
$python3 -m pip install .

# Normalmente los servicios de shared host ofrecen MySQL, necesitamos estas librerias.
$python3 -m pip install cryptography pymysql

# Configuramos la aplicacion
# Utilice una clave segura.
$export CACAO_KEY="dW=BMIPE&@M,M6s*qaRu"
# Conexión a la base de datos.
$export CACAO_DB=mysql+pymysql://usuario:contraseña@localhost:3306/database
# Usuario y Contraseña:
$export CACAO_USER=usuario
$export CACAO_PWD=contraseña

# Verificamos que la instalación es funcional.
$cacaoctl version
0.0.1.dev20210715

# Iniciamos la base de datos.
$cacaoctl initdb
```

A este punto la aplicación esta instalada y la base de datos inicializada.

## Configuramos archivo cacao.cgi

``` bash
$pwd
/home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html/cgi-bin
$ls
cacao-accounting  venv

$vi cacao.cgi
```

```
#!/home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html/venv/bin/python
from wsgiref.handlers import CGIHandler

from cacao import app
```


## Crear archivo cacao.py

```bash
$cacao-accounting  venv

vi cacao.cgi
```

Configuramos la aplicación cgi:

```
import os
import sys
sys.path.insert(0, '/home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html/cgi-bin/venv/lib/python3.7/site-packages')
sys.path.insert(1, '/home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html/cgi-bin/venv/lib64/python3.7/site-packages')

from cacao_accounting import create_app
from cacao_accounting.config import configuracion

app = create_app(configuracion)
```

## Configurar archivo .htaccess

```bash
$pwd
$/home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html

$vi .htaccess
```

Y configuramos la aplicacion:

```
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^(.*)$ /home/u350-nud6xqxi8gnk/www/cacao.bmogroup.solutions/public_html/cgi-bin/cacao.cgi/$1 [L]
```
Los persimos de ambos archivos deber 755

```
chmod 755 cacao.cgi
chmod 755 .htaccess
```

La estructura final del archivo queda de la siguiente manera:

```
public_html
  - .htaccess
  - cgi-bin
    - cacao.cgi 
    - cacao.py
    - cacao-accounting
    - venv  
```
