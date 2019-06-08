import logging
from django.core.cache import cache
logger=logging.getLogger(__name__)


def get_cached_column(
        cache_key,
        primary_key,
        model,
        col_name
):

    cached_field = cache.get(cache_key.format(primary_key))
    if cached_field:
        return cached_field

    # get from db
    obj = model.objects.filter(pk=primary_key).values_list(col_name, flat=True)

    if not len(obj):
        return None
    #logger.info("cache miss for {}.{}".format(model, col_name))

    cache.set(cache_key.format(primary_key), obj[0], timeout=86400)
    return obj[0]


def obj_exists_cached(
        cache_key,
        primary_key,
        model
):
    does_exist = cache.get(cache_key.format(primary_key))
    if does_exist:
        return True

    # check db
    exists = model.objects.filter(pk=primary_key).exists()
    if exists:
        cache.set(cache_key.format(primary_key), True, timeout=86400)
    return exists