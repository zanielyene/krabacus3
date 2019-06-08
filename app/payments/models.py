import uuid, waffle, logging
from django.utils import timezone

from django.db import models
from django.db.models import signals, Sum
from django.contrib.auth.models import User
from eve_api.models import EVEPlayerCharacter
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SubscriptionStatus(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, related_name="subscription", on_delete=models.CASCADE)

    # the below fields are all updated via check_subscription_payments
    active = models.BooleanField(default=False)
    credit_remaining = models.BigIntegerField(default = 0)
    credit_consumed = models.BigIntegerField(default = 0)
    subscription_last_updated = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return "Subscription for {}".format(self.user)

    @property
    def payments(self):
        return SubscriptionPayment.objects.filter(subscription=self).order_by('payment_read_time')

    @property
    def is_trial(self):
        return not self.payments.filter(is_trial_payment=False).exists()

    @property
    def time_remaining_hours(self):
        if not self.active:
            return 0
        uncharged_amount = self._calculate_charge(timezone.now())
        if self.credit_remaining < uncharged_amount:
            return 0
        actual_credit_remaining = self.credit_remaining - uncharged_amount
        hourly_price = int(settings.SUBSCRIPTION_PRICE_PER_MONTH / 30 / 24)

        return int(actual_credit_remaining/hourly_price)

    def _calculate_charge(self, time_end):
        hourly_price = int(settings.SUBSCRIPTION_PRICE_PER_MONTH / 30 / 24)
        hours_to_charge = (time_end - self.subscription_last_updated).total_seconds() / 3600
        return int(hours_to_charge * hourly_price)

    def check_subscription_payments(self):
        now = timezone.now()

        # update credit
        total_credit = SubscriptionPayment.objects.filter(subscription=self).aggregate(Sum('amount'))['amount__sum']
        if total_credit is None:
            total_credit = 0
        self.credit_remaining = total_credit - self.credit_consumed

        amount_to_charge = self._calculate_charge(now)
        if self.credit_remaining < amount_to_charge:
            # out of credit, disable account
            partial_charge = self.credit_remaining
            self.credit_consumed += partial_charge
            self.credit_remaining = 0
            if self.active:
                logger.info("Disabling subscription for {}, out of funds.".format(self.pk))
            self.active = False
        else:
            # charge account normally
            self.credit_remaining -= amount_to_charge
            self.credit_consumed += amount_to_charge
            if not self.active:
                logger.info("Enabling subscription for {}".format(self.pk))
            self.active = True
            logger.info("Deducting {} ISK from {}'s subscription to pay".format(amount_to_charge, self.user))
        self.subscription_last_updated = now
        self.save()

    @staticmethod
    def create_fresh_subscription(sender, instance, created, **kwargs):
        subscription, created = SubscriptionStatus.objects.get_or_create(user=instance)
        if created:
            if waffle.switch_is_active("enable-free-trial"):
                SubscriptionPayment.create_free_trial(subscription)
            subscription.check_subscription_payments()


signals.post_save.connect(SubscriptionStatus.create_fresh_subscription, sender=User)


class SubscriptionPayment(models.Model):
    subscription = models.ForeignKey(SubscriptionStatus, on_delete=models.CASCADE)
    is_trial_payment = models.BooleanField(default=False)
    amount = models.BigIntegerField()
    source_character = models.ForeignKey(EVEPlayerCharacter, on_delete=models.CASCADE, null=True)
    journal_id = models.BigIntegerField(db_index=True, default=0)
    payment_time_actual = models.DateTimeField(default=timezone.now)
    payment_read_time = models.DateTimeField(default=timezone.now)

    @staticmethod
    def exists(journal_id):
        """
        Cache-backed exists method.
        :param journal_id:
        :return:
        """
        exists = cache.get("payment_recorded_{}".format(journal_id))
        if exists is not None:
            return True
        else:
            exists_db = SubscriptionPayment.objects.filter(journal_id=journal_id).exists()
            if exists_db:
                # after 90 days we DGAF
                timeout = 86400 * 90
                cache.set("payment_recorded_{}".format(journal_id), True, timeout=timeout)
            return exists_db

    @staticmethod
    def create_free_trial(subscription_status):
        trial_payment = SubscriptionPayment(
            subscription = subscription_status,
            is_trial_payment = True,
            source_character=None,
            payment_time_actual = timezone.now(),
            payment_read_time = timezone.now(),
            amount = int(settings.SUBSCRIPTION_PRICE_PER_MONTH / 2)
        )
        trial_payment.save()
        return

