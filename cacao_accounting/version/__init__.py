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

"""Definición unica de la version de la aplicación."""

# Only update the version if all tests are passing.
# PyPi will refuse to push two packages with the same version
# Keep the version bump in a single commit without other changes included in it to ensure a clean release.

APPNAME = "Cacao Accounting"
APPAUTHOR = "William Moreno Reyes"
MAYOR = "0"
MENOR = "0"
PATCH = "1"
DATE = "20250407"
PRERELEASE = "dev" + DATE
# POSTRELESE = "post" + DATE
POSTRELESE = None

if PRERELEASE:  # pragma: no cover
    VERSION = MAYOR + "." + MENOR + "." + PATCH + "." + PRERELEASE
else:
    if POSTRELESE:
        VERSION = MAYOR + "." + MENOR + "." + PATCH + "." + POSTRELESE
    else:
        VERSION = MAYOR + "." + MENOR + "." + PATCH
