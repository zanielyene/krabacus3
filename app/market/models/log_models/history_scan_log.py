import uuid
from django.db import models
from eve_api.models import Region


class MarketHistoryScanLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan_start = models.DateTimeField(db_index=True, auto_now_add=True)
    scan_complete = models.DateTimeField(db_index=True, default=None, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)

    class Meta:
        index_together = [
            ("region", "scan_start"),
            ("region", "scan_complete"),
        ]

    @staticmethod
    def get_most_recent_completed_scan(region_id):
        exists = MarketHistoryScanLog.objects.filter(
            region_id=region_id,
            scan_complete__isnull=False).exists()
        if not exists:
            return None

        scan_log = MarketHistoryScanLog.objects.filter(
            region_id=region_id,
            scan_complete__isnull=False
        ).order_by('-scan_start').first()
        return scan_log
