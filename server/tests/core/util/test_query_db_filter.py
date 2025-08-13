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
            last_execution=datetime(2025, 7, 12, 12, 0),
            next_execution=consts.NEVER,
            owner_server='server3',
            state=State.LAUNCHING,
        )

    def test_eq_query(self):
        result = exec_query("name eq 'hourly_job'", Scheduler.objects)
        self.assertEqual(result.count(), 1)
        first = result.first()
        assert first is not None
        self.assertEqual(first.name, 'hourly_job')

    def test_and_query(self):
        result = exec_query("owner_server eq 'server1' and frecuency gt 3600", Scheduler.objects)
        self.assertEqual(result.count(), 2)  # daily_job and weekly_job

    def test_or_query(self):
        result = exec_query(f"state eq '{State.RUNNING}' or frecuency lt 3600", Scheduler.objects)
        self.assertEqual(result.count(), 1)
        first = result.first()
        assert first is not None
        self.assertEqual(first.name, 'hourly_job')

    def test_func_startswith(self):
        results = exec_query("startswith(name, 'week')", Scheduler.objects)
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'weekly_job')

    def test_not_query(self):
        results = exec_query(f"not(state eq '{State.LAUNCHING}')", Scheduler.objects)
        self.assertEqual(results.count(), 3)
        self.assertFalse(results.filter(state=State.LAUNCHING).exists())

    def test_complex_and_or_combination(self):
        results = exec_query(
            f"(state eq '{State.FOR_EXECUTE}' and frecuency lt '{Scheduler.DAY}') or owner_server eq 'server3'",
            Scheduler.objects
        )
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'long_job')

        results = exec_query("endswith(owner_server, '1')", Scheduler.objects)
        self.assertEqual(results.count(), 2)  # daily_job & weekly_job

    def test_nested_not_and(self):
        result = exec_query(f"not(state eq '{State.FOR_EXECUTE}' and owner_server eq 'server1')", Scheduler.objects)
        self.assertEqual(result.count(), 2)
        names = {r.name for r in result}
        self.assertFalse('daily_job' in names and 'weekly_job' in names)

    def test_invalid_query_returns_empty(self):
        try:
            results = exec_query("frecuency >> 1000", Scheduler.objects)  # invalid syntax
            self.assertEqual(results.count(), 0)
        except Exception:
            self.fail("exec_query should handle invalid syntax gracefully")

    def test_field_comparison(self):
        # next_execution > last_execution
        results = exec_query("next_execution gt last_execution", Scheduler.objects)
        self.assertEqual(results.count(), 3)  # daily, hourly, weekly

        # last_execution < next_execution
        results = exec_query("last_execution lt next_execution", Scheduler.objects)
        self.assertEqual(results.count(), 3)

    def test_func_length(self):
        # name length == 10 (daily_job)
        results = exec_query("length(name) eq 10", Scheduler.objects)
        self.assertEqual(results.count(), 2)
        names = {r.name for r in results}
        assert names == {'hourly_job', 'weekly_job'}

    def test_func_tolower(self):
        # tolower(name) == 'daily_job'
        # Update the expected name to uppercase so test is for real
        Scheduler.objects.filter(name='daily_job').update(name='DAILY_JOB')
        results = exec_query("tolower(name) eq 'daily_job'", Scheduler.objects)
        self.assertEqual(results.count(), 1)

    def test_func_toupper(self):
        # toupper(name) == 'DAILY_JOB'
        results = exec_query("toupper(name) eq 'DAILY_JOB'", Scheduler.objects)
        self.assertEqual(results.count(), 1)

    def test_func_year(self):
        # year(last_execution) == 2025
        results = exec_query("year(last_execution) eq 2025", Scheduler.objects)
        self.assertEqual(results.count(), 4)

    def test_func_month(self):
        # month(last_execution) == 8
        results = exec_query("month(last_execution) eq 8", Scheduler.objects)
        self.assertEqual(results.count(), 3)

    def test_func_day(self):
        # day(last_execution) == 13
        results = exec_query("day(last_execution) eq 13", Scheduler.objects)
        self.assertEqual(results.count(), 2)  # daily_job & hourly_job
