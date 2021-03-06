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

from cacao_accounting.database import db
from cacao_accounting.exception import DataError, ERROR1
from sqlalchemy_paginator import Paginator


MAX_NUMBER = 15


def paginar_consulta(tabla=None, elementos=None):
    """
    Toma una consulta simple y la devuel como una consulta paginada.
    """
    if tabla:
        items = elementos or MAX_NUMBER
        consulta = db.session.query(tabla).order_by(tabla.id)
        consulta_paginada = Paginator(consulta, items)
        return consulta_paginada
    else:
        raise DataError(ERROR1)
