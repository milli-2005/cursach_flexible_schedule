"""Пакет представлений: собирает функции страниц из доменных файлов views."""

from .auth import *
from .availability import *
from .distribution_rules import *
from .public import *
from .reports import *
from .schedules import *
from .swaps import *
from .workouts import *
from ..exports.operational_excel import export_operational_excel
