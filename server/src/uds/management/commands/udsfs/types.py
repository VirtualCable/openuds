import stat
import time
import logging
import typing

logger = logging.getLogger(__name__)

class StatType(typing.NamedTuple):
    st_mode: int
    st_ctime: int = -1
    st_mtime: int = -1
    st_atime: int = -1
    st_nlink: int = 1

    def as_dict(self) -> typing.Dict[str, int]:
        return {
            'st_mode': self.st_mode,
            'st_ctime': self.st_ctime if self.st_ctime != -1 else int(time.time()),
            'st_mtime': self.st_mtime if self.st_mtime != -1 else int(time.time()),
            'st_atime': self.st_atime if self.st_atime != -1 else int(time.time()),
            'st_nlink': self.st_nlink
        }

class UDSFSInterface:
    """
    Base Class for UDS Info File system
    """
    def getattr(self, path: typing.List[str]) -> StatType:
        """
        Get file attributes. Path is the full path to the file, already splitted.
        """
        raise NotImplementedError

    def readdir(self, path: typing.List[str]) -> typing.List[str]:
        """
        Get a list of files in the directory. Path is the full path to the directory, already splitted.
        """
        raise NotImplementedError
    