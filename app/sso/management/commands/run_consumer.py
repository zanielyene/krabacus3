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
    help = "Run the queue consumer"
    _type_map = {'int': int, 'float': float}

    def add_arguments(self, parser):
        option_handler = OptionParserHandler()
        groups = (
            option_handler.get_logging_options(),
            option_handler.get_worker_options(),
            option_handler.get_scheduler_options(),
        )
        for option_list in groups:
            for short, full, kwargs in option_list:
                if short == '-v':
                    full = '--huey-verbose'
                    short = '-V'
                if 'type' in kwargs:
                    kwargs['type'] = self._type_map[kwargs['type']]
                kwargs.setdefault('default', None)
                parser.add_argument(full, short, **kwargs)
        parser.add_argument("--queue")

    def handle(self, *args, **options):

        consumer_options = {}
        try:
            if isinstance(settings.HUEY, dict):
                consumer_options.update(settings.HUEY.get('consumer', {}))
        except AttributeError:
            pass

        for key, value in options.items():
            if value is not None:
                consumer_options[key] = value

        consumer_options.setdefault('verbose',
                                    consumer_options.pop('huey_verbose', None))

        autodiscover_modules("tasks")

        huey_queue = settings.HUEY_QUEUES[options["queue"]]
        #del options["queue"]

        config = ConsumerConfig(**consumer_options)
        config.validate()
        config.setup_logger()

        consumer = Consumer(huey_queue, **config.values)
        logger.info("The following tasks are available for this queue:")
        for command in consumer.huey.registry._registry:
            logger.info(command.replace('queue_task_', ''))
        consumer.run()