import time, logging
from conf.huey_queues import general_queue


import dateutil.parser
from datetime import timedelta
import re

from eve_api.esi_client import EsiClient
from market.models import TradingRoute, MarketOrder, MarketPriceDAO
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType, EsiKey
from .models import SubscriptionPayment, SubscriptionStatus
from huey import crontab
from django.conf import settings


from django.db.models import Q
from django.utils import timezone

logger=logging.getLogger(__name__)


def process_new_payment(source_character, amount, journal_id, date, reason):
    # validate uuid
    if reason is None:
        logger.error("Received donation without a reason string: id: {} ".format(journal_id))
        return
    p = re.compile('.*([0-9a-f-]{8}-[0-9a-f-]{4}-[0-9a-f-]{4}-[0-9a-f-]{4}-[0-9a-f-]{12}).*')
    m = p.findall(reason)
    if len(m) != 1:
        logger.error("Received donation without any valid uuid string: id: {} reason: {}".format(journal_id, reason))
        return
    ref_id = m[0]

    subscriber_exists = SubscriptionStatus.objects.filter(pk=ref_id).exists()
    if not subscriber_exists:
        logger.error("Received a donation with a uuid string we cannot identify. journal_id: {} uuid: {}".format(journal_id, ref_id))
        return

    # create payment
    subscription = SubscriptionStatus.objects.get(pk=ref_id)

    payment = SubscriptionPayment(
        subscription = subscription,
        amount = int(amount),
        source_character = source_character,
        journal_id = journal_id,
        payment_time_actual = date,
        payment_read_time = timezone.now()
    )
    payment.save()
    logger.info("Logging payment to subscription {} from {} for amount {}".format(ref_id, source_character.name, amount))
    subscription.check_subscription_payments()
    return

@general_queue.periodic_task(crontab(minute='*/30'))
def update_subscription_payments():
    logger.info('LAUNCH_TASK update_subscription_payments')
    with general_queue.lock_task('update_subscription_payments'):
        char = EVEPlayerCharacter.get_object(settings.PAYMENT_CHARACTER_ID)
        client = EsiClient(authenticating_character=char)
        journal_entries = client.get_multiple_paginated("/v4/characters/{}/wallet/journal/".format(char.pk))
        for entry in journal_entries:
            if entry["ref_type"] == "player_donation" and entry.get("second_party_id") == char.pk:
                if not SubscriptionPayment.exists(entry["id"]):
                    process_new_payment(
                        EVEPlayerCharacter.get_object(entry["first_party_id"]),
                        entry["amount"],
                        entry["id"],
                        dateutil.parser.parse(entry["date"]),
                        entry.get("reason")
                    )

    logger.info('FINISH_TASK update_subscription_payments')


@general_queue.task()
def update_subscription(subscription_id):
    logger.info('LAUNCH_TASK update_subscription {}'.format(subscription_id))
    with general_queue.lock_task('update_user_subscription_{}'.format(subscription_id)):
        logger.info("Updating subscription {} from task".format(subscription_id))
        sub = SubscriptionStatus.objects.get(pk=subscription_id)
        sub.check_subscription_payments()
    logger.info('FINISH_TASK update_subscription {}'.format(subscription_id))


@general_queue.periodic_task(crontab(minute='*/5'))
def enqueue_update_subscriptions():
    # lock children tasks
    logger.info('LAUNCH_TASK enqueue_update_subscriptions')
    subscriptions_to_update = SubscriptionStatus.objects.filter(
        subscription_last_updated__lte=timezone.now()-timedelta(minutes=30)
    )
    logger.info("Enqueueing {} subscriptions for updating".format(subscriptions_to_update))
    for sub in subscriptions_to_update:
        update_subscription(sub.pk)
    logger.info('FINISH_TASK enqueue_update_subscriptions')
