# (c) 2020 Michał Górny
# 2-clause BSD license

import datetime
import unittest

from django.conf import settings
from django.core import management
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from goose.models import Count, DataClass, Value


class CountTuple(tuple):
    """A Count tuple that is sortable"""

    def to_sortable(self) -> tuple:
        """Return tuple used as a sort key"""
        return self[:-1] + (self[-1] is not None, self[-1])

    def __lt__(self,
               other: tuple
               ) -> bool:
        assert(isinstance(other, self.__class__))
        return self.to_sortable() < other.to_sortable()


def count_to_tuple(count: Count) -> tuple:
    return CountTuple(
        value_to_tuple(count.value)
        + (count.count,
           count.age))


def value_to_tuple(value: Value) -> tuple:
    return (value.data_class.name,
            value.value)


def create_stamp(dt: datetime.datetime) -> datetime.datetime:
    stamp = DataClass.objects.get(name='stamp')
    with transaction.atomic():
        Count.objects.create(
            value=Value.objects.create(
                data_class=stamp,
                value=dt.isoformat()),
            count=1,
            age=1)
    return dt


def create_data1(age: int) -> None:
    profile = DataClass.objects.get(name='profile')
    world = DataClass.objects.get(name='world')
    with transaction.atomic():
        Count.objects.create(
            value=Value.objects.get_or_create(
                data_class=profile,
                value='default/linux/amd64/17.0')[0],
            count=3,
            age=age)
        Count.objects.create(
            value=Value.objects.get_or_create(
                data_class=world,
                value='dev-libs/libfoo')[0],
            count=5,
            age=age)
        Count.objects.create(
            value=Value.objects.get_or_create(
                data_class=world,
                value='dev-libs/libbar')[0],
            count=2,
            age=age)
        Count.objects.create(
            value=Value.objects.get_or_create(
                data_class=world,
                value='dev-util/bar')[0],
            count=1,
            age=age)


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
                ('id', 'test1', 1, 0),
                ('profile', 'default/linux/amd64/17.0', 1, 0),
                ('world', 'dev-libs/libbar', 1, 0),
                ('world', 'dev-libs/libfoo', 1, 0),
                ('world', 'sys-apps/frobnicate', 1, 0),
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
                ('id', 'test1', 1, 0),
                ('id', 'test2', 1, 0),
                ('id', 'test3', 1, 0),
                ('profile', 'default/linux/amd64/17.0', 2, 0),
                ('profile', 'default/linux/amd64/17.1', 1, 0),
                ('world', 'dev-libs/libbar', 3, 0),
                ('world', 'dev-libs/libfoo', 2, 0),
                ('world', 'sys-apps/example', 1, 0),
                ('world', 'sys-apps/frobnicate', 1, 0),
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
                ('id', 'test1', 1, 0),
                ('profile', 'default/linux/amd64/17.0', 1, 0),
                ('world', 'dev-libs/libbar', 1, 0),
                ('world', 'dev-libs/libfoo', 1, 0),
                ('world', 'sys-apps/frobnicate', 1, 0),
            ])

    def test_new_submission_with_existing_data(self) -> None:
        create_data1(1)

        resp = self.client.put(reverse('submit'),
                               content_type='application/json',
                               data=self.JSON_1)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('id', 'test1', 1, 0),
                ('profile', 'default/linux/amd64/17.0', 1, 0),
                ('profile', 'default/linux/amd64/17.0', 3, 1),
                ('world', 'dev-libs/libbar', 1, 0),
                ('world', 'dev-libs/libbar', 2, 1),
                ('world', 'dev-libs/libfoo', 1, 0),
                ('world', 'dev-libs/libfoo', 5, 1),
                ('world', 'dev-util/bar', 1, 1),
                ('world', 'sys-apps/frobnicate', 1, 0),
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

    @unittest.expectedFailure
    def test_duplicate_submission_in_last_period(self) -> None:
        """
        Test that a last-period duplicate submission is accepted

        If a duplicate submission happens in the last period before
        removing the old data, we should accept it.  Otherwise, people
        will have to submit data not every N days but N+1 because
        of processing delay.
        """

        dt = datetime.datetime.utcnow()
        stamp = DataClass.objects.get(name='stamp')
        stamp_val = Value.objects.create(data_class=stamp, value='')
        stamps = []
        for i in range(settings.GOOSE_MAX_PERIODS - 1):
            Count.objects.create(
                value=stamp_val,
                count=1,
                inclusion_time=dt)
            stamps.append(('stamp', '', 1, dt))
            dt -= datetime.timedelta(days=1)

        ident = DataClass.objects.get(name='id')
        ident_val = Value.objects.create(data_class=ident,
                                         value='test1')
        Count.objects.create(
            value=ident_val,
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
                ('id', 'test1', 1, dt),
                ('profile', 'default/linux/amd64/17.0', 1, None),
            ]
            + list(reversed(stamps))
            + [
                ('world', 'dev-libs/libbar', 1, None),
                ('world', 'dev-libs/libfoo', 1, None),
                ('world', 'sys-apps/frobnicate', 1, None),
            ])


