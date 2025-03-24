from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Retrieve an item from a dictionary using a key."""
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiply the value by arg."""
    try:
        return value * arg
    except (TypeError, ValueError):
        return ''