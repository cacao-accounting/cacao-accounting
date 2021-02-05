import pytest
from unittest import TestCase
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data
from opensource-database import Entidad, CentroCosto, Unidad, Proyecto, Moneda


