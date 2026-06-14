# Кастомные фильтры для шаблонов (.html).
# В Django-шаблонах нельзя писать Python-код.
# Чтоб обойти это, регистрируем функции-фильтры и вызываем их через {{ значение|фильтр:аргумент }}.
# Django читает переменную register (Library) и берёт всё, что обёрнуто в @register.filter.

from django import template
    # Импортируем Library — класс, в который регистрируются фильтры.

register = template.Library()
    # Создаём экземпляр Library. Django ищет переменную с таким именем.


# get_item — достаёт значение из словаря по ключу
# {{ словарь|get_item:ключ }} → значение
@register.filter
    # Говорит Django: «эта функция — фильтр для шаблонов».
def get_item(dictionary, key):
    # dictionary — то, к чему применяем фильтр (левая часть |).
    # key — аргумент после : в шаблоне.
    if dictionary is None:
        return {}
            # Если в словаре ничего нет (None), то нельзя вызывать .get() —
            # Python выдаст ошибку «'NoneType' object has no attribute 'get'».
            # Чтоб страница не упала — сразу возвращаем пустой словарь {}.
    if hasattr(dictionary, 'get'):
        return dictionary.get(key, {})
            # hasattr проверяет, есть ли у объекта метод .get.
            # Если есть — вызываем. {} — что вернуть, если ключ не найден.
    return {}
        # Если у объекта нет метода .get (например, это число или строка) — {}.


# hadd — складывает два числа в шаблоне
# {{ число1|hadd:число2 }} → сумма. В Django-шаблонах нет +, поэтому так.
@register.filter
def hadd(value, arg):
    # value — первое число, arg — второе (после :).
    try:
        return float(value) + float(arg)
            # Приводим к float и складываем.
    except (ValueError, TypeError):
        return value
            # Если не получилось (например, передали не число) — возвращаем как есть.


# multiply — умножает, возвращает целое (без .0)
# {{ число1|multiply:число2 }} → целое. В Django-шаблонах нет *.
@register.filter
def multiply(value, arg):
    try:
        return int(float(value) * float(arg))
            # Умножаем как float, превращаем в int — убираем .0.
    except (ValueError, TypeError):
        return 0
            # При ошибке — 0, чтоб в таблице не было пустых ячеек.


# short_name — «Фамилия Имя» из объекта пользователя (или логин, если имя не заполнено)
# {{ user|short_name }} → "Иванов Иван"
@register.filter
def short_name(user):
    # user — объект User Django (поля last_name, first_name, username).
    if not user:
        return ''
            # Если user = None — пустая строка, чтоб не было ошибки.
    parts = [p for p in (user.last_name, user.first_name) if p]
        # Собираем фамилию + имя в список, отбрасывая пустые строки.
    return ' '.join(parts) if parts else user.username
        # Если список непустой — склеиваем "Фамилия Имя", иначе берём логин.


# is_positive — проверяет, что число > 0
# {{ число|is_positive }} → True/False. Нужно для {% if число|is_positive %}.
@register.filter
def is_positive(value):
    try:
        return float(value) > 0
            # Пробуем привести к float и сравнить с 0.
    except (ValueError, TypeError):
        return False
            # Если не число — возвращаем False.
