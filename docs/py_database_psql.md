# Setup a database for Cacao Accounting.

Once you have installed Cacao Accounting from [sources](py_sources.md) or from [pypi](py_pypi.md)
and have the `cacaoctl` available in `/opt/cacao-accounting/venv/bin/cacaoctl` you can setup your
database service:

## Setup PostgreSQL :simple-postgresql:

Follow the next steps to install PostgreSQL in your system.

=== ":simple-ubuntu: APT Based OS"

    Install PostgreSQL with:

    ``` bash
    sudo apt update
    sudo apt install -y postgresql-common
    sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
    sudo apt install -y postgresql
    sudo systemctl enable postgresql --now
    ```

=== ":simple-fedora: RPM Based OS"

    Install PostgreSQL with:

    ```bash
    sudo dnf update
    sudo dnf install -y postgresql-server postgresql
    sudo postgresql-setup --initdb
    sudo systemctl enable postgresql --now
    ```

Secure your database with:

``` bash
sudo -u postgres psql
``` 

And in the psql console execute:

``` bash
ALTER USER postgres WITH ENCRYPTED PASSWORD 'strong_password';
CREATE USER cacaodbuser ENCRYPTED PASSWORD 'cacaodbpwsd';
\q
``` 

!!! warning

    It is recommend to use a custom user and password to setup your database. Remember to
    save your `user`, `password` and `database name` for future reference.

Allow password authentication on the server with:

=== ":simple-ubuntu: APT Based OS"

    Install PostgreSQL with:

    ``` bash
    sudo sed -i '/^local/s/peer/scram-sha-256/' /etc/postgresql/16/main/pg_hba.conf
    ```

=== ":simple-fedora: RPM Based OS"

    Install PostgreSQL with:

    ```bash
    sudo cp /var/lib/pgsql/data/pg_hba.conf /var/lib/pgsql/data/pg_hba.conf.bak
    sudo nano /var/lib/pgsql/data/pg_hba.conf
    ```

    Find the following configuration section within the file

    ```
    local   all             all                                     peer
    ```

    And change `peer` with `md5`:

    ```
    local   all             all                                     md5
    ```

Restart the database server with:

``` bash
sudo systemctl restart postgresql
``` 

Create the Cacao Accounting database with:

``` bash
sudo -u postgres cacaoaccountingdb -O cacaodbuser
```

With this setup you can set the `CACAO_DB` enviroment variable to the conection string of the
database you have created, also set a `SECRET_KEY` enviroment variable with lowercases, uppercases
and numbers.

```sql
sudo export CACAO_DB=postgresql+pg8000://cacaodbuser:cacaodbpwsd@localhost/cacaoaccountingdb
sudo export CACAO_KEY=sñldkñsadfmnskpfmskn1235aaaaaaAAAAAAA
```

!!! note

    Aditional info about Cacao Accounting configuration is available [here](set_up.md).

Populate the database and create a new administrator user with:

```bash
CACAO_USER=cacaoadmin
CACAO_PSWD=cacaoadminpass
/opt/cacao-accounting/venv/bin/cacaoctl setupdb
```

!!! warning

    Use a custom user id and password for the administrative user of Cacao Accounting.

If not errors are reported your database show be populated with the system tables and initial records.

You can continue to setup systemd to start Cacao Accounting at [startup](py_systemd.md).