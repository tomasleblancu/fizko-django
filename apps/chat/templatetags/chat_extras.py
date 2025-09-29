"""
Template tags and filters for chat app
"""
import json
import pprint
from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """
    Template filter to look up a key in a dictionary
    Usage: {{ dict|lookup:'key' }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


@register.filter
def pprint(value):
    """
    Template filter to pretty print JSON/dict data
    Usage: {{ data|pprint }}
    """
    try:
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, ensure_ascii=False)
        else:
            return pprint.pformat(value, indent=2)
    except:
        return str(value)


@register.filter
def get_item(dictionary, key):
    """
    Alternative lookup filter
    """
    return dictionary.get(key) if dictionary else None