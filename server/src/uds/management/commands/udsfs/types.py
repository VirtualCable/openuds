import stat
import time
import logging
import typing

logger = logging.getLogger(__name__)


class StatType(typing.NamedTuple):
    st_dev: int = -1
    st_ino: int = -1
    st_nlink: int = 1
    st_mode: int = stat.S_IFREG
    st_uid: int = -1
    st_gid: int = -1
    st_rdev: int = -1
    st_size: int = -1
    st_blksize: int = -1
    st_blocks: int = -1
    st_ctime: int = time.time_ns()
    st_mtime: int = time.time_ns()
    st_atime: int = time.time_ns()

    def as_dict(self) -> typing.Dict[str, int]:
        rst = {
            'st_mode': self.st_mode,
            'st_ctime': self.st_ctime,
            'st_mtime': self.st_mtime,
            'st_atime': self.st_atime,
            'st_nlink': self.st_nlink,
        }
        # Append optional fields
        if self.st_dev != -1:
            rst['st_dev'] = self.st_dev
        if self.st_ino != -1:
            rst['st_ino'] = self.st_ino
        if self.st_uid != -1:
            rst['st_uid'] = self.st_uid
        if self.st_gid != -1:
            rst['st_gid'] = self.st_gid
        if self.st_rdev != -1:
            rst['st_rdev'] = self.st_rdev
        if self.st_size != -1:
            rst['st_size'] = self.st_size
        if self.st_blksize != -1:
            rst['st_blksize'] = self.st_blksize
        if self.st_blocks != -1:
            rst['st_blocks'] = self.st_blocks

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

    def flush(self, path: typing.List[str]) -> None:  # pylint: disable=unused-argument
        return
