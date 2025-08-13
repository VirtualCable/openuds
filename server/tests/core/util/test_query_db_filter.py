from datetime import datetime

from uds.models import Scheduler
from uds.core import consts
from uds.core.types.states import State

from uds.core.util.query_db_filter import exec_query  # Ajusta el path si necesario


from tests.utils.test import UDSTestCase


class SchedulerQueryTests(UDSTestCase):
    def setUp(self):
        Scheduler.objects.create(
            name='daily_job',
            frecuency=Scheduler.DAY,
            last_execution=datetime(2025, 8, 13, 12, 0),
            next_execution=datetime(2025, 8, 14, 12, 0),
            owner_server='server1',
            state=State.FOR_EXECUTE,
        )

        Scheduler.objects.create(
            name='hourly_job',
            frecuency=Scheduler.HOUR,
            last_execution=datetime(2025, 8, 13, 19, 0),
            next_execution=datetime(2025, 8, 13, 20, 0),
            owner_server='server2',
            state=State.RUNNING,
        )

        Scheduler.objects.create(
            name='weekly_job',
            frecuency=Scheduler.DAY * 7,
            last_execution=datetime(2025, 8, 7, 12, 0),
            next_execution=datetime(2025, 8, 14, 12, 0),
            owner_server='server1',
            state=State.FOR_EXECUTE,
        )

        Scheduler.objects.create(
            name='long_job',
            frecuency=Scheduler.DAY * 30,
            last_execution=datetime(2025, 7, 13, 12, 0),
            next_execution=consts.NEVER,
            owner_server='server3',
            state=State.LAUNCHING,
        )

    def test_eq_query(self):
        q = exec_query("name eq 'hourly_job'")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'hourly_job')

    def test_and_query(self):
        q = exec_query("owner_server eq 'server1' and frecuency gt 3600")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 2)  # daily_job and weekly_job

    def test_or_query(self):
        q = exec_query(f"state eq {State.RUNNING} or frecuency lt 3600")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'hourly_job')

    def test_func_startswith(self):
        q = exec_query("startswith(name, 'week')")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'weekly_job')

    def test_not_query(self):
        q = exec_query(f"not(state eq {State.LAUNCHING})")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 3)
        self.assertFalse(results.filter(state=State.LAUNCHING).exists())

    def test_complex_and_or_combination(self):
        q = exec_query(
            f"(state eq {State.FOR_EXECUTE} and frecuency lt {Scheduler.DAY}) or owner_server eq 'server3'"
        )
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'long_job')

        q = exec_query("endswith(owner_server, '1')")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 2)  # daily_job & weekly_job

    def test_nested_not_and(self):
        q = exec_query(f"not(state eq {State.FOR_EXECUTE} and owner_server eq 'server1')")
        results = Scheduler.objects.filter(q)
        self.assertEqual(results.count(), 2)
        names = {r.name for r in results}
        self.assertFalse('daily_job' in names and 'weekly_job' in names)

    def test_invalid_query_returns_empty(self):
        try:
            q = exec_query("frecuency >> 1000")  # invalid syntax
            results = Scheduler.objects.filter(q)
            self.assertEqual(results.count(), 0)
        except Exception:
            self.fail("exec_query should handle invalid syntax gracefully")
