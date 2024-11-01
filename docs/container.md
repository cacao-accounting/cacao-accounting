[![Docker Repository on Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting/status "Docker Repository on Quay")](https://quay.io/repository/cacaoaccounting/cacaoaccounting)

Existe una imagen de contenedor OCI disponible para ejecutar Cacao Accounting en entornos de contenedores,
la imagen esta alojada en [Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting).

## Instalar podman para la administración de contenedores.

Recomendamos `podman` para ejecutar Cacao Accounting utilizando contenedores. Podman
permite ejecutar contenedores en `pods`, un pod es un conjunto de contenedores que se ejecutan
en conjunto con lo cual podemos facilitar la administración de aplicaciones que requieren mas de un
contenedor para operar, para instalar podman debemos contar con acceso a instalar paquetes en su
sistema operativo:

```bash
# Fedora, Rocky Linux, Alma Linux, RHEL ...
sudo dnf -y install podman

# Debian, Ubuntu ...
sudo apt install -y podman
```

### Cockpit

Cockpit es una interfaz web para la administración de servidores que ofrece un interfaz grafica
para la administración de Contenedores con Podman:

```bash
# Fedora, Rocky Linux, Alma Linux, RHEL ...
sudo dnf install cockpit-podman cockpit
sudo systemctl enable --now cockpit.socket

# Debian, Ubuntu ...
sudo apt install cockpit-podman cockpit
sudo systemctl enable --now cockpit.socket
```

Una vez `podman` esta instalado podemos ejecutar Cacao Accounting en un pod utilizando uno de
los ejemplos siguientes.

# Ejecutar Cacao Accounting utilizando la imagen OCI.

## Crea un archivo de configuración de [Caddy Server](https://caddyserver.com/).

En el directorio en el que desea iniciar el contenedor cree un archivo de configuración para Caddy Server:

```bash
touch Caddyfile
```

Puede utilizar la siguiente configuración básica para configurar `Caddy` como servidor web:

```
localhost {
	reverse_proxy localhost:8080
}
```

## Utilizando MySQL como motor de base de datos.

Puede utilizar el siguiente conjunto de comandos para iniciar un pod para Cacao Accounting
que utilice MySQL como servidor de base de datos y Caddy como servidor web.

```bash
#!/bin/bash
# Creamos un pod:
podman pod create --name cacao-mysql -p 9980:80 -p 9443:443 -p 9443:443/udp

# Creamos un volumen para almacenar la base de datos fuera del contenedor:
podman volume create cacao-mysql-backup

# Creamos el contenedor para la base de datos:
podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-db \
    --volume cacao-mysql-backup:/var/lib/mysql  \
    -e MYSQL_ROOT_PASSWORD=cacaodb \
    -e MYSQL_DATABASE=cacaodb \
    -e MYSQL_USER=cacaodb \
    -e MYSQL_PASSWORD=cacaodb \
    -d docker.io/library/mysql:8

# Creamos el contenedor para el servidor web:
podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-server \
    -v ./Caddyfile:/etc/caddy/Caddyfile:z \
    -v caddy_data:/data \
    -v caddy_config:/config \
    -d docker.io/library/caddy:alpine

# Creamos el contenedor de la aplicación:
podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-app \
    -e CACAO_KEY=nsjksldknsdlkd532445yryrgfhdyyreysljdn \
    -e CACAO_DB=mysql+pymysql://cacaodb:cacaodb@localhost:3306/cacaodb \
    -e CACAO_USER=cacaouser \
    -e CACAO_PWD=cacappwd \
    -d quay.io/cacaoaccounting/cacaoaccounting
```

Para que el script funcione debe estar guardado en el mismo directorio que el archivo de configuración
de Caddy:

```bash
$ pwd
/home/wmoreno/Documentos/code/container/mysql
$ ls
mysql.sh  Caddyfile
```

Edite el contenido del script de acuerdo a sus nececidades y ejecutelo con:

```bash
$ bash mysql.sh
```

## Utilizando Postgresql como motor de base de datos.

Puede utilizar el siguiente conjunto de comandos para iniciar un pod para Cacao Accounting
que utilice Postgresql como servidor de base de datos y Caddy como servidor web.

```bash
#!/bin/bash
# Creamos un pod:
podman pod create --name cacao-psql -p 9981:80 -p 9444:443 -p 9444:443/udp

# Creamos un volumen para almacenar la base de datos fuera del contenedor:
podman volume create cacao-postgresql-backup

# Creamos el contenedor para la base de datos:
podman run --pod cacao-psql --rm --name cacao-psql-db \
    --volume cacao-postgresql-backup:/var/lib/postgresql/data \
    -e POSTGRES_DB=cacaodb \
    -e POSTGRES_USER=cacaodb \
    -e POSTGRES_PASSWORD=cacaodb \
    -d docker.io/library/postgres:17-alpine

# Creamos el contenedor para el servidor web:
podman run --pod cacao-psql --rm --replace --init --name cacao-psql-server \
    -v ./Caddyfile:/etc/caddy/Caddyfile:z \
    -v caddy_data:/data \
    -v caddy_config:/config \
    -d docker.io/library/caddy:alpine

# Creamos el contenedor de la aplicación:
podman run --pod cacao-psql --rm --init --name cacao-psql-app \
    -e CACAO_KEY=nsjksldknsdlkdsljasfsadggfhhhhf5325364dn \
    -e CACAO_DB=postgresql+pg8000://cacaodb:cacaodb@localhost:5432/cacaodb \
    -e CACAO_USER=cacaouser \
    -e CACAO_PWD=cacappwd \
    -d quay.io/cacaoaccounting/cacaoaccounting
```

Para que el script funcione debe estar guardado en el mismo directorio que el archivo de configuración
de `Caddy`:

```bash
$ pwd
/home/wmoreno/Documentos/code/container/psql
$ ls
psql.sh  Caddyfile
```

#### Permitir que el contenedor acceda al archivo de configuración de `Caddy`.

Si esta ejecutando Cacao Accounting en Fedora, Rocky Linux, Alma Linux o similares con SELinux activo la opción `:z`
evita que SELinux bloquee el acceso al archivo de configuración, si utiliza otro host intente usar la opción `:ro`

Edite el contenido del script de acuerdo a sus nececidades y ejecutelo con:

```bash
$ bash psql.sh
```

Lectura recomendada: https://www.redhat.com/en/blog/container-permission-denied-errors
