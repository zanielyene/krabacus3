from django import template
from django.utils import timezone
import dateutil.parser
from notifications.models import UpdateMessageReadReceipt

register = template.Library()

@register.filter
def has_viewed_update(user, message):
    read_receipt = UpdateMessageReadReceipt.objects.filter(user=user, message=message).exists()
    if read_receipt:
        return True
    else:
        return False
