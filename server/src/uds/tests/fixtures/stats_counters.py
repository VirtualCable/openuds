import typing
import datetime
import random

from uds.core.util.stats import counters
from uds import models


def create_stats_counters(
    owner_type: int,
    owner_id: int,
    counter_type: int,
    since: datetime.datetime,
    to: datetime.datetime,
    number: int,
) -> typing.List[models.StatsCounters]:
    '''
    Create a list of counters with the given type, counter_type, since and to, save it in the database
    and return it
    '''
    # Convert datetime to unix timestamp
    since_stamp = int(since.timestamp())
    to_stamp = int(to.timestamp())

    # Calculate the time interval between each counter
    interval = (to_stamp - since_stamp) / number
    
    counters = []
    for i in range(number):
        counter = models.StatsCounters()
        counter.owner_id = owner_id
        counter.owner_type = owner_type
        counter.counter_type = counter_type
        counter.stamp = since_stamp + interval * i
        counter.value = i * 10
        # And add it to the list
        counters.append(counter)

    # Bulk create the counters
    models.StatsCounters.objects.bulk_create(counters)
    return counters

