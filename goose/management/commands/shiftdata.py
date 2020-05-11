import argparse
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import dateparse

from goose.models import Count, DataClass, Value 


def timestamp(x):
    val = dateparse.parse_datetime(x)
    if x is None:
        raise ValueError(f'Not a valid ISO8601 timestamp: {f}')
    return val


class Command(BaseCommand):
    help = 'Include fresh submissions and discard old data'

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--max-periods',
                            type=int,
                            help='Max periods to keep (default: '
                                 'settings.GOOSE_MAX_PERIODS)')
        parser.add_argument('--timestamp',
                            type=timestamp,
                            help='Use the specified timestamp for new '
                                 'data (default: current time)')

    def handle(self, *args, **options) -> None:
        dt = options['timestamp'] or datetime.datetime.utcnow()
        keep_periods = (options['max_periods']
                        or settings.GOOSE_MAX_PERIODS)

        stamps = sorted(set(x[0] for x in Count.objects
                            .exclude(inclusion_time__exact=None)
                            .values_list('inclusion_time')))
        to_remove = stamps[:-keep_periods+1]

        with transaction.atomic():
            Count.objects.filter(inclusion_time__in=to_remove).delete()
            Value.objects.filter(count=None).delete()
            Count.objects.create(
                value=Value.objects.get_or_create(
                    data_class=DataClass.objects.get(name='stamp'),
                    value='')[0],
                count=1,
                inclusion_time=None)
            Count.objects.filter(inclusion_time__exact=None).update(
                inclusion_time=dt)
