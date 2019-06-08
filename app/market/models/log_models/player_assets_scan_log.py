import uuid
from django.db import models
from django.utils import timezone
from eve_api.models import EVEPlayerCharacter


class PlayerAssetsScanLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan_start = models.DateTimeField(db_index=True, auto_now_add=True)
    scan_complete = models.DateTimeField(db_index=True, default=None, null=True)
    character = models.ForeignKey(EVEPlayerCharacter, on_delete=models.CASCADE)

    class Meta:
        index_together = [
            ("character", "scan_start"),
            ("character", "scan_complete"),
        ]

    @staticmethod
    def get_most_recent_completed_scan(character_id):
        exists = PlayerAssetsScanLog.objects.filter(
            character_id=character_id,
            scan_complete__isnull=False).exists()
        if not exists:
            return None

        scan_log = PlayerAssetsScanLog.objects.filter(
            character_id=character_id,
            scan_complete__isnull=False
        ).order_by('-scan_start').first()
        return scan_log

    @staticmethod
    def start_scan_log(character):
        log = PlayerAssetsScanLog(character=character)
        log.save()
        return log

    def stop_scan_log(self):
        self.scan_complete = timezone.now()
        self.save()
