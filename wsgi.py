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
Ejecuta el servidor WSGI predeterminado.

Si en la version de la aplicacion se establece cualquier valor para
PRERELEASE que no sea NULL se ejecutara el servidor de desarrollo con
la opción DEBUG habilitada.
"""

from cacao_accounting.config import TESTING_MODE
from cacao_accounting.server import app, server


if __name__ == "__main__":
    if TESTING_MODE:
        app.run(debug=True, port=8080)
    else:
        server()
