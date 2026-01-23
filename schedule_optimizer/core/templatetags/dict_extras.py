from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Безопасное получение значения из словаря (поддерживает вложенные вызовы)."""
    if dictionary is None:
        return {}
    if hasattr(dictionary, 'get'):
        return dictionary.get(key, {})
    return {}