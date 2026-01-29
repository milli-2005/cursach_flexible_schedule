from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, 0)

@register.filter
def hadd(value, arg):
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return value