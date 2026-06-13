"""Пользовательские фильтры шаблонов Django для расчетов и доступа к словарям."""

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Позволяет делать {{ dict|get_item:key }} в шаблонах"""
    return dictionary.get(key)

@register.filter
def hadd(value, arg):
    """Складывает два значения в шаблоне, когда это удобнее сделать прямо при выводе."""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return value


#    Это гарантирует целые числа без .0.
@register.filter
def multiply(value, arg):
    """Умножает два значения в шаблоне для простых расчетов в интерфейсе."""
    try:
        return int(float(value) * float(arg))
    except (ValueError, TypeError):
        return 0


@register.filter
def is_positive(value):
    """Проверяет, является ли число положительным, для условного вывода в шаблоне."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False
