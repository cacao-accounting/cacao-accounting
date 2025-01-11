# Setup overview

Cacao Accounting is a Python :material-language-python: based project built on the [Flask](flask.palletsprojects.com) :simple-flask:
microframework. Flask utilizes the [wsgi protocol](https://peps.python.org/pep-3333/) to handle users requets. To set up a Cacao Accounting instance, you'll need:

1. A WSGI application server: [waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/) is included by default.

2. A web server: [nginx](https://nginx.org/en/) and the [Caddy](https://caddyserver.com/) web server are common choices.

3. A database service: Supported options include [SQLite](https://www.sqlite.org/index.html), [Postgresql](https://www.postgresql.org/), and [MySQL8](https://www.mysql.com/).

4. A optional [Redis](https://redis.io/) server.

You can set up a Cacao Accounting instance in several ways:

1. From the :simple-docker: [OCI Image](container.md).
2. From the :material-language-python: [Python Package Index](py_pypi.md).
3. From :simple-git: [sources](py_sources.md).

Also note that there is a [Desktop Version](https://github.com/cacao-accounting/cacao-accounting-desktop) :desktop: of Cacao Accounting available.
