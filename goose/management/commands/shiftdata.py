# (c) 2020 Michał Górny
# 2-clause BSD license

import argparse
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
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

        stamp_cls = DataClass.objects.get(name='stamp')

        last_update = (Count.objects.filter(value__data_class=stamp_cls)
                       .aggregate(models.Max('value__value'))
                       ['value__value__max'])
        if last_update is not None:
            # TODO: replace it with fromisoformat() when infra manages
            # to switch to py3.7
            delta = dt - datetime.datetime.strptime(
                last_update.split('.')[0], '%Y-%m-%dT%H:%M:%S')
            if delta < min_delay:
                raise CommandError(
                    f'shiftdata already called {delta} ago, min delay '
                    f'is set to {min_delay}')

        with transaction.atomic():
            Count.objects.filter(age__gte=keep_periods).delete()
            # TODO: can we prevent unnecessary manual cascade here?
            Value.objects.filter(count=None).delete()
            Count.objects.all().update(age=models.F('age')+1)
            Count.objects.create(
                value=Value.objects.create(
                    data_class=stamp_cls,
                    value=dt.isoformat()),
                count=1,
                age=1)
