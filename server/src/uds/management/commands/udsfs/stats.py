import stat
import calendar
import datetime
import typing
import logging

from uds import models
from uds.core.util.stats.events import EVENT_NAMES, getOwner

from . import types

logger = logging.getLogger(__name__)

LINELEN = 160

class StatsFS(types.UDSFSInterface):
    """
    Class to handle stats fs in UDS.
    """
    _directory_stats: typing.ClassVar[types.StatType] = types.StatType(
        st_mode=(stat.S_IFDIR | 0o755), st_nlink=1
    )
    _dispatchers: typing.Mapping[str, typing.Callable[[int, int], bytes]]

    def __init__(self) -> None:
        # Initialize _dispatchers
        self._dispatchers = {
            'events.csv': self._read_events,
            'pools.csv': self._read_pools,
        }


    def readdir(self, path: typing.List[str]) -> typing.List[str]:
        # If len(path) == 0, return the list of possible stats files (from _dispatchers)
        # else, raise an FileNotFoundError
        if len(path) == 0:
            return ['.', '..'] + list(self._dispatchers.keys())
        
        raise FileNotFoundError

    def getattr(self, path: typing.List[str]) -> types.StatType:
        if len(path) < 1:
            return StatsFS._directory_stats

        # Ensure that the path is valid
        if len(path) != 1:
            raise FileNotFoundError

        # Ensure that the path is a valid stats file
        if path[0] not in self._dispatchers:
            raise FileNotFoundError

        # Calculate the size of the file
        size = len(self._dispatchers[path[0]](0, 0))
        logger.debug('Size of %s: %s', path[0], size)

        return types.StatType(st_mode=(stat.S_IFREG | 0o755), st_nlink=1, st_size=size)

    def read(self, path: typing.List[str], size: int, offset: int) -> bytes:
        logger.debug('Reading data from %s: offset: %s, size: %s', path, offset, size)

        # Ensure that the path is valid
        if len(path) != 1:
            raise FileNotFoundError

        # Ensure that the path is a valid stats file
        if path[0] not in self._dispatchers:
            raise FileNotFoundError

        # Dispatch the read to the dispatcher
        data = self._dispatchers[path[0]](size, offset)
        logger.debug('Readed %s data length', len(data))
        return data

    # Dispatchers for different stats files
    def _read_events(self, size: int, offset: int) -> bytes:
        logger.debug('Reading events. offset: %s, size: %s', offset, size)
        # Get stats events from last 24 hours (in UTC) stamp is unix timestamp
        virtualFile = models.StatsEvents.getCSVHeader().encode() + b'\n'
        for record in models.StatsEvents.objects.filter(
            stamp__gte=calendar.timegm(datetime.datetime.utcnow().timetuple()) - 86400
        ):
            virtualFile += record.toCsv().encode() + b'\n'
        return virtualFile

    def _read_pools(self, size: int, offset: int) -> bytes:
        logger.debug('Reading pools. offset: %s, size: %s', offset, size)
        return b'Pools'
