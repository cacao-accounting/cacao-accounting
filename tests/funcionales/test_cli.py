# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes

# pylint: disable=redefined-outer-name
import pytest
from cacao_accounting import create_app as app_factory
from cacao_accounting.database import database
from cacao_accounting.datos import base_data, dev_data


@pytest.fixture(scope="module", autouse=True)
def rapp():
    app = app_factory(
        {
            "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DEBUG": True,
            "DESKTOPMODE": False,
        }
    )
    with app.app_context():
        database.drop_all()
        database.create_all()
        base_data(user="hello", passwd="hello")
        dev_data()
    app.app_context().push()
    yield app


@pytest.fixture
def client(rapp):
    return rapp.test_client()


def test_runner(rapp):
    from os import environ
    from cacao_accounting.metadata import VERSION

    r = rapp.test_cli_runner()
    result = r.invoke(args=["version"])
    assert VERSION in result.output

    if environ.get("CACAO_TEST"):
        result = r.invoke(args=["cleandb"])
        result = r.invoke(args=["initdb"])
        result = r.invoke(args=["setupdb"])
