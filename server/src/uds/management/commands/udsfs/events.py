import stat
import time
import typing
import logging

from . import types

logger = logging.getLogger(__name__)

class EventFS(types.UDSFSInterface):
    """
    Class to handle events fs in UDS.
    """
    _own_stats = types.StatType(st_mode=(stat.S_IFDIR | 0o755), st_nlink=1)

    def __init__(self):
        pass

    def getattr(self, path: typing.List[str]) -> types.StatType:
        if len(path) <= 1:
            return self._own_stats
        return types.StatType(st_mode=stat.S_IFREG | 0o444, st_nlink=1)

    def readdir(self, path: typing.List[str]) -> typing.List[str]:
        if len(path) <= 1:
            return ['.', '..']
        return []
