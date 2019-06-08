from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid


class UpdateMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post_time = models.DateTimeField(default=timezone.now)
    subject = models.TextField()
    message = models.TextField()
    trigger_unread_widget = models.BooleanField(default=False)


class UpdateMessageReadReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    time_read = models.DateTimeField(default=timezone.now)
    message = models.ForeignKey(UpdateMessage, on_delete=models.CASCADE)

    @staticmethod
    def mark_messages_read(user, messages):
        """
        Returns list of unread messages that are now read
        :param user:
        :param messages:
        :return:
        """
        receipts_to_commit = []
        for message in messages:
            if not UpdateMessageReadReceipt.objects.filter(message=message,user=user).exists():
                receipts_to_commit.append(
                    UpdateMessageReadReceipt(
                        user=user,
                        message=message
                    )
                )

        UpdateMessageReadReceipt.objects.bulk_create(receipts_to_commit)
        return receipts_to_commit
