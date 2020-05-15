# (c) 2020 Michał Górny
# 2-clause BSD license

import ipaddress
import itertools
import json
import random

from pathlib import Path

from django.conf import settings
from django.db import models, transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    )
from django.views.decorators import http as decorators_http

from goose.models import DataClass, Value, Count


class HttpResponseUnsupportedMediaType(HttpResponse):
    status_code = 415


class HttpResponseTooManyRequests(HttpResponse):
    status_code = 429


class GooseDataError(Exception):
    pass


class GooseLimitError(Exception):
    pass


MAX_COUNT = {
    'id': 1,
    'ip': settings.GOOSE_MAX_SUBMISSIONS_PER_IP,
}


@decorators_http.require_http_methods(['GET', 'HEAD'])
def index(request: HttpRequest) -> HttpResponse:
    with (Path(__file__).parent / '..' / 'README.rst').open() as f:
        body = f.read().splitlines()

    assert body[:3] == ['=====', 'GOOSE', '=====']
    o_adjs = ['Optimized', 'Official', 'Oleophobic', 'Omnipotent',
              'Omnivorous', 'Online', 'Open', 'Ordinary', 'Orderly']
    e_nouns = ['Edifice', 'Emporium', 'Engine', 'Establishment',
               'Excavator', 'Extractor']
    oo_choice = ' '.join(random.sample(o_adjs, 2))
    e_choice = random.choice(e_nouns)
    body[1] += f': Gentoo {oo_choice} Statistic {e_choice}'
    body[0] = len(body[1]) * '='
    body[2] = body[0]

    return HttpResponse('\n'.join(body),
                        content_type='text/plain')


def add_data(data_cls: DataClass, value: str) -> None:
    xval, _ = Value.objects.get_or_create(
        data_class=data_cls,
        value=value)
    count, created = Count.objects.get_or_create(
        value=xval,
        inclusion_time=None,
        defaults={'count': 1})
    if not created:
        count.count += 1
        count.save()


@decorators_http.require_http_methods(['PUT'])
def submit(request: HttpRequest) -> HttpResponse:
    if request.content_type != 'application/json':
        return HttpResponseUnsupportedMediaType()

    ipaddr = ipaddress.ip_address(request.META['REMOTE_ADDR'])
    if ipaddr.version == 6:
        # if it's 6to4 or alike, map to the IPv4 address
        if ipaddr.ipv4_mapped:
            ipaddr = ipaddr.ipv4_mapped
        elif ipaddr.sixtofour:
            ipaddr = ipaddr.sixtofour
        elif ipaddr.teredo:
            ipaddr = ipaddr.teredo[1]
        else:
            # otherwise, limit per /64 prefix
            ipaddr = ipaddress.IPv6Address(
                int(ipaddr) & ~0xffffffffffffffff)
            # this is going to raise an exception if we cleared it wrong
            assert ipaddress.IPv6Network((ipaddr, 64))

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            raise GooseDataError('Malformed JSON')
        if data.get('goose-version') != 1:
            raise GooseDataError(
                'Unsupported goose-version or missing')
        if 'id' not in data:
            raise GooseDataError('id field missing')

        with transaction.atomic():
            for cls in DataClass.objects.all():
                if cls.name == 'ip':
                    val = str(ipaddr)
                elif cls.name in data:
                    val = data[cls.name]
                else:
                    continue

                if cls.data_type == DataClass.DataClassType.STRING:
                    if not isinstance(val, str):
                        raise GooseDataError(
                            f'Expected a single string for {cls.name}')
                    if cls.name in ('id', 'ip'):
                        try:
                            xval = Value.objects.get(data_class=cls,
                                                     value=val)
                        except Value.DoesNotExist:
                            pass
                        else:
                            cval = (Count.objects.filter(value=xval)
                                    .aggregate(models.Sum('count'))
                                    ['count__sum'])
                            max_count = MAX_COUNT[cls.name]
                            if cval >= max_count:
                                raise GooseLimitError(
                                    f'No more than {max_count} '
                                    f'submissions permitted per '
                                    f'{cls.name}={val}')
                    add_data(cls, val)
                elif cls.data_type == DataClass.DataClassType.STRING_ARRAY:
                    if (not isinstance(val, list)
                            or not all(isinstance(x, str) for x in val)):
                        raise GooseDataError(
                            f'Expected a list of strings for {cls.name}')
                    for x in val:
                        add_data(cls, x)
                else:
                    assert False, 'incorrect data_type'
    except GooseDataError as e:
        return HttpResponseBadRequest(f'{e}\n',
                                      content_type='text/plain')
    except GooseLimitError as e:
        return HttpResponseTooManyRequests(f'{e}\n',
                                           content_type='text/plain')

    return HttpResponse('Thank you, data added!\n',
                        content_type='text/plain')


@decorators_http.require_http_methods(['GET', 'HEAD'])
def stats_json(request: HttpRequest) -> HttpResponse:
    counts = (
        Value.objects
        .select_related('data_class')
        .filter(data_class__public=True)
        .annotate(
            total_count=models.Sum(
                'count__count',
                filter=models.Q(count__inclusion_time__isnull=False))))
    ret = dict(
        (g.name, dict((x.value, x.total_count) for x in vals
                      if x.total_count))
        for g, vals in itertools.groupby(counts,
                                         key=lambda x: x.data_class))
    ret['last-update'] = (
        Count.objects.aggregate(models.Min('inclusion_time'))
        ['inclusion_time__min'])
    return JsonResponse(ret)
