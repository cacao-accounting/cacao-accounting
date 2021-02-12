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


import os
import pytest
import requests
import subprocess
import time
from sys import executable
from unittest import TestCase
from cacao_accounting import create_app
from cacao_accounting.datos.base import base_data
from cacao_accounting.datos.demo import demo_data


@pytest.fixture(scope="class")
def iniciar_servidor():
    pr = subprocess.Popen(
        [
            executable,
            os.path.abspath(os.path.dirname(__file__)),
        ]
    )
