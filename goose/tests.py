import datetime

from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from goose.models import Count, DataClass, Value


def count_to_tuple(count: Count) -> tuple:
    return (count.value.data_class.name,
            count.value.value,
            count.count,
            count.inclusion_time)


class SubmissionTests(TestCase):
    JSON_1 = {
        'goose-version': 1,
        'id': 'test1',
        'world': [
            'dev-libs/libfoo',
            'dev-libs/libbar',
            'sys-apps/frobnicate'
        ],
        'profile': 'default/linux/amd64/17.0'
    }

    JSON_2 = {
        'goose-version': 1,
        'id': 'test2',
        'world': [
            'dev-libs/libbar',
            'sys-apps/example',
        ],
        'profile': 'default/linux/amd64/17.1'
    }

    JSON_3 = {
        'goose-version': 1,
        'id': 'test3',
        'world': [
            'dev-libs/libfoo',
            'dev-libs/libbar',
        ],
        'profile': 'default/linux/amd64/17.0'
    }

    def test_new_submission(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('id', 'test1', 1, None),
                ('profile', 'default/linux/amd64/17.0', 1, None),
                ('world', 'dev-libs/libbar', 1, None),
                ('world', 'dev-libs/libfoo', 1, None),
                ('world', 'sys-apps/frobnicate', 1, None),
            ])

    def test_multiple_submissions(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_2)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_3)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('id', 'test1', 1, None),
                ('id', 'test2', 1, None),
                ('id', 'test3', 1, None),
                ('profile', 'default/linux/amd64/17.0', 2, None),
                ('profile', 'default/linux/amd64/17.1', 1, None),
                ('world', 'dev-libs/libbar', 3, None),
                ('world', 'dev-libs/libfoo', 2, None),
                ('world', 'sys-apps/example', 1, None),
                ('world', 'sys-apps/frobnicate', 1, None),
            ])

    def test_duplicate_submission(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 429)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('id', 'test1', 1, None),
                ('profile', 'default/linux/amd64/17.0', 1, None),
                ('world', 'dev-libs/libbar', 1, None),
                ('world', 'dev-libs/libfoo', 1, None),
                ('world', 'sys-apps/frobnicate', 1, None),
            ])

    def test_new_submission_with_existing_data(self) -> None:
        profile = DataClass.objects.get(name='profile')
        world = DataClass.objects.get(name='world')
        dt = datetime.datetime.utcnow()
        with transaction.atomic():
            Count.objects.create(
                value=Value.objects.create(
                    data_class=profile,
                    value='default/linux/amd64/17.0'),
                count=3,
                inclusion_time=dt)
            Count.objects.create(
                value=Value.objects.create(
                    data_class=world,
                    value='dev-libs/libfoo'),
                count=5,
                inclusion_time=dt)
            Count.objects.create(
                value=Value.objects.create(
                    data_class=world,
                    value='dev-libs/libbar'),
                count=2,
                inclusion_time=dt)
            Count.objects.create(
                value=Value.objects.create(
                    data_class=world,
                    value='dev-util/bar'),
                count=1,
                inclusion_time=dt)

        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('id', 'test1', 1, None),
                ('profile', 'default/linux/amd64/17.0', 1, None),
                ('profile', 'default/linux/amd64/17.0', 3, dt),
                ('world', 'dev-libs/libbar', 1, None),
                ('world', 'dev-libs/libbar', 2, dt),
                ('world', 'dev-libs/libfoo', 1, None),
                ('world', 'dev-libs/libfoo', 5, dt),
                ('world', 'dev-util/bar', 1, dt),
                ('world', 'sys-apps/frobnicate', 1, None),
            ])

    def test_bad_method(self) -> None:
        resp = self.client.get(reverse('submit'))
        self.assertEqual(resp.status_code, 405)

    def test_bad_content_type(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='text/plain',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 415)

    def test_malformed_json(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data='{"foo"')
        self.assertEqual(resp.status_code, 400)

    def test_missing_version(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data={'profile': 'foo',
                                     'id': 'testz'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Count.objects.all())

    def test_wrong_version(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data={'goose-version': 0,
                                     'profile': 'foo',
                                     'id': 'testz'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Count.objects.all())

    def test_missing_id(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data={'goose-version': 1,
                                     'profile': 'foo'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Count.objects.all())

    def test_wrong_type_profile(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data={'goose-version': 1,
                                     'id': 'testz',
                                     'profile': ['foo'],
                                     'world': [
                                         'dev-libs/foo',
                                         'dev-libs/bar',
                                     ]})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Count.objects.all())

    def test_wrong_type_world(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data={'goose-version': 1,
                                     'id': 'testz',
                                     'profile': 'foo',
                                     'world': 'dev-libs/foo'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Count.objects.all())

    def test_wrong_type_world_member(self) -> None:
        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data={'goose-version': 1,
                                     'id': 'testz',
                                     'profile': 'foo',
                                     'world': [
                                         'dev-libs/foo',
                                         4,
                                     ]})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Count.objects.all())
