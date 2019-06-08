from django.views.generic import TemplateView

import logging

from .models import UpdateMessage, UpdateMessageReadReceipt

logger = logging.getLogger(__name__)


class UpdatesView(TemplateView):
    template_name = 'notifications/updates_page.html'

    def get_context_data(self, **kwargs):
        ctx = super(UpdatesView, self).get_context_data(**kwargs)

        updates = UpdateMessage.objects.all().order_by('-post_time')

        ctx["updates"] = updates

        # if authenticated user, highlight unread
        if self.request.user.is_authenticated:
            messages_user_has_read = list(UpdateMessageReadReceipt.objects.filter(user=self.request.user).values_list('message_id', flat=True))
            UpdateMessageReadReceipt.mark_messages_read(self.request.user, updates)

        else:
            messages_user_has_read = updates.values_list('id', flat=True)
        ctx["updates_read"] = messages_user_has_read

        return ctx
