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

"""
Utilidad para cargar la configuración de la aplicacion.
"""

from os import environ
from os.path import exists, join
from appdirs import user_config_dir, site_config_dir
from configobj import ConfigObj
from cacao_accounting.metadata import DEVELOPMENT, APPAUTHOR, APPNAME
from cacao_accounting.tools import home


DOCKERISED = "DOCKERISED" in environ

DESKTOP = "CACAO-DESKTOP" in environ or exists(join(home, "cacaodesktop"))

if "SERVER_THREADS" in environ:
    THREADS = int("SERVER_THREADS")
else:
    THREADS = 3

local_conf = "cacaoaccounting.conf"
user_conf = join(user_config_dir(APPNAME, APPAUTHOR), local_conf)
global_conf = join(site_config_dir(APPNAME, APPAUTHOR), local_conf)


if exists(local_conf):
    configuracion = ConfigObj(local_conf)

elif exists(user_conf):
    configuracion = ConfigObj(user_conf)

elif exists(global_conf):
    configuracion = ConfigObj(global_conf)

else:
    configuracion = {}
    if "DYNO" in environ or "CACAO_ACCOUNTING" in environ:
        configuracion["SQLALCHEMY_DATABASE_URI"] = environ["SQLALCHEMY_DATABASE_URI"]
        configuracion["SECRET_KEY"] = environ["SECRET_KEY"]
    elif DEVELOPMENT or ("CACAOTEST" in environ) or ("CI" in environ):
        SQLITE = "sqlite:///cacaoaccounting.db"
        MYSQL = "mysql+pymysql://cacao:cacao@localhost:3306/cacao"
        POSTGRESQL = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"
        configuracion["SQLALCHEMY_DATABASE_URI"] = POSTGRESQL
        configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        configuracion["ENV"] = "development"
        configuracion["SECRET_KEY"] = "dev"
        configuracion["EXPLAIN_TEMPLATE_LOADING"] = True
        configuracion["DEGUG"] = True
    else:
        pass
