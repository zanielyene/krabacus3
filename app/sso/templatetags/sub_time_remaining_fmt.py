from django import template
from django.utils.timezone import now

register = template.Library()

MOMENT = 120  # duration in seconds within which the time difference


# will be rendered as 'a moment ago'

@register.filter
def sub_time_remaining_fmt(value):
    """
    Finds the difference between the datetime value given and now()
    and returns appropriate humanize form
    """

    if not value:
        return "EXPIRED"

    days = int(value/24)
    hours = value - days * 24
    return "{} days {} hrs".format(days,hours)
