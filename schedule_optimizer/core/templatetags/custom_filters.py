from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Позволяет делать {{ dict|get_item:key }} в шаблонах"""
    return dictionary.get(key)

@register.filter
def hadd(value, arg):
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return value


#    Это гарантирует целые числа без .0.
@register.filter
def multiply(value, arg):
    try:
        return int(float(value) * float(arg))
    except (ValueError, TypeError):
        return 0


@register.filter
def is_positive(value):
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False
