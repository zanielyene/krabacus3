from django import template
from django.conf import settings
from django.template.defaultfilters import stringfilter

import hashlib

register = template.Library()

@register.filter
@stringfilter
def hashmail(value):
    return hashlib.sha1(value + getattr(settings, 'MAIL_SALT', 'twizted loves butts')).hexdigest()
