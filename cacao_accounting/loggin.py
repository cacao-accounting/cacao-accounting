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
Configuración centralizada para logs del sistema.
"""

from sys import stderr
from loguru import logger
from cacao_accounting.conf import logs_file
from cacao_accounting.metadata import __state__

if __state__ == "development":
    logger.add(stderr, format="{time} {level} {message}", level="DEBUG")
elif __state__ == "release_candidate" or __state__ == "alpha":
    logger.add(logger.ad(stderr, format="{time} {level} {message}", level="INFO"))
else:
    logger.add(logger.ad(logs_file, format="{time} {level} {message}", level="INFO"))
