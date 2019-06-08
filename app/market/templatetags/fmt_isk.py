from django import template
from django.utils.timezone import now

register = template.Library()

MOMENT = 120  # duration in seconds within which the time difference


# will be rendered as 'a moment ago'

@register.filter
def fmt_isk(value):
    """
    Finds the difference between the datetime value given and now()
    and returns appropriate humanize form
    """
    if value is None:
        return None
    v = abs(value)
    if v < 1000:
        return str(round(value / 1000, 3)) + " K"
    if v < 10000:
        return str(round(value / 1000, 2)) + " K"
    if v < 100000:
        return str(round(value / 1000, 1)) + " K"
    if v < 1000000:
        return str(int(value / 1000)) + " K"
    if v < 10000000:
        return str(round(value / 1000000, 2)) + " M"
    if v < 100000000:
        return str(round(value / 1000000, 1)) + " M"
    if v < 1000000000:
        return str(int(value / 1000000)) + " M"
    if v < 10000000000:
        return str(round(value / 1000000000, 2)) + " B"
    return str(round(value / 1000000000, 1)) + " B"