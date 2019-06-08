from django import template
from django.utils.timezone import now

register = template.Library()

MOMENT = 120  # duration in seconds within which the time difference


# will be rendered as 'a moment ago'

@register.filter
def fmt_int(value):
    """
    Finds the difference between the datetime value given and now()
    and returns appropriate humanize form
    """
    if value is None:
        return -999999999999999
    return int(value)
