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

"""Modulo a ejecutar por defecto al ejecutar cacao_accounting."""

from cacao_accounting.server import app, server
from cacao_accounting.version import PRERELEASE


if __name__ == "__main__":
    if PRERELEASE:
        app.run(debug=True, port=8000)
    else:
        server()
