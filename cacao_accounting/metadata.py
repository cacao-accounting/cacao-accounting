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

from datetime import datetime


APPNAME = "Cacao Accounting"
APPAUTHOR = "William Moreno Reyes"
MAYOR = "0"
MENOR = "0"
PATCH = "1"
PRERELEASE = "dev" + datetime.today().strftime("%Y%m%d%H%M") 
VERSION = MAYOR + "." + MENOR + "." + PATCH + "." + PRERELEASE

# development
# release_candidate
# alpha
# beta
# stable

__state__ = "development"
DEVELOPMENT = __state__ != "stable"


