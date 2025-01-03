# Setup a database for Cacao Accounting.

Once you have installed Cacao Accounting from [sources](py_sources.md) or from [pypi](py_pypi.md)
and have the `cacaoctl` available in `/opt/cacao-accounting/venv/bin/cacaoctl` you can setup your
database service:

## Setup MySQL :simple-mysql:

Follow the next steps to install MySQL in your system.

=== ":simple-ubuntu: APT Based OS"

    Install MySQL with:

    ``` bash
    sudo apt update
    sudo apt install mysql-server -y
    mysql --version
    sudo systemctl enable mysql --now
    sudo systemctl status mysql
    ```

=== ":simple-fedora: RPM Based OS"

    Install MySQL with:

    ```bash
    sudo dnf update
    sudo dnf install mysql-server -y
    mysql --version
    sudo systemctl start mysqld.service --now
    sudo systemctl status mysqld
    ```

Once installed secure your MySQL database with:

```bash
sudo mysql_secure_installation
```

!!! info

    Refers to the [MySQL official documentation](https://dev.mysql.com/doc/refman/8.4/en/mysql-secure-installation.html) about the secure installation script

Once you have installer and secured MySQL loggin with:

```bash
sudo mysql -u root -p
```

And create a user and database with:

```sql
CREATE DATABASE IF NOT EXISTS cacaoaccounting;
CREATE USER IF NOT EXISTS 'cacaodbuser' IDENTIFIED BY 'cacaodbpswd';
GRANT ALL PRIVILEGES ON cacaoaccounting.* TO 'cacaodbuser';
FLUSH PRIVILEGES;
```

!!! warning

    It is recommend to use a custom user and password to setup your database. Remember to
    save your `user`, `password` and `database name` for future reference.

With this setup you can set the `CACAO_DB` enviroment variable to the conection string of the
database you have created, also set a `SECRET_KEY` enviroment variable with lowercases, uppercases
and numbers.

```sql
sudo export CACAO_DB=mysql+pymysql://cacaodbuser:cacaodbpswd@localhost/cacaoaccounting
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