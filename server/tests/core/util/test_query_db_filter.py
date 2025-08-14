from datetime import datetime
import logging

from uds.models import Scheduler
from uds.core import consts
from uds.core.types.states import State

from uds.core.util.query_db_filter import exec_query  # Ajusta el path si necesario


from tests.utils.test import UDSTestCase

logger = logging.getLogger(__name__)


class DBQueryTests(UDSTestCase):
    def setUp(self) -> None:
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

    def test_eq_query(self) -> None:
        result = exec_query("name eq 'hourly_job'", Scheduler.objects)
        self.assertEqual(result.count(), 1)
        first = result.first()
        assert first is not None
        self.assertEqual(first.name, 'hourly_job')

    def test_and_query(self) -> None:
        result = exec_query("owner_server eq 'server1' and frecuency gt 3600", Scheduler.objects)
        self.assertEqual(result.count(), 2)  # daily_job and weekly_job

    def test_or_query(self) -> None:
        result = exec_query(f"state eq '{State.RUNNING}' or frecuency lt 3600", Scheduler.objects)
        self.assertEqual(result.count(), 1)
        first = result.first()
        assert first is not None
        self.assertEqual(first.name, 'hourly_job')

    def test_func_startswith(self) -> None:
        results = exec_query("startswith(name, 'week')", Scheduler.objects)
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'weekly_job')

    def test_not_query(self) -> None:
        results = exec_query(f"not(state eq '{State.LAUNCHING}')", Scheduler.objects)
        self.assertEqual(results.count(), 3)
        self.assertFalse(results.filter(state=State.LAUNCHING).exists())

    def test_complex_and_or_combination(self) -> None:
        results = exec_query(
            f"(state eq '{State.FOR_EXECUTE}' and frecuency lt '{Scheduler.DAY}') or owner_server eq 'server3'",
            Scheduler.objects,
        )
        self.assertEqual(results.count(), 1)
        first = results.first()
        assert first is not None
        self.assertEqual(first.name, 'long_job')

        results = exec_query("endswith(owner_server, '1')", Scheduler.objects)
        self.assertEqual(results.count(), 2)  # daily_job & weekly_job

    def test_nested_not_and(self) -> None:
        result = exec_query(
            f"not(state eq '{State.FOR_EXECUTE}' and owner_server eq 'server1')", Scheduler.objects
        )
        self.assertEqual(result.count(), 2)
        names = {r.name for r in result}
        self.assertFalse('daily_job' in names and 'weekly_job' in names)

    def test_invalid_query_returns_value_error(self) -> None:
        with self.assertRaises(ValueError):
            exec_query("frecuency >> 1000", Scheduler.objects)  # invalid syntax

    def test_field_comparison(self) -> None:
        # next_execution > last_execution
        results = exec_query("next_execution gt last_execution", Scheduler.objects)
        self.assertEqual(results.count(), 3)  # daily, hourly, weekly

        # last_execution < next_execution
        results = exec_query("last_execution lt next_execution", Scheduler.objects)
        self.assertEqual(results.count(), 3)

    def test_func_length(self) -> None:
        # name length == 10 (daily_job)
        results = exec_query("length(name) eq 10", Scheduler.objects)
        self.assertEqual(results.count(), 2)
        names = {r.name for r in results}
        assert names == {'hourly_job', 'weekly_job'}

    def test_func_tolower(self) -> None:
        # tolower(name) == 'daily_job'
        # Update the expected name to uppercase so test is for real
        Scheduler.objects.filter(name='daily_job').update(name='DAILY_JOB')
        results = exec_query("tolower(name) eq 'daily_job'", Scheduler.objects)
        self.assertEqual(results.count(), 1)

    def test_func_toupper(self) -> None:
        # toupper(name) == 'DAILY_JOB'
        results = exec_query("toupper(name) eq 'DAILY_JOB'", Scheduler.objects)
        self.assertEqual(results.count(), 1)

    def test_func_year(self) -> None:
        # year(last_execution) == 2025
        results = exec_query("year(last_execution) eq 2025", Scheduler.objects)
        self.assertEqual(results.count(), 4)

    def test_func_month(self) -> None:
        # month(last_execution) == 8
        results = exec_query("month(last_execution) eq 8", Scheduler.objects)
        self.assertEqual(results.count(), 3)

    def test_func_day(self) -> None:
        # day(last_execution) == 13
        results = exec_query("day(last_execution) eq 13", Scheduler.objects)
        self.assertEqual(results.count(), 2)  # daily_job & hourly_job

    def test_func_concat(self) -> None:
        results = exec_query(
            f"concat(name, ' - ', state) eq 'daily_job - {State.FOR_EXECUTE}'", Scheduler.objects
        )
        res = list(results)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, 'daily_job')

    def test_func_substring(self) -> None:
        results = exec_query("substring(name, 1, 4) eq 'aily'", Scheduler.objects)
        res = list(results)
        logger.info('Query executed: %s', results.query)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, 'daily_job')

    def test_func_floor(self) -> None:
        # Scheduler frecuency: DAY = 86400, HOUR = 3600, etc.
        result = exec_query("floor(frecuency) eq 3600", Scheduler.objects)
        res = list(result)
        logger.info('Query executed: %s', result.query)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, 'hourly_job')

    def test_func_round(self) -> None:
        # Assuming frecuency is exact, round should behave like floor here
        result = exec_query("round(frecuency) eq 604800", Scheduler.objects)
        res = list(result)
        logger.info('Query executed: %s', result.query)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, 'weekly_job')

    def test_func_ceiling(self) -> None:
        # Should match long_job with frecuency = 2592000
        result = exec_query("ceiling(frecuency) eq 2592000", Scheduler.objects)
        res = list(result)
        logger.info('Query executed: %s', result.query)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, 'long_job')

    def test_func_trim(self) -> None:
        # Add a scheduler with padded name to test trim
        Scheduler.objects.create(
            name='  hourly_job  ',
            frecuency=Scheduler.HOUR,
            last_execution=datetime(2025, 8, 13, 21, 0),
            next_execution=datetime(2025, 8, 13, 22, 0),
            owner_server='server4',
            state=State.FINISHED,
        )

        result = exec_query("trim(name) eq 'hourly_job'", Scheduler.objects)
        res = list(result)
        logger.info('Query executed: %s', result.query)
        self.assertEqual(len(res), 2)
        self.assertIn('server4', {r.owner_server for r in res})
