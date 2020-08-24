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

from appdirs import user_config_dir, site_config_dir, user_log_dir
from configobj import ConfigObj
from os import environ
from os.path import exists, join
from sys import platform, stdout
from cacao_accounting.loggin import logger as logs
from cacao_accounting.metadata import DEVELOPMENT

appname = "CacaoAccounting"
appauthor = "William Moreno Reyes"

local_conf = "cacaoaccounting.conf"
log_file = "cacaoaccounting.log"
user_conf = join(user_config_dir(appname, appauthor), local_conf)
user_logs = join(user_log_dir(appname, appauthor), log_file)
global_conf = join(site_config_dir(appname, appauthor), local_conf)


if exists(local_conf):
    configuracion = ConfigObj(local_conf)
    logs.add(log_file, format="{time} {level} {message}", level="DEBUG")

elif exists(user_conf):
    configuracion = ConfigObj(user_conf)
    logs.add(user_logs, format="{time} {level} {message}", level="INFO")

elif exists(global_conf):
    configuracion = ConfigObj(global_conf)
    if "DOCKERISED" in environ:
        logs.add(stdout, format="{time} {level} {message}", level="INFO")
    elif platform == "linux":
        logs.add(join("/var/logs", log_file), format="{time} {level} {message}", level="INFO")
    elif platform == "'win32'":
        logs.add(log_file, format="{time} {level} {message}", level="INFO")
    else:
        pass

else:
    configuracion = {}
    if "DYNO" in environ or "CACAO_ACCOUNTING" in environ:
        configuracion["SQLALCHEMY_DATABASE_URI"] = environ["SQLALCHEMY_DATABASE_URI"]
        configuracion["DATABASE"] = environ["DATABASE"]
        configuracion["ENV"] = environ["ENV"]
        configuracion["SECRET_KEY"] = environ["SECRET_KEY"]
    elif DEVELOPMENT:
        configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cacaoaccounting.db"
        configuracion["DATABASE"] = "sqlite"
        configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        configuracion["ENV"] = "development"
        configuracion["SECRET_KEY"] = "dev"
        configuracion["EXPLAIN_TEMPLATE_LOADING"] = True
        configuracion["DEGUG"] = True
    else:
        pass
