# Setup a database for Cacao Accounting.

Once you have installed Cacao Accounting and have the `cacaoctl` available in `/opt/cacao-accounting/venv/bin/cacaoctl` you can setup your database service:

## Setingup MySQL

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
