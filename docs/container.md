# Setup Cacao Accounting from the OCI image.

[![Docker Repository on Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting/status "Docker Repository on Quay")](https://quay.io/repository/cacaoaccounting/cacaoaccounting)

A [OCI image](https://github.com/opencontainers/image-spec) :simple-docker: is available is hosted in [Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting) :simple-redhat: for executing Cacao Accounting in containers based deployments.

!!! note

    If you do not need a container based deployment you can install Cacao Accounting as a Python package
    from the package hosted at [pypi](py_pypi.md) :material-language-python:.

!!! info

    This guide uses `podman` and `cockpit` as reference, but you can use any tool you prefer to run
    the Cacao Accounting OCI image like [Docker CE](https://docs.docker.com/engine/install/).

!!! info

    There is a [Desktop Version](https://github.com/cacao-accounting/cacao-accounting-desktop) :desktop: of Cacao Accounting available.

## Install the `podman` tool.

[`Podman`](https://podman.io/) :simple-podman: is a powerful and versatile container engine that provides a robust alternative to Docker. [`Cockpit`](https://cockpit-project.org/) is a server management tool that is available as a Linux plugin. It allows users to manage Linux systems using a web-based graphical interface and dashboard.

With `podman` and `cockpit` you can create `pods` to group many containers in a single unit.

### Install the podman tool.

=== ":simple-debian: Debian based operative systems."

    ``` bash
    sudo apt install -y podman

    ```

=== ":simple-fedora: Fedora based operative systems."

    ```bash
    sudo dnf -y install podman
    ```

### Install the cockpit manager plugin.

=== ":simple-debian: Debian based operative systems."

    ``` bash
    sudo apt -y install cockpit-podman cockpit
    sudo systemctl enable --now cockpit.socket
    ```

=== ":simple-fedora: Fedora based operative systems."

    ```bash
    sudo dnf -y install cockpit-podman cockpit
    sudo systemctl enable --now cockpit.socket
    ```

The next screenshot shows a Fedora Server running multiple Cacao Accounting instances running in pods:

![OCI Image](https://bmogroup.solutions/imgs/Podman-containers-wmoreno-fedora.png)

# Execute the Cacao Accounting OCI imange.

To execute de Cacao Accounting OCI image you need to setup the following services:

1. The Cacao Accounting wsgi app.
2. A database service, you can use Postgresql or MySQL.
3. A web server to handle users request, you can use Nginx, Caddy or any web server with proxy functionality.
4. A optional Redis service for caching.

!!! info

    This guide uses `caddy` because its simple configuration but Nginx is a another well documented web
    server option.

## Create a [Caddy](https://caddyserver.com/) :simple-caddy: web server configuration file.

Similar to working with `podman-compose` it is recommended to create a directory to store the configuration files needed to
execute the services that a Cacao Accounting instance requires:

```bash
mkdir cacao-accounting-services
cd cacao-accounting-services
touch Caddyfile
```

Copy this base configuration to the Caddyfile:

```
:80 {
	reverse_proxy localhost:8080
}
```

!!! note

    Additional details to use the Caddy web server as a proxy server is available in the [Caddy website](https://caddyserver.com/docs/quick-starts/reverse-proxy).

## Create a `pod` to group Cacao Accounting services.

!!! note

    You can create pod and services from the Cockpit Web interface, but for the brevety of this guide we will create the inicial services
    from the command line, once created the services you can use Cockpit .

Those are the commands required to setup a Cacao Accounting deployment (chosee your prefered database service):

!!! tip

    Do not copy and paste these commands directly, you can download a example script above and edit it with your prefered text editor.

=== ":simple-mysql: MySQL"

    ``` bash
    podman pod create --replace --name cacao-mysql -p 9080:80 -p 9443:443 -p 9443:443/udp

    podman volume create --ignore cacao-mysql-backup

    podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-db \
      --volume cacao-mysql-backup:/var/lib/mysql \
      -e MYSQL_ROOT_PASSWORD=cacaodb \
      -e MYSQL_DATABASE=cacaodb \
      -e MYSQL_USER=cacaodb \
      -e MYSQL_PASSWORD=cacaodb \
      -d docker.io/library/mysql:8

    podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-server \
      -v ./Caddyfile:/etc/caddy/Caddyfile:z \
      -v caddy_data:/data \
      -v caddy_config:/config \
      -d docker.io/library/caddy:alpine

    podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-app \
      -e CACAO_KEY=nsjksAAA.ldknsdlkd532445yrVBNyrgfhdyyreys+++++ljdn \
      -e CACAO_DB=mysql+pymysql://cacaodb:cacaodb@localhost:3306/cacaodb \
      -e CACAO_USER=cacaouser \
      -e CACAO_PSWD=cacaopswd \
      -d quay.io/cacaoaccounting/cacaoaccounting:main

    ```

    Download the base script for MySQL in the same directory of your Caddy file and edit.

    !!! warning

         Review the script before running it, it is adviced to setup a custom `user` and `password` for the
         Cacao Accounting app.

    ```bash
    $ curl -O https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/refs/heads/main/docs/oci_files/mysql.sh
    $ ls
    mysql.sh  Caddyfile
    $ bash mysql.sh
    ```

=== ":simple-postgresql: Postgresql"

    ```bash
    podman pod create --replace --name cacao-psql -p 7080:80 -p 9444:443 -p 9444:443/udp

    podman volume create --ignore cacao-postgresql-backup

    podman run --pod cacao-psql --rm --replace --init --name cacao-psql-db \
      --volume cacao-postgresql-backup:/var/lib/postgresql/data \
      -e POSTGRES_DB=cacaodb \
      -e POSTGRES_USER=cacaodb \
      -e POSTGRES_PASSWORD=cacaodb \
      -d docker.io/library/postgres:17-alpine

    podman run --pod cacao-psql --rm --replace --init --name cacao-psql-server \
      -v ./Caddyfile:/etc/caddy/Caddyfile:z \
      -v caddy_pg_data:/data \
      -v caddy_pg_config:/config \
      -d docker.io/library/caddy:alpine

    podman run --pod cacao-psql --rm --replace --init --name cacao-psql-app \
      -e CACAO_KEY=nsjksldknsdlkLKJ,dsljasfsadggfhh+++++++ASDhhf5325364dn \
      -e CACAO_DB=postgresql+pg8000://cacaodb:cacaodb@localhost:5432/cacaodb \
      -e CACAO_USER=cacaouser \
      -e CACAO_PSWD=cacaopswd \
      -d quay.io/cacaoaccounting/cacaoaccounting:main
    ```

    Download the base script for Postgresql in the same directory of your Caddy file and edit.

    !!! warning

         Review the script before running it, it is adviced to setup a custom `user` and `password` for the
         Cacao Accounting app.

    ```bash
    $ curl -O https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/refs/heads/main/docs/oci_files/psql.sh
    $ ls
    psql.sh  Caddyfile
    $ bash psql.sh
    ```

### Allow the `Caddy` :simple-caddy: web Server to read the `Caddyfile`.

In Fedora, Rocky Linux, Alma Linux with active SELinux the `:z` option is required to grant the Caddy service read
access to the Caddyfile, other operative system like Debian or Ubuntu try `:ro` to grant read access to the process running
the container to the host file system.

!!! info

    You can read more about containers file system access in this post: [https://www.redhat.com/en/blog/container-permission-denied-errors](https://www.redhat.com/en/blog/container-permission-denied-errors)

### Allow access to restricted ports.

!!! warning

    It is recomended to run podman containers as normal users (not root or sudo), running as root you can map your pod to ports under 1024.

Running `podman` as a not `root` user will no have access to map ports under `1024`.

!! info

    You can read more about containers port mapping in this post: [https://access.redhat.com/solutions/7044059](https://access.redhat.com/solutions/7044059)

Most of the time this is not a issue, but you can use `redir` to redirect traffic to restricted ports:

```
sudo dnf install redir
sudo redir -n -s :80 127.0.0.1:8080
```

You can run podman as root or with sudo to grant access to ports under 1024.
