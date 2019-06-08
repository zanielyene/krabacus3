import logging
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from dataclasses import dataclass
from django.apps import apps
from django.core.cache import cache
logger=logging.getLogger(__name__)


class TransactionLinkage(models.Model):
    id = models.BigAutoField(primary_key=True)

    source_transaction = models.ForeignKey("PlayerTransaction", related_name="source_transaction", on_delete=models.CASCADE)
    destination_transaction = models.ForeignKey("PlayerTransaction", related_name="destination_transaction",on_delete=models.CASCADE)
    quantity_linked = models.BigIntegerField()
    date_linked = models.DateTimeField(default=timezone.now)
    route = models.ForeignKey("TradingRoute", on_delete=models.CASCADE)

    class Meta:
        index_together = [
            ["route", "date_linked"]
        ]

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = timezone.now()
        return super(TransactionLinkage, self).save(*args, **kwargs)


@dataclass
class TransactionSource:
    fuzzy: bool
    unit_price: float
    total_price: float
    linkages : list


class PlayerTransaction(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    character = models.ForeignKey(EVEPlayerCharacter, on_delete=models.CASCADE)

    client_id = models.BigIntegerField()
    timestamp = models.DateTimeField()
    is_buy = models.BooleanField()
    is_personal = models.BooleanField()
    journal_ref_id = models.BigIntegerField()
    location = models.ForeignKey(Structure, on_delete=models.CASCADE)
    quantity = models.BigIntegerField()
    object_type = models.ForeignKey(ObjectType, on_delete=models.CASCADE)
    unit_price = models.FloatField()

    # we don't index these because we don't want the entire goddamn index rebuilt every time there's a change made
    quantity_without_known_source = models.BigIntegerField()
    quantity_without_known_destination = models.BigIntegerField()

    def __str__(self):
        return "Transaction #{}".format(self.pk)

    @staticmethod
    def exists(ccp_id):
        """
        Cache-backed exists method. Cache only hits for Structures we know exist.
        :param ccp_id:
        :return:
        """
        exists = cache.get("transaction_exists_%s" % ccp_id)
        if exists is not None:
            return True
        else:
            exists_db = PlayerTransaction.objects.filter(pk=ccp_id).exists()
            if exists_db:
                # after 90 days we DGAF
                timeout = 86400 * 90
                cache.set("transaction_exists_%s" % ccp_id, True, timeout=timeout)
            return exists_db

    def get_source_value(self, quantity, route):
        if quantity > self.quantity:
            raise Exception("somethings broken with {}".format(self.pk))

        linkages = TransactionLinkage.objects.filter(Q(destination_transaction=self) & Q(route=route))
        if not linkages:
            return None

        ret_links = []
        quant_accounted = 0
        sum_of_products = 0
        for link in linkages:
            quant_accounted += link.quantity_linked
            sum_of_products += link.quantity_linked * link.source_transaction.unit_price
            ret_links.append(link)

        fuzzy = False if quant_accounted == quantity else True
        unit_price = sum_of_products / quant_accounted

        if fuzzy:
            sum_of_products = quantity / quant_accounted * sum_of_products

        return TransactionSource(fuzzy, unit_price, sum_of_products, ret_links)


    class Meta:
        index_together = [
            ["location", "object_type", "character", "timestamp", "is_buy"]
        ]

    def _get_routes_that_apply_to_transaction(self):
        TradingRoute_lazy = apps.get_model('market', 'TradingRoute')
        routes = TradingRoute_lazy.objects.filter(
            destination_character = self.character,
            destination_structure = self.location
        )
        return routes

    def link_transactions(self):
        # todo: LOCK THE SHIT OUT OF THIS
        routes = self._get_routes_that_apply_to_transaction()
        older_than = self.timestamp

        new_links = []
        transactions_to_save = []
        attributed = 0

        for route in routes:
            transactions = PlayerTransaction.objects.filter(
                location=route.source_structure,
                object_type=self.object_type,
                character=route.source_character,
                timestamp__lte=older_than,
                quantity_without_known_destination__gt=0,
                is_buy=True,
            ).order_by('timestamp')

            for source_txn in transactions:
                if source_txn.quantity_without_known_destination >= self.quantity_without_known_source:
                    contribution = self.quantity_without_known_source
                else:
                    contribution = source_txn.quantity_without_known_destination

                self.quantity_without_known_source -= contribution
                source_txn.quantity_without_known_destination -= contribution
                attributed += contribution

                link = TransactionLinkage(
                    source_transaction = source_txn,
                    destination_transaction = self,
                    quantity_linked = contribution,
                    route = route
                )
                new_links.append(link)
                transactions_to_save.append(source_txn)

                if not self.quantity_without_known_source:
                    break

            if not self.quantity_without_known_source:
                break

        if transactions_to_save:
            logger.info("Successfully attributed {} units of transaction {}".format(attributed, self.pk))
            with transaction.atomic():
                self.save()
                for t in transactions_to_save:
                    t.save()

                TransactionLinkage.objects.bulk_create(new_links)

