import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import autodiscover_modules

from huey.consumer import Consumer
from huey.consumer_options import ConsumerConfig
from huey.consumer_options import OptionParserHandler

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    help = "Purges a huey queue of tasks"


    def add_arguments(self, parser):

        parser.add_argument("--queue", "-q")


    def handle(self, *args, **options):

        consumer_options = {}

        try:
            if isinstance(settings.HUEY, dict):
                consumer_options.update(settings.HUEY.get('consumer', {}))
        except AttributeError:
            pass

        huey_queue = settings.HUEY_QUEUES[options["queue"]]
        logger.info("Purging {} of {} tasks".format(options["queue"], huey_queue.pending_count()))

        huey_queue.flush()
        logger.info("Purge complete")
