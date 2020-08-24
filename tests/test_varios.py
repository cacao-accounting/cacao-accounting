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

from cacao_accounting.loggin import logger
from cacao_accounting.metadata import __state__


def logs():
    logger.debug("Debug")
    logger.info("Info")
    logger.warning("Warning")
    logger.error("Error")
    logger.critical("Critical")


def test_dev():
    __state__ = "development"
    logs()


def test_rc():
    __state__ = "release_candidate"
    logs()


def test_stable():
    __state__ = "stable"
    logs()
