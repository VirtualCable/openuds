"""
Tests for the delay-after-create feature on the dynamic user service.

Lets external storage or cluster managers settle their affinity rules before
the broker asks the provider to power on the new VM.

The tests cover the broker side: that ``_create_queue_with_delay`` and
``_create_queue_l1_cache_with_delay`` insert the right number of NOP
operations, that ``DELAY_AFTER_CREATE_SECONDS`` is honoured, and that
setting the delay to zero keeps the queue untouched.
"""

from uds.core.services.generics.dynamic import userservice as dyn_userservice_mod
from uds.core.types import services as services_types


class _StubUserService(dyn_userservice_mod.DynamicUserService):
    '''Concrete DynamicUserService with the abstract methods stubbed out,
    so the queue helpers can be exercised without a real provider attached.
    '''

    DELAY_AFTER_CREATE_SECONDS = 0

    def __init__(self) -> None:  # type: ignore[no-super-call]
        # Skip the base __init__ on purpose: the real one wants an autoserializable
        # state we don't have here. The queue helpers don't read instance state.
        pass

    def op_create(self) -> None:  # type: ignore[override]
        return None

    def op_start(self) -> None:  # type: ignore[override]
        return None


def _stub(delay: int) -> _StubUserService:
    _StubUserService.DELAY_AFTER_CREATE_SECONDS = delay
    return _StubUserService()


def test_no_delay_keeps_queue_untouched() -> None:
    stub = _stub(0)
    assert stub._create_queue_with_delay() == list(
        dyn_userservice_mod.DynamicUserService._create_queue
    )
    assert stub._create_queue_l1_cache_with_delay() == list(
        dyn_userservice_mod.DynamicUserService._create_queue_l1_cache
    )


def test_ten_seconds_inserts_two_nops_before_start() -> None:
    stub = _stub(10)
    queue = stub._create_queue_with_delay()
    start_index = queue.index(services_types.Operation.START)
    inserted = queue[start_index - 2 : start_index]
    assert inserted == [services_types.Operation.NOP, services_types.Operation.NOP], (
        f"expected two NOPs before START, got {inserted!r}"
    )


def test_l1_cache_queue_also_gets_the_delay() -> None:
    stub = _stub(10)
    queue = stub._create_queue_l1_cache_with_delay()
    start_index = queue.index(services_types.Operation.START)
    inserted = queue[start_index - 2 : start_index]
    assert inserted == [services_types.Operation.NOP, services_types.Operation.NOP]


def test_delay_zero_or_negative_is_no_op() -> None:
    for value in (0, -1, -100):
        stub = _stub(value)
        assert stub._create_queue_with_delay() == list(
            dyn_userservice_mod.DynamicUserService._create_queue
        )
