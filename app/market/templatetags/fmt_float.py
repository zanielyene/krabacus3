from django import template
from django.utils.timezone import now

register = template.Library()

MOMENT = 120  # duration in seconds within which the time difference


# will be rendered as 'a moment ago'

@register.filter
def fmt_float(value):
    """
    Finds the difference between the datetime value given and now()
    and returns appropriate humanize form
    """
    if value is None:
        return None
    if value == 0:
        return 0
    if value <= 1:
        return round(value, 3)
    if value <= 10:
        return round(value, 2)
    if value <= 100:
        return round(value,1)
    return int(value)
