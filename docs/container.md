[![Docker Repository on Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting/status "Docker Repository on Quay")](https://quay.io/repository/cacaoaccounting/cacaoaccounting)

Existe una imagen de contenedor OCI :simple-docker: disponible para ejecutar Cacao Accounting en entornos de contenedores,
la imagen esta alojada en [Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting).

Si va a ejecutar Cacao Accounting en un servidor dedicado y no desea utilizar contenedores puede instalar el paquete directamente desde [pypi](pypi.md)

## Instalar podman para la administración de contenedores.

Recomendamos `podman` para ejecutar Cacao Accounting utilizando contenedores. Podman le
permite ejecutar contenedores en `pods`, un pod es un conjunto de contenedores que se ejecutan
en conjunto con lo cual podemos facilitar la administración de aplicaciones que requieren mas de un
contenedor para operar, para instalar podman debemos contar con acceso a instalar paquetes en su
sistema operativo:

=== ":simple-ubuntu: Ubuntu LTS"

    ``` bash
    sudo apt install -y podman

    ```

=== ":simple-fedora: Fedora, Rocky Linux, Alma Linux, RHEL."

    ```bash
    sudo dnf -y install podman
    ```

### Cockpit

Cockpit es una interfaz web para la administración de servidores que ofrece un interfaz grafica
para la administración de Contenedores con Podman:

=== ":simple-ubuntu: Ubuntu LTS"

    ``` bash
    sudo apt -y install cockpit-podman cockpit
    sudo systemctl enable --now cockpit.socket
    ```

=== ":simple-fedora: Fedora, Rocky Linux, Alma Linux, RHEL."

    ```bash
    sudo dnf -y install cockpit-podman cockpit
    sudo systemctl enable --now cockpit.socket
    ```
    
La siguiente imagen muestra un servidor Fedora Server ejecutando dos instancias de la imagen OCI de
Cacao Accounting, una de ellas utilizando MySQL la otra utilizando PostgreSQL, en ambos casos se
utiliza Caddy como servidor proxy:

![OCI Image](https://bmogroup.solutions/imgs/Podman-containers-wmoreno-fedora.png)

# Ejecutar Cacao Accounting utilizando la imagen OCI.

Puede ejecutar Cacao Accounting utilizando los siguientes ejemplos.

## Crea un archivo de configuración de :simple-caddy: [Caddy Server](https://caddyserver.com/).

En el directorio en el que desea iniciar el contenedor cree un archivo de configuración para Caddy Server:

```bash
touch Caddyfile
```

Puede utilizar la siguiente configuración básica para configurar `Caddy` como servidor web:

```
:80 {
	reverse_proxy localhost:8080
}
```

## Ejecutar un `pod` para ejecutar Cacao Accounting.

=== ":simple-mysql: MySQL"

    ``` bash
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
    Puede decargar el script, editarlo de acuerdo a sus necesidades y ejecutar los contenedores
    ejecutando lo siguiente:

    ```bash
    $ pwd
    /home/wmoreno/Documentos/code/container/mysql
    $ curl -O https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/refs/heads/main/docs/oci_files/Caddyfile
    $ curl -O https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/refs/heads/main/docs/oci_files/mysql.sh
    $ ls
    mysql.sh  Caddyfile
    $ bash mysql.sh
    ```

=== ":simple-postgresql: Postgresql"

    ```bash
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

    Puede decargar el script, editarlo de acuerdo a sus necesidades y ejecutar los contenedores
    ejecutando lo siguiente:

    ```bash
    $ pwd
    /home/wmoreno/Documentos/code/container/psql
    $ curl -O https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/refs/heads/main/docs/oci_files/Caddyfile
    $ curl -O https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/refs/heads/main/docs/oci_files/psql.sh
    $ ls
    psql.sh  Caddyfile
    $ bash psql.sh
    ```

### Permitir que el contenedor acceda al archivo de configuración de :simple-caddy: `Caddy`.

Si esta ejecutando Cacao Accounting en Fedora, Rocky Linux, Alma Linux o similares con SELinux activo la opción `:z`
evita que SELinux bloquee el acceso al archivo de configuración, si utiliza otro host intente usar la opción `:ro`.

Lectura recomendada: https://www.redhat.com/en/blog/container-permission-denied-errors

### Permitir a podman acceder a puertos restringidos.

Por defecto al ejecutar `podman` como un usuario sin privilegios de root el acceso a los puertos inferiones al 1024 no
se pueden mapear sin permisos de `root`.

Lectura recomendada: https://access.redhat.com/solutions/7044059

Otra opción es utilizar la herramienta `redir` para redireccionar el trafico de los puertos registringidos a los puertos
que se mapearon en el `pod`

```
sudo dnf install redir
sudo redir -n -s :80 127.0.0.1:8080
```

Finalmente si no va a ejecutar software adicional en el servidor puede ejecutar el `pod` como `root`, sin embargo una de las ventajas de usar `podman` es no tener que requerir permisos elevados para ejecutar contenedores, sin embargo si el servidor va a estar dedicado unicamente a servir Cacao Accounting la instalación se puede realizar directamente desde el
paquete publicado en [Pypi](pypi.md)