# Install Cacao Accounting from Sources.

Cacao Accounting source code is hosted in [Github](https://github.com/cacao-accounting/cacao-accounting),
you can install Cacao Accounting from sources following the next steps:

!!! success

    In order to successfully install Cacao Accounting from sources you need this tools available
    in your system: [Python :material-language-python:](https://www.python.org/), [git :material-git:](https://git-scm.com/)
    and [npm :fontawesome-brands-npm:](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).

!!! tip

    It is recommended to install Cacao Accounting in the `/opt` directory of your Linux system, this is the
    directory recommend by the [Linux FHS](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s13.html) so
    you main Cacao Accounting installation directoty will be `/opt/cacao-accounting` and the `cacaoctl` tool
    will be available in `/opt/cacao-accounting/venv/bin/cacaoctl`, this path will be used latter in this 
    guide.

## Clone the git repository:

Get the sources from Github with:

```bash
cd /opt
git clone https://github.com/cacao-accounting/cacao-accounting.git
cd cacao-accounting
```

## Create a Python Virtual Enviroment:

```bash
python3 -m venv venv 
source venv/bin/activate
```

## Install node modules:

```bash
cd cacao_accounting/static
npm install
# Back to main directory with
cd ..
cd ..
```

## Install Cacao Accounting in the Virtual Enviroment:

Install Cacao Accounting with:

```bash
# Ensure your virtual env is active!
python -m pip install .
```

### Verify Cacao Accouting is installed with:

You can check Cacao Accounting is installed with:

```bash
cacaoctl version
0.0.0.dev20241209
```

Once Cacao Accounting is installed and the `cacaoctl` tool is available in `/opt/cacao-accounting/venv/bin/cacaoctl` you can continue to setup your [database](py_database.md).
