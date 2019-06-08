from django import template
from django.utils import timezone
import dateutil.parser

register = template.Library()

MOMENT = 120  # duration in seconds within which the time difference


# will be rendered as 'a moment ago'

@register.filter
def fmt_timedelta(value):
    """
    Finds the difference between the datetime value given and now()
    and returns appropriate humanize form
    """
    if value is None or value == "":
        return "Never"

    delta = timezone.now() - value
    tot_seconds = delta.total_seconds()

    days = int(tot_seconds/86400)
    tot_seconds -= days * 86400
    hours = int(tot_seconds/3600)
    tot_seconds -= hours * 3600
    minutes = int(tot_seconds/60)
    tot_seconds -= minutes * 60
    tot_seconds = int(tot_seconds)

    s = ""
    if days:
        s += "{} days ".format(days)
    if hours:
        s += "{} hours ".format(hours)
    if minutes:
        s += "{} mins ".format(minutes)
    if tot_seconds:
        s += "{} sec ".format(tot_seconds)
    s += "ago"

    return s
