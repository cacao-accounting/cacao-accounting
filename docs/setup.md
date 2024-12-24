# Setup overview

Cacao Accounting is a Python :material-language-python: based project with the [Flask](flask.palletsprojects.com) :simple-flask:
microframework as base, Flask uses the [wsgi protocol](https://peps.python.org/pep-3333/), to setup a Cacao Accounting instance
you need:

1. A WSGI application server, [waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/) is included by default.

2. A WEB server, [nginx](https://nginx.org/en/) and [Caddy](https://caddyserver.com/) are common options.

3. A database service, [SQLite](https://www.sqlite.org/index.html), [Postgresql](https://www.postgresql.org/), and [MySQL8](https://www.mysql.com/)
   are supported.

4. A optional [Redis](https://redis.io/) server.

You can set up a Cacao Instance using:

1. From the :simple-docker: [OCI Image](container.md).
2. From the :material-language-python: [Python Package Index](pypi.md).
3. From :simple-git: [sources](sources.md).
