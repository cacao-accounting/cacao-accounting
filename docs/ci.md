# Unit Testing

The accounting records of companies using Cacao Accounting is something we care about, so we have many tests to check the quality of a Cacao Accounting release.

- [Python Package:](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-package.yml) Check the code aganist various Python versions, you can run the test suite with: `CACAO_TEST=True SECRET_KEY=ASD123kljaAddS python -m pytest -v -s --slow=True`
- [Coverage:](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-coverage.yml) Generate code [coverage report](https://coveralls.io/github/cacao-accounting/cacao-accounting?branch=main).
- [Database Validation:](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/dbcheck.yml) Check the database schema aganist multiple database engines, we check aganist SQLite, MySQL and PostgreSQL.
- [Publish to PyPi:](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/publish.yml) Publish the last release to the Python Package Index, this will fail if there is not a update the release.
