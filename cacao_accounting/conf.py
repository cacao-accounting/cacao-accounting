"""
Copyright 2020 William José Moreno Reyes

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Contributors:
 - William José Moreno Reyes
"""

from appdirs import user_config_dir, site_config_dir
import configobj
from os import environ
from os.path import exists, join

appname = "CacaoAccounting"
appauthor = "William Moreno Reyes"
local_conf = "cacaoaccounting.conf"
user_conf = join(user_config_dir(appname, appauthor), local_conf)
global_conf = join(site_config_dir(appname, appauthor), local_conf)

# Verificación si estamos corriendo en Heroku
if "DYNO" in ["DYNO"]:
    HEROKU = True
else:
    HEROKU = False

if exists(local_conf):
    config = configobj.ConfigObj(local_conf)
elif exists(user_conf):
    config = configobj.ConfigObj(user_conf)
elif exists(global_conf):
    config = configobj.ConfigObj(global_conf)
else:
    config = []


