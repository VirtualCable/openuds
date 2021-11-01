import stat
import time
import logging
import typing

logger = logging.getLogger(__name__)


class StatType(typing.NamedTuple):
    st_mode: int = stat.S_IFREG
    st_size: int = -1
    st_ctime: int = time.time_ns()
    st_mtime: int = time.time_ns()
    st_atime: int = time.time_ns()
    st_nlink: int = 1

    def as_dict(self) -> typing.Dict[str, int]:
        rst = {
            'st_mode': self.st_mode,
            'st_ctime': self.st_ctime,
            'st_mtime': self.st_mtime,
            'st_atime': self.st_atime,
            'st_nlink': self.st_nlink
        }
        # Append optional fields
        if self.st_size != -1:
            rst['st_size'] = self.st_size
        return rst


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
    
    def read(self, path: typing.List[str], size: int, offset: int) -> bytes:
        """
        Read a file. Path is the full path to the file, already splitted.
        """
        raise NotImplementedError
