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

from setuptools import setup
from os import path
from datetime import datetime

aqui = path.abspath(path.dirname(__file__))
with open(path.join(aqui, "README.md"), encoding="utf-8") as f:
    descripcion = f.read()

timestamp = ".dev" + datetime.today().strftime("%Y%m%d%H%M")

setup(
    name="cacao_accounting",
    version="0.0.1" + timestamp,
    author="William José Moreno Reyes",
    author_email="williamjmorenor@gmail.com",
    description="Software contable para micro, pequeñas y medianas empresas.",
    long_description=descripcion,
    long_description_content_type="text/markdown",
    packages=["cacao_accounting"],
    include_package_data=True,
    classifiers=[
        "Development Status :: 1 - Planning",
        "Framework :: Flask",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: Spanish",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Office/Business :: Financial",
        "Topic :: Office/Business :: Financial :: Accounting",
    ],
    install_requires=[
        "alembic",
        "appdirs",
        "babel",
        "bcrypt",
        "configobj",
        "flask",
        "flask-alembic",
        "flask-babel",
        "flask-login",
        "flask-sqlalchemy",
        "flask-wtf",
        "loguru",
        "pg8000",
        "PyMySQL",
        "sqlalchemy",
        "teritorio",
        "waitress",
        "wtforms",
        "WTForms-SQLAlchemy",
    ],
    entry_points={
        "console_scripts": [
            "cacaoctl=cacao_accounting:command",
        ]
    },
)