class ShiftDataTests(TestCase):
    def test_new_data(self) -> None:
        dt = datetime.datetime.utcnow()
        create_data1(0)
        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=dt,
                                    max_periods=2)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('profile', 'default/linux/amd64/17.0', 3, 1),
                ('stamp', dt.isoformat(), 1, 1),
                ('world', 'dev-libs/libbar', 2, 1),
                ('world', 'dev-libs/libfoo', 5, 1),
                ('world', 'dev-util/bar', 1, 1),
            ])

    def test_old_data(self) -> None:
        new_dt = datetime.datetime.utcnow()
        create_data1(1)
        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=new_dt,
                                    max_periods=2)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('profile', 'default/linux/amd64/17.0', 3, 2),
                ('stamp', new_dt.isoformat(), 1, 1),
                ('world', 'dev-libs/libbar', 2, 2),
                ('world', 'dev-libs/libfoo', 5, 2),
                ('world', 'dev-util/bar', 1, 2),
            ])

    def test_very_old_data(self) -> None:
        mid_dt = datetime.datetime.utcnow()
        new_dt = mid_dt + datetime.timedelta(days=1)
        create_data1(2)

        with self.assertNumQueries(11):
            management.call_command('shiftdata',
                                    timestamp=mid_dt,
                                    max_periods=2)
        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=new_dt,
                                    max_periods=2)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('stamp', mid_dt.isoformat(), 1, 2),
                ('stamp', new_dt.isoformat(), 1, 1),
            ])
        self.assertEqual(
            sorted(value_to_tuple(x) for x in Value.objects.all()),
            [
                ('stamp', mid_dt.isoformat()),
                ('stamp', new_dt.isoformat()),
            ])

    def test_prehistoric_data(self) -> None:
        mid_dt = datetime.datetime.utcnow()
        new_dt = mid_dt + datetime.timedelta(days=1)
        create_data1(3)
        create_data1(2)

        with self.assertNumQueries(11):
            management.call_command('shiftdata',
                                    timestamp=mid_dt,
                                    max_periods=2)
        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=new_dt,
                                    max_periods=2)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('stamp', mid_dt.isoformat(), 1, 2),
                ('stamp', new_dt.isoformat(), 1, 1),
            ])
        self.assertEqual(
            sorted(value_to_tuple(x) for x in Value.objects.all()),
            [
                ('stamp', mid_dt.isoformat()),
                ('stamp', new_dt.isoformat()),
            ])

    def test_mixed_data(self) -> None:
        mid_dt = datetime.datetime.utcnow()
        new_dt = mid_dt + datetime.timedelta(days=1)
        create_data1(1)
        create_data1(0)
        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=mid_dt,
                                    max_periods=2)

        create_data1(0)
        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=new_dt,
                                    max_periods=2)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('profile', 'default/linux/amd64/17.0', 3, 1),
                ('profile', 'default/linux/amd64/17.0', 3, 2),
                ('stamp', mid_dt.isoformat(), 1, 2),
                ('stamp', new_dt.isoformat(), 1, 1),
                ('world', 'dev-libs/libbar', 2, 1),
                ('world', 'dev-libs/libbar', 2, 2),
                ('world', 'dev-libs/libfoo', 5, 1),
                ('world', 'dev-libs/libfoo', 5, 2),
                ('world', 'dev-util/bar', 1, 1),
                ('world', 'dev-util/bar', 1, 2),
            ])

    def test_too_frequent(self) -> None:
        old_dt = datetime.datetime.utcnow()
        new_dt = old_dt + datetime.timedelta(hours=12)

        with self.assertNumQueries(9):
            management.call_command('shiftdata',
                                    timestamp=old_dt,
                                    max_periods=2)
        with self.assertNumQueries(2):
            with self.assertRaises(management.CommandError):
                management.call_command('shiftdata',
                                        timestamp=new_dt,
                                        max_periods=2)

        self.assertEqual(
            sorted(count_to_tuple(x) for x in Count.objects.all()),
            [
                ('stamp', old_dt.isoformat(), 1, 1),
            ])


class StatsJsonTests(TestCase):
    def test_one_submission(self) -> None:
        dt = create_stamp(datetime.datetime.utcnow())
        create_data1(1)

        with self.assertNumQueries(3):
            resp = self.client.get(reverse('stats_json'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'last-update': dt.isoformat(),
            'profile': {
                'default/linux/amd64/17.0': 3,
            },
            'world': {
                'dev-libs/libfoo': 5,
                'dev-libs/libbar': 2,
                'dev-util/bar': 1,
            },
        })

    def test_two_submissions(self) -> None:
        old_dt = create_stamp(datetime.datetime.utcnow())
        create_data1(2)
        new_dt = create_stamp(old_dt + datetime.timedelta(days=1))
        create_data1(1)

        with self.assertNumQueries(3):
            resp = self.client.get(reverse('stats_json'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'last-update': new_dt.isoformat(),
            'profile': {
                'default/linux/amd64/17.0': 6,
            },
            'world': {
                'dev-libs/libfoo': 10,
                'dev-libs/libbar': 4,
                'dev-util/bar': 2,
            },
        })

    def test_unprocessed_submission(self) -> None:
        create_data1(0)
        with self.assertNumQueries(3):
            resp = self.client.get(reverse('stats_json'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'last-update': None,
            'profile': {},
            'world': {},
        })

    def test_mixed(self) -> None:
        dt = create_stamp(datetime.datetime.utcnow())
        create_data1(1)
        create_data1(0)

        with self.assertNumQueries(3):
            resp = self.client.get(reverse('stats_json'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'last-update': dt.isoformat(),
            'profile': {
                'default/linux/amd64/17.0': 3,
            },
            'world': {
                'dev-libs/libfoo': 5,
                'dev-libs/libbar': 2,
                'dev-util/bar': 1,
            },
        })
