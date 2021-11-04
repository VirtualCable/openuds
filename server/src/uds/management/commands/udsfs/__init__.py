import errno
import stat
import os.path
import logging
import typing


from django.core.management.base import BaseCommand

from uds import models
from uds.core.util.fuse import FUSE, FuseOSError, Operations

from . import types

from . import events
from . import stats

logger = logging.getLogger(__name__)


class UDSFS(Operations):

    dispatchers: typing.ClassVar[typing.Dict[str, types.UDSFSInterface]] = {
        'events': events.EventFS(),
        'stats': stats.StatsFS(),
    }

    # Own stats are the service creation date and 2 hardlinks because of the root folder
    _own_stats = types.StatType(
        st_mode=(stat.S_IFDIR | 0o755), st_nlink=2 + len(dispatchers)
    )

    def __init__(self):
        pass

    def _dispatch(
        self, path: typing.Optional[str], operation: str, *args, **kwargs
    ) -> typing.Any:
        try:
            if path:
                path_parts = path.split('/')
                logger.debug('Dispatching %s for %s', operation, path_parts)
                if path_parts[1] in self.dispatchers:
                    return getattr(self.dispatchers[path_parts[1]], operation)(
                        path_parts[2:], *args, **kwargs
                    )
        except Exception as e:
            logger.error('Error while dispatching %s for %s: %s', operation, path, e)

        raise FuseOSError(errno.ENOENT)

    def getattr(
        self, path: typing.Optional[str], fh: typing.Any = None
    ) -> typing.Dict[str, int]:
        # If root folder, return service creation date
        if path == '/':
            return self._own_stats.as_dict()
        # If not root folder, split path to locate dispatcher and call it with the rest of the path
        attrs = typing.cast(types.StatType, self._dispatch(path, 'getattr')).as_dict()
        logger.debug('Attrs for %s: %s', path, attrs)
        return attrs

    def getxattr(self, path: str, name: str, position: int = 0) -> str:
        '''
        Get extended attribute for the given path. Right now, always returns an "empty" string
        '''
        logger.debug('Getting attr %s from %s (%s)', name, path, position)
        return ''

    def readdir(self, path: str, fh: typing.Any) -> typing.List[str]:
        '''
        Read directory, that is composed of the dispatcher names and the "dot" entries
        in case of the root folder, otherwise call the dispatcher with the rest of the path
        '''
        if path == '/':
            return ['.', '..'] + list(self.dispatchers.keys())
        return typing.cast(typing.List[str], self._dispatch(path, 'readdir'))

    def read(
        self, path: typing.Optional[str], size: int, offset: int, fh: typing.Any
    ) -> bytes:
        '''
        Reads the content of the "virtual" file
        '''
        return typing.cast(bytes, self._dispatch(path, 'read', size, offset))

    def flush(self, path: typing.Optional[str], fh: typing.Any) -> None:
        '''
        Flushes the content of the "virtual" file
        '''
        self._dispatch(path, 'flush')


class Command(BaseCommand):
    args = "<mod.name=value mod.name=value mod.name=value...>"
    help = "Updates configuration values. If mod is omitted, UDS will be used. Omit whitespaces betwen name, =, and value (they must be a single param)"

    def add_arguments(self, parser):
        parser.add_argument(
            'mount_point', type=str, help='Mount point for the FUSE filesystem'
        )
        parser.add_argument(
            '-d', '--debug', action='store_true', help='Enable debug logging'
        )

    def handle(self, *args, **options):
        logger.debug("Handling UDS FS")

        fuse = FUSE(UDSFS(), options['mount_point'], foreground=True, allow_other=True, debug=options['debug'])
