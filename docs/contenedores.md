[![Docker Repository on Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting/status "Docker Repository on Quay")](https://quay.io/repository/cacaoaccounting/cacaoaccounting)

Existe una imagen de contenedor OCI disponible para ejecutar Cacao Accounting en entornos de contenedores en [https://quay.io/repository/cacaoaccounting/cacaoaccounting](https://quay.io/repository/cacaoaccounting/cacaoaccounting).

## Instalar podman para la administración de contenedores.

Recomendamos ```podman``` para ejecutar Cacao Accounting utilizando contenedores. Podman 
permite ejecutar contenedores en ```pods```, un pod es un conjunto de contenedores que se ejecutan
en conjunto con lo cual podemos facilitar la administración de aplicaciones que requieren mas de un
contenedor para operar, para instalar podman debemos contar con acceso a instalar paquetes en su
sistema operativo:

```bash
# Fedora, CentOS ...
dnf -y install podman

# Debian, Ubuntu ...
apt install -y podman

# OpenSUSE
sudo zypper in podman
```

Una vez podman esta instalado podemos ejecutar Cacao Accounting en un pod utilizando uno de
los ejemplos siguientes.

## Utilizando MySQL como motor de base de datos.

```bash
# Creamos un pod:
podman pod create --name cacao-mysql -p 8080:8080 -p 3306:3306 -p 9980:80 -p 9443:443

# Creamos un volumen para almacenar la base de datos fuera del contenedor:
podman volume create cacao-mysql-backup

# Creamos el contenedor para la base de datos:
podman run --pod cacao-mysql --rm --name cacaodbmysql \
    --volume cacao-mysql-backup:/var/lib/mysql  \
    -e MYSQL_ROOT_PASSWORD=cacaodb \
    -e MYSQL_DATABASE=cacaodb \
    -e MYSQL_USER=cacaodb \
    -e MYSQL_PASSWORD=cacaodb \
    -d mysql:8

# Creamos el contenedor de la aplicación:
podman run --pod cacao-mysql --rm --init --name cacao1 \
    -e CACAO_ACCOUNTING=True \
    -e CACAO_KEY=nsjksldknsdlkdsljdn \
    -e CACAO_DB=mysql+pymysql://cacaodb:cacaodb@localhost:3306/cacaodb \
    -e CACAO_USER=cacaouser \ # Si no es especifica utiliza cacao por defecto
    -e CACAO_PWD=cacappwd \ # Si no es especifica utiliza cacao por defecto
    -d quay.io/cacaoaccounting/cacaoaccounting
``` 

## Utilizando Postgresql como motor de base de datos.

```bash
# Creamos un pod:
podman pod create --name cacao-psql -p 8080:8080 -p 5432:5432 -p 8980:80 -p 8443:443

# Creamos un volumen para almacenar la base de datos fuera del contenedor:
podman volume create cacao-postgresql-backup

# Creamos el contenedor para la base de datos:
podman run --pod cacao-psql --rm --name cacaodbpg \
    --volume cacao-postgresql-backup:/var/lib/postgresql/data \
    -e POSTGRES_DB=cacaodb \
    -e POSTGRES_USER=cacaodb \
    -e POSTGRES_PASSWORD=cacaodb \
    -d postgres:13

# Creamos el contenedor de la aplicación:
podman run --pod cacao-psql --rm --init --name cacao2 \
    -e CACAO_ACCOUNTING=True \
    -e CACAO_KEY=nsjksldknsdlkdsljdn \
    -e CACAO_DB=postgresql+pg8000://cacaodb:cacaodb@localhost:5432/cacaodb \
    -e CACAO_USER=cacaouser \ # Si no es especifica utiliza cacao por defecto
    -e CACAO_PWD=cacappwd \ # Si no es especifica utiliza cacao por defecto
    -d quay.io/cacaoaccounting/cacaoaccounting

```

Luego de un momento la aplicación debera estar disponible en: http://localhost:8080, en caso
que el contenedor no se ejecute puede favor de reportar el error [aquí](https://github.com/cacao-accounting/cacao-accounting/issues).

```bash
Cacao Accounting es software en desarrollo no apto para uso en producción.
```

Para administrar el pod podemos ejecutar:

```bash
podman pod stop 
podman pod start 
```

Esta configuración es adecuada para uso en una red local, no se recomiendo el exponer
directamente el servidor WSGI a Internet, para eso es mejor configurar nginx como proxy
inverso.
