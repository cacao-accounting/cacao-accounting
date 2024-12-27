# Install Cacao Accounting from the [Python Package Index](https://pypi.org/project/cacao-accounting/).

![PyPI - Version](https://img.shields.io/pypi/v/cacao-accounting)
![PyPI - Status](https://img.shields.io/pypi/status/cacao-accounting)
![PyPI - Implementation](https://img.shields.io/pypi/implementation/cacao-accounting)
![PyPI - Format](https://img.shields.io/pypi/format/cacao-accounting)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cacao-accounting)

You can install Cacao Accounting in a dedicated server as a Python Package hosted in the [Python Package Index :material-language-python:](https://pypi.org/project/cacao-accounting/).

!!! note

    If you want to run aditional software in your server it is recomended to install Cacao Accounting
    using the [OCI image :simple-docker:](container.md) to isolate each service from others.

You can install Cacao Accounting in any Linux OS that supports:

- A compatible database server: PostgreSQL or MySQL.
- A web server like nginx
- A supported version of Python (>=3.8)

!!! success

    It is recommend to choose a long tern support version of your base OS like Ubuntu LTS (.deb based OS)
    or a RedHat Linux clone like Rocky Linux (.rpm based OS).

!!! tip

    It is recommended to install Cacao Accounting in the `/opt` directory of your Linux system, this is the
    directory recommend by the [Linux FHS](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s13.html) so
    you main Cacao Accounting installation directoty will be `/opt/cacao-accounting` and the `cacaoctl` tool
    will be available in `/opt/cacao-accounting/venv/bin/cacaoctl`, this path will be used latter in this 
    guide.

## Create a Python Virtual Enviroment:

```bash
cd /pot
mkdir cacao-accounting
cd cacao-accounting
python3 -m venv venv 
sudo source venv/bin/activate
```

## Install Cacao Accounting in the Virtual Enviroment:

Install Cacao Accounting with:

```bash
# Ensure your virtual env is active!
python -m pip install cacao-accounting
```

### Verify Cacao Accouting is installed with:

You can check Cacao Accounting is installed with:

```bash
cacaoctl version
0.0.0.dev20241209
```

Once Cacao Accounting is installed and the `cacaoctl` tool is available in `/opt/cacao-accounting/venv/bin/cacaoctl` you can continue to setup your database server, you can choose 
[PostgreSQL](py_database_psql.md) or [MySQL](py_database_mysql.md).
