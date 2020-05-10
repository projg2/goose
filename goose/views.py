import json

from django.db import transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    )

from goose.models import DataClass, Value, Count


class HttpResponseUnsupportedMediaType(HttpResponse):
    status_code = 415


class HttpResponseTooManyRequests(HttpResponse):
    status_code = 429


class GooseDataError(Exception):
    pass


class GooseLimitError(Exception):
    pass


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


def submit(request: HttpRequest) -> HttpResponse:
    if request.method != 'PUT':
        return HttpResponseNotAllowed(['PUT'])
    if request.content_type != 'application/json':
        return HttpResponseUnsupportedMediaType()

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
                if cls.name not in data:
                    continue
                val = data[cls.name]
                if cls.data_type == DataClass.DataClassType.STRING:
                    if not isinstance(val, str):
                        raise GooseDataError(
                            f'Expected a single string for {cls.name}')
                    if cls.name == 'id':
                        try:
                            xval = Value.objects.get(data_class=cls,
                                                     value=val)
                        except Value.DoesNotExist:
                            pass
                        else:
                            if Count.objects.filter(value=xval):
                                raise GooseLimitError(
                                    f'Data for id={val} already submitted')
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
