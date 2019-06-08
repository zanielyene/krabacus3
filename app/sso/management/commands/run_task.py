import logging
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import autodiscover_modules
from django.core.management.base import BaseCommand, CommandError
from huey.consumer import Consumer
from huey.consumer_options import ConsumerConfig
from huey.consumer_options import OptionParserHandler
from conf.huey_queues import HUEY_QUEUES
import json

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "enqueue a huey task"

    def add_arguments(self, parser):

        parser.add_argument("task")
        parser.add_argument("--params")

    def handle(self, **options):

        if options.get('task', None) == "help":
            all_tasks = []
            for name, queue in HUEY_QUEUES.items():
                tasks = queue.get_tasks()
                all_tasks.extend(tasks)
            logger.info("Available tasks:")
            for t in all_tasks:
                logger.info(t[11:])
            raise CommandError('You need to provide a task to run.')

        autodiscover_modules("tasks")

        queue_to_use = None
        for name,queue in HUEY_QUEUES.items():
            tasks = queue.get_tasks()
            if "queue_task_{}".format(options.get('task')) in tasks:
                queue_to_use = queue
                break

        if queue_to_use is None:
            raise CommandError('Task is not registered to any queues: {}'.format(options.get('task')))

        task_class = queue_to_use.registry.get_task_class("queue_task_{}".format(options.get('task')))
        try:
            mod = __import__(task_class.__module__)
        except ImportError:
            raise CommandError('Error importing task')

        fullpath = task_class.__module__ + "." + options.get('task')

        for i in fullpath.split(".")[1:]:
            mod = getattr(mod, i)

        if not options.get('params'):
            logger.info("Enqueueing Task: {}".format(options.get("task")))
            mod()
        else:
            logger.info("params: {}".format(options.get('params')))
            decoded_options = json.loads(str(options.get('params')))
            logger.info("Enqueueing Task: {}".format(options.get("task")))
            mod(decoded_options)

