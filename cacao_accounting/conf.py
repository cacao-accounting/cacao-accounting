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

from appdirs import user_config_dir, site_config_dir
from configobj import ConfigObj
from os import environ
from os.path import exists, join

appname = "CacaoAccounting"
appauthor = "William Moreno Reyes"

local_conf = "cacaoaccounting.conf"
user_conf = join(user_config_dir(appname, appauthor), local_conf)
global_conf = join(site_config_dir(appname, appauthor), local_conf)

# Verificación si estamos corriendo en Heroku
if "DYNO" in environ:
    HEROKU = True
else:
    HEROKU = False

if exists(local_conf):
    configuracion = ConfigObj(local_conf)
elif exists(user_conf):
    configuracion = ConfigObj(user_conf)
elif exists(global_conf):
    configuracion = ConfigObj(global_conf)
else:
    configuracion = {}
    if HEROKU or "CACAO_ACCOUNTING" in environ:
        configuracion["SQLALCHEMY_DATABASE_URI"] = environ["SQLALCHEMY_DATABASE_URI"]
        configuracion["ENV"] = environ["ENV"]
        configuracion["SECRET_KEY"] = environ["SECRET_KEY"]
    else:
        configuracion["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cacaoaccounting.db"
        configuracion["ENV"] = "development"
        configuracion["DEBUG"] = True
        configuracion["SECRET_KEY"] = "dev"
