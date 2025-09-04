import pytest
import gc
from django.db import connections


@pytest.fixture(autouse=True)
def close_all_db_connections():
    yield
    for conn in connections.all():
        try:
            conn.close()
        except Exception:
            pass


def pytest_sessionfinish(session: pytest.Session, exitstatus: pytest.ExitCode) -> None:
    """Al final de toda la suite, cerrar conexiones y forzar GC."""
    try:
        from django.db import connections

        for conn in connections.all():
            try:
                conn.close()
            except Exception:
                pass
    except ImportError:
        pass
    gc.collect()
