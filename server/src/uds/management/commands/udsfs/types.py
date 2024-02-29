# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

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

    def as_dict(self) -> dict[str, int]:
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

    def getattr(self, path: list[str]) -> StatType:
        """
        Get file attributes. Path is the full path to the file, already splitted.
        """
        raise NotImplementedError

    def readdir(self, path: list[str]) -> list[str]:
        """
        Get a list of files in the directory. Path is the full path to the directory, already splitted.
        """
        raise NotImplementedError

    def read(self, path: list[str], size: int, offset: int) -> bytes:
        """
        Read a file. Path is the full path to the file, already splitted.
        """
        raise NotImplementedError

    def flush(self, path: list[str]) -> None:  # pylint: disable=unused-argument
        return
