import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import autodiscover_modules

from huey.consumer import Consumer
from huey.consumer_options import ConsumerConfig
from huey.consumer_options import OptionParserHandler

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Queue consumer. Example usage::

    To start the consumer (note you must export the settings module):

    django-admin.py run_huey
    """
    help = "Get number of tasks in queue and return up to 10 tasks at head of queue"


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
        logger.info("{} has {} tasks in the queue".format(options["queue"], huey_queue.pending_count()))

        queued_tasks = huey_queue.pending()
        queued_tasks.reverse()
        queued_tasks = queued_tasks[:10]
        ctr = 1
        for task in queued_tasks:
            logger.info("{}. {}".format(ctr, task))
            ctr += 1
