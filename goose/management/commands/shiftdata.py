import argparse
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import dateparse

from goose.models import Count, DataClass, Value


def timedelta(x):
    val = dateparse.parse_timedelta(x)
    if x is None:
        raise ValueError(f'Not a valid timedelta: {x}')
    return val


def timestamp(x):
    val = dateparse.parse_datetime(x)
    if x is None:
        raise ValueError(f'Not a valid ISO8601 timestamp: {x}')
    return val


class Command(BaseCommand):
    help = 'Include fresh submissions and discard old data'

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--max-periods',
                            type=int,
                            help='Max periods to keep (default: '
                                 'settings.GOOSE_MAX_PERIODS)')
        parser.add_argument('--min-delay',
                            type=timedelta,
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
        min_delay = (options['min_delay']
                     or settings.GOOSE_MIN_UPDATE_DELAY)

        stamps = sorted(set(x[0] for x in Count.objects
                            .filter(inclusion_time__isnull=False)
                            .values_list('inclusion_time')))
        if stamps:
            if dt - stamps[-1] < min_delay:
                raise CommandError(
                    'shiftdata already called {dt - stamps[-1]} ago, '
                    'min delay is set to {min_delay}')
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
            Count.objects.filter(inclusion_time__isnull=True).update(
                inclusion_time=dt)
