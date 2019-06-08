from django import template
from django.utils import timezone
import dateutil.parser
from notifications.models import UpdateMessage, UpdateMessageReadReceipt
register = template.Library()

@register.filter
def get_news_notification_count(user):
    if not user.is_authenticated:
        return 0

    read_receipts = UpdateMessageReadReceipt.objects.filter(user=user).values_list('message_id', flat=True)
    messages = UpdateMessage.objects.filter(trigger_unread_widget = True).exclude(id__in=read_receipts)
    unread_messages_count = len(messages)
    return unread_messages_count
