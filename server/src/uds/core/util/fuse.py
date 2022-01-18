# Copyright (c) 2012 Terence Honles <terence@honles.com> (maintainer)
# Copyright (c) 2008 Giorgos Verigakis <verigak@gmail.com> (author)
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Modified to add type checking, fix bugs, etc.. by dkmaster@dkmon.com

import sys
import os
import ctypes
import errno
import typing
import warnings
import logging

from ctypes.util import find_library
from platform import machine, system
from signal import signal, SIGINT, SIG_DFL
from stat import S_IFDIR
from functools import partial

logger = logging.getLogger(__name__)
_system = system()
_machine = machine()

c_win_long: typing.Type = ctypes.c_int32
c_win_ulong: typing.Type = ctypes.c_uint32

if _system == 'Windows':
    # NOTE:
    #
    # sizeof(long)==4 on Windows 32-bit and 64-bit
    # sizeof(long)==4 on Cygwin 32-bit and ==8 on Cygwin 64-bit
    #
    # We have to fix up c_long and c_ulong so that it matches the
    # Cygwin (and UNIX) sizes when run on Windows.
    import sys

    if sys.maxsize > 0xFFFFFFFF:
        c_win_long = ctypes.c_int64
        c_win_ulong = ctypes.c_uint64

if _system == 'Windows' or _system.startswith('CYGWIN'):

    class c_timespec(ctypes.Structure):  # type: ignore
        _fields_ = [('tv_sec', c_win_long), ('tv_nsec', c_win_long)]


else:

    class c_timespec(ctypes.Structure):  # type: ignore
        _fields_ = [('tv_sec', ctypes.c_long), ('tv_nsec', ctypes.c_long)]


class c_utimbuf(ctypes.Structure):
    _fields_ = [('actime', c_timespec), ('modtime', c_timespec)]


class c_stat(ctypes.Structure):
    pass  # Platform dependent


_libfuse_path = os.environ.get('FUSE_LIBRARY_PATH')
if not _libfuse_path:
    if _system == 'Darwin':
        # libfuse dependency
        _libiconv = ctypes.CDLL(find_library('iconv'), ctypes.RTLD_GLOBAL)

        _libfuse_path = (
            find_library('fuse4x') or find_library('osxfuse') or find_library('fuse')
        )
    elif _system == 'Windows':
        try:
            import _winreg as reg  # type: ignore
        except ImportError:
            import winreg as reg  # type: ignore

        def Reg32GetValue(rootkey, keyname, valname):
            key, val = None, None
            try:
                key = reg.OpenKey(  # type: ignore
                    rootkey, keyname, 0, reg.KEY_READ | reg.KEY_WOW64_32KEY  # type: ignore
                )
                val = str(reg.QueryValueEx(key, valname)[0])  # type: ignore
            except WindowsError:  # type: ignore
                pass
            finally:
                if key is not None:
                    reg.CloseKey(key)  # type: ignore
            return val

        _libfuse_path = Reg32GetValue(
            reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WinFsp", r"InstallDir"  # type: ignore
        )
        if _libfuse_path:
            _libfuse_path += r"bin\winfsp-%s.dll" % (
                "x64" if sys.maxsize > 0xFFFFFFFF else "x86"
            )
    else:
        _libfuse_path = find_library('fuse')

if not _libfuse_path:
    raise EnvironmentError('Unable to find libfuse')
else:
    _libfuse = ctypes.CDLL(_libfuse_path)

if _system == 'Darwin' and hasattr(_libfuse, 'macfuse_version'):
    _system = 'Darwin-MacFuse'


c_dev_t: typing.Type
c_fsblkcnt_t: typing.Type
c_fsfilcnt_t: typing.Type
c_gid_t: typing.Type
c_mode_t: typing.Type
c_off_t: typing.Type
c_pid_t: typing.Type
c_uid_t: typing.Type
setxattr_t: typing.Type
getxattr_t: typing.Type

if _system in ('Darwin', 'Darwin-MacFuse', 'FreeBSD'):
    ENOTSUP = 45

    c_dev_t = ctypes.c_int32
    c_fsblkcnt_t = ctypes.c_ulong
    c_fsfilcnt_t = ctypes.c_ulong
    c_gid_t = ctypes.c_uint32
    c_mode_t = ctypes.c_uint16
    c_off_t = ctypes.c_int64
    c_pid_t = ctypes.c_int32
    c_uid_t = ctypes.c_uint32
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
        ctypes.c_int,
        ctypes.c_uint32,
    )
    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
        ctypes.c_uint32,
    )
    if _system == 'Darwin':
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint16),
            ('st_ino', ctypes.c_uint64),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_birthtimespec', c_timespec),
            ('st_size', c_off_t),
            ('st_blocks', ctypes.c_int64),
            ('st_blksize', ctypes.c_int32),
            ('st_flags', ctypes.c_int32),
            ('st_gen', ctypes.c_int32),
            ('st_lspare', ctypes.c_int32),
            ('st_qspare', ctypes.c_int64),
        ]
    else:
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_uint32),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint16),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_size', c_off_t),
            ('st_blocks', ctypes.c_int64),
            ('st_blksize', ctypes.c_int32),
        ]
elif _system == 'Linux':
    ENOTSUP = 95

    c_dev_t = ctypes.c_ulonglong
    c_fsblkcnt_t = ctypes.c_ulonglong
    c_fsfilcnt_t = ctypes.c_ulonglong
    c_gid_t = ctypes.c_uint
    c_mode_t = ctypes.c_uint
    c_off_t = ctypes.c_longlong
    c_pid_t = ctypes.c_int
    c_uid_t = ctypes.c_uint
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
        ctypes.c_int,
    )

    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
    )

    if _machine == 'x86_64':
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_ulong),
            ('st_nlink', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('__pad0', ctypes.c_int),
            ('st_rdev', c_dev_t),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_long),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
        ]
    elif _machine == 'mips':
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('__pad1_1', ctypes.c_ulong),
            ('__pad1_2', ctypes.c_ulong),
            ('__pad1_3', ctypes.c_ulong),
            ('st_ino', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_ulong),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('__pad2_1', ctypes.c_ulong),
            ('__pad2_2', ctypes.c_ulong),
            ('st_size', c_off_t),
            ('__pad3', ctypes.c_ulong),
            ('st_atimespec', c_timespec),
            ('__pad4', ctypes.c_ulong),
            ('st_mtimespec', c_timespec),
            ('__pad5', ctypes.c_ulong),
            ('st_ctimespec', c_timespec),
            ('__pad6', ctypes.c_ulong),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_long),
            ('__pad7_1', ctypes.c_ulong),
            ('__pad7_2', ctypes.c_ulong),
            ('__pad7_3', ctypes.c_ulong),
            ('__pad7_4', ctypes.c_ulong),
            ('__pad7_5', ctypes.c_ulong),
            ('__pad7_6', ctypes.c_ulong),
            ('__pad7_7', ctypes.c_ulong),
            ('__pad7_8', ctypes.c_ulong),
            ('__pad7_9', ctypes.c_ulong),
            ('__pad7_10', ctypes.c_ulong),
            ('__pad7_11', ctypes.c_ulong),
            ('__pad7_12', ctypes.c_ulong),
            ('__pad7_13', ctypes.c_ulong),
            ('__pad7_14', ctypes.c_ulong),
        ]
    elif _machine == 'ppc':
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_ulonglong),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('__pad2', ctypes.c_ushort),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_longlong),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
        ]
    elif _machine == 'ppc64' or _machine == 'ppc64le':
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_ulong),
            ('st_nlink', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('__pad', ctypes.c_uint),
            ('st_rdev', c_dev_t),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_long),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
        ]
    elif _machine == 'aarch64':
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('st_ino', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('__pad1', ctypes.c_ulong),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_int),
            ('__pad2', ctypes.c_int),
            ('st_blocks', ctypes.c_long),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
        ]
    else:
        # i686, use as fallback for everything else
        c_stat._fields_ = [
            ('st_dev', c_dev_t),
            ('__pad1', ctypes.c_ushort),
            ('__st_ino', ctypes.c_ulong),
            ('st_mode', c_mode_t),
            ('st_nlink', ctypes.c_uint),
            ('st_uid', c_uid_t),
            ('st_gid', c_gid_t),
            ('st_rdev', c_dev_t),
            ('__pad2', ctypes.c_ushort),
            ('st_size', c_off_t),
            ('st_blksize', ctypes.c_long),
            ('st_blocks', ctypes.c_longlong),
            ('st_atimespec', c_timespec),
            ('st_mtimespec', c_timespec),
            ('st_ctimespec', c_timespec),
            ('st_ino', ctypes.c_ulonglong),
        ]
elif _system == 'Windows' or _system.startswith('CYGWIN'):
    ENOTSUP = 129 if _system == 'Windows' else 134
    c_dev_t = ctypes.c_uint
    c_fsblkcnt_t = c_win_ulong
    c_fsfilcnt_t = c_win_ulong
    c_gid_t = ctypes.c_uint
    c_mode_t = ctypes.c_uint
    c_off_t = ctypes.c_longlong
    c_pid_t = ctypes.c_int
    c_uid_t = ctypes.c_uint
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
        ctypes.c_int,
    )
    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
    )
    c_stat._fields_ = [
        ('st_dev', c_dev_t),
        ('st_ino', ctypes.c_ulonglong),
        ('st_mode', c_mode_t),
        ('st_nlink', ctypes.c_ushort),
        ('st_uid', c_uid_t),
        ('st_gid', c_gid_t),
        ('st_rdev', c_dev_t),
        ('st_size', c_off_t),
        ('st_atimespec', c_timespec),
        ('st_mtimespec', c_timespec),
        ('st_ctimespec', c_timespec),
        ('st_blksize', ctypes.c_int),
        ('st_blocks', ctypes.c_longlong),
        ('st_birthtimespec', c_timespec),
    ]
else:
    raise NotImplementedError('%s is not supported.' % _system)


if _system == 'FreeBSD':
    c_fsblkcnt_t = ctypes.c_uint64
    c_fsfilcnt_t = ctypes.c_uint64
    setxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
        ctypes.c_int,
    )

    getxattr_t = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_size_t,
    )

    class c_statvfs(ctypes.Structure):  # type: ignore
        _fields_ = [
            ('f_bavail', c_fsblkcnt_t),
            ('f_bfree', c_fsblkcnt_t),
            ('f_blocks', c_fsblkcnt_t),
            ('f_favail', c_fsfilcnt_t),
            ('f_ffree', c_fsfilcnt_t),
            ('f_files', c_fsfilcnt_t),
            ('f_bsize', ctypes.c_ulong),
            ('f_flag', ctypes.c_ulong),
            ('f_frsize', ctypes.c_ulong),
        ]


elif _system == 'Windows' or _system.startswith('CYGWIN'):

    class c_statvfs(ctypes.Structure):  # type: ignore
        _fields_ = [
            ('f_bsize', c_win_ulong),
            ('f_frsize', c_win_ulong),
            ('f_blocks', c_fsblkcnt_t),
            ('f_bfree', c_fsblkcnt_t),
            ('f_bavail', c_fsblkcnt_t),
            ('f_files', c_fsfilcnt_t),
            ('f_ffree', c_fsfilcnt_t),
            ('f_favail', c_fsfilcnt_t),
            ('f_fsid', c_win_ulong),
            ('f_flag', c_win_ulong),
            ('f_namemax', c_win_ulong),
        ]


else:

    class c_statvfs(ctypes.Structure):  # type: ignore
        _fields_ = [
            ('f_bsize', ctypes.c_ulong),
            ('f_frsize', ctypes.c_ulong),
            ('f_blocks', c_fsblkcnt_t),
            ('f_bfree', c_fsblkcnt_t),
            ('f_bavail', c_fsblkcnt_t),
            ('f_files', c_fsfilcnt_t),
            ('f_ffree', c_fsfilcnt_t),
            ('f_favail', c_fsfilcnt_t),
            ('f_fsid', ctypes.c_ulong),
            # ('unused', ctypes.c_int),
            ('f_flag', ctypes.c_ulong),
            ('f_namemax', ctypes.c_ulong),
        ]


if _system == 'Windows' or _system.startswith('CYGWIN'):

    class fuse_file_info(ctypes.Structure):  # type: ignore
        _fields_ = [
            ('flags', ctypes.c_int),
            ('fh_old', ctypes.c_int),
            ('writepage', ctypes.c_int),
            ('direct_io', ctypes.c_uint, 1),
            ('keep_cache', ctypes.c_uint, 1),
            ('flush', ctypes.c_uint, 1),
            ('padding', ctypes.c_uint, 29),
            ('fh', ctypes.c_uint64),
            ('lock_owner', ctypes.c_uint64),
        ]


else:

    class fuse_file_info(ctypes.Structure):  # type: ignore
        _fields_ = [
            ('flags', ctypes.c_int),
            ('fh_old', ctypes.c_ulong),
            ('writepage', ctypes.c_int),
            ('direct_io', ctypes.c_uint, 1),
            ('keep_cache', ctypes.c_uint, 1),
            ('flush', ctypes.c_uint, 1),
            ('nonseekable', ctypes.c_uint, 1),
            ('flock_release', ctypes.c_uint, 1),
            ('padding', ctypes.c_uint, 27),
            ('fh', ctypes.c_uint64),
            ('lock_owner', ctypes.c_uint64),
        ]


class FuseContext(ctypes.Structure):
    _fields_ = [
        ('fuse', ctypes.c_voidp),  # type: ignore
        ('uid', c_uid_t),
        ('gid', c_gid_t),
        ('pid', c_pid_t),
        ('private_data', ctypes.c_voidp),  # type: ignore
    ]


_libfuse.fuse_get_context.restype = ctypes.POINTER(FuseContext)


class FuseOperations(ctypes.Structure):
    _fields_ = [
        (
            'getattr',
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(c_stat)),
        ),
        (
            'readlink',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_byte),
                ctypes.c_size_t,
            ),
        ),
        ('getdir', ctypes.c_voidp),  # type: ignore  # Deprecated, use readdir
        ('mknod', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, c_mode_t, c_dev_t)),
        ('mkdir', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, c_mode_t)),
        ('unlink', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p)),
        ('rmdir', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p)),
        ('symlink', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p)),
        ('rename', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p)),
        ('link', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p)),
        ('chmod', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, c_mode_t)),
        ('chown', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, c_uid_t, c_gid_t)),
        ('truncate', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, c_off_t)),
        ('utime', ctypes.c_voidp),  # type: ignore   # Deprecated, use utimens
        (
            'open',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'read',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_byte),
                ctypes.c_size_t,
                c_off_t,
                ctypes.POINTER(fuse_file_info),
            ),
        ),
        (
            'write',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_byte),
                ctypes.c_size_t,
                c_off_t,
                ctypes.POINTER(fuse_file_info),
            ),
        ),
        (
            'statfs',
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(c_statvfs)),
        ),
        (
            'flush',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'release',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'fsync',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.POINTER(fuse_file_info),
            ),
        ),
        ('setxattr', setxattr_t),
        ('getxattr', getxattr_t),
        (
            'listxattr',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_byte),
                ctypes.c_size_t,
            ),
        ),
        (
            'removexattr',
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p),
        ),
        (
            'opendir',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'readdir',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_voidp,  # type: ignore
                ctypes.CFUNCTYPE(
                    ctypes.c_int,
                    ctypes.c_voidp,  # type: ignore
                    ctypes.c_char_p,
                    ctypes.POINTER(c_stat),
                    c_off_t,
                ),
                c_off_t,
                ctypes.POINTER(fuse_file_info),
            ),
        ),
        (
            'releasedir',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'fsyncdir',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.POINTER(fuse_file_info),
            ),
        ),
        ('init', ctypes.CFUNCTYPE(ctypes.c_voidp, ctypes.c_voidp)),  # type: ignore
        ('destroy', ctypes.CFUNCTYPE(ctypes.c_voidp, ctypes.c_voidp)),  # type: ignore
        ('access', ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int)),
        (
            'create',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, c_mode_t, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'ftruncate',
            ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_char_p, c_off_t, ctypes.POINTER(fuse_file_info)
            ),
        ),
        (
            'fgetattr',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(c_stat),
                ctypes.POINTER(fuse_file_info),
            ),
        ),
        (
            'lock',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(fuse_file_info),
                ctypes.c_int,
                ctypes.c_voidp,  # type: ignore
            ),
        ),
        (
            'utimens',
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(c_utimbuf)),
        ),
        (
            'bmap',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_ulonglong),
            ),
        ),
        ('flag_nullpath_ok', ctypes.c_uint, 1),
        ('flag_nopath', ctypes.c_uint, 1),
        ('flag_utime_omit_ok', ctypes.c_uint, 1),
        ('flag_reserved', ctypes.c_uint, 29),
        (
            'ioctl',
            ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.POINTER(fuse_file_info),
                ctypes.c_uint,
                ctypes.c_void_p,
            ),
        ),
    ]


def time_of_timespec(ts: c_timespec, use_ns=False):
    return ts.tv_sec * 10 ** 9 + ts.tv_nsec  # type: ignore


def set_st_attrs(st: c_stat, attrs: typing.Mapping[str, int]) -> None:
    for key, val in attrs.items():
        if key in ('st_atime', 'st_mtime', 'st_ctime', 'st_birthtime'):
            timespec: typing.Optional[c_timespec] = getattr(st, key + 'spec', None)
            if timespec is None:
                continue

            timespec.tv_sec, timespec.tv_nsec = divmod(int(val), 10 ** 9)
        elif hasattr(st, key):
            setattr(st, key, val)


def fuse_get_context():
    'Returns a (uid, gid, pid) tuple'

    ctxp = _libfuse.fuse_get_context()
    ctx = ctxp.contents
    return ctx.uid, ctx.gid, ctx.pid


def fuse_exit():
    '''
    This will shutdown the FUSE mount and cause the call to FUSE(...) to
    return, similar to sending SIGINT to the process.

    Flags the native FUSE session as terminated and will cause any running FUSE
    event loops to exit on the next opportunity. (see fuse.c::fuse_exit)
    '''
    fuse_ptr = ctypes.c_void_p(_libfuse.fuse_get_context().contents.fuse)
    _libfuse.fuse_exit(fuse_ptr)


class FuseOSError(OSError):
    def __init__(self, errno):
        super(FuseOSError, self).__init__(errno, os.strerror(errno))


class FUSE:
    '''
    This class is the lower level interface and should not be subclassed under
    normal use. Its methods are called by fuse.

    Assumes API version 2.6 or later.
    '''

    OPTIONS = (
        ('foreground', '-f'),
        ('debug', '-d'),
        ('nothreads', '-s'),
    )

    def __init__(
        self,
        operations: 'Operations',
        mountpoint: str,
        *,
        raw_fi: bool = False,
        encoding: typing.Optional[str] = None,
        **kwargs,
    ) -> None:

        '''
        Setting raw_fi to True will cause FUSE to pass the fuse_file_info
        class as is to Operations, instead of just the fh field.

        This gives you access to direct_io, keep_cache, etc.
        '''
        encoding = encoding or 'utf-8'
        self.operations = operations
        self.raw_fi = raw_fi
        self.encoding = encoding
        self.__critical_exception: BaseException = Exception()

        # string arguments
        sargs: typing.List[str] = ['fuse']

        # Convert options to fuse flags
        sargs.extend(flag for arg, flag in self.OPTIONS if kwargs.pop(arg, False))

        kwargs.setdefault('fsname', operations.__class__.__name__)
        sargs.append('-o')
        sargs.append(','.join(FUSE._normalize_fuse_options(**kwargs)))
        sargs.append(mountpoint)

        args: typing.List[bytes] = [arg.encode(encoding) for arg in sargs]
        argv = (ctypes.c_char_p * len(args))(*args)

        fuse_ops = FuseOperations()
        for ent in FuseOperations._fields_:
            name, prototype = ent[:2]

            check_name = name

            # ftruncate()/fgetattr() are implemented in terms of their
            # non-f-prefixed versions in the operations object
            if check_name in ['ftruncate', 'fgetattr']:
                check_name = check_name[1:]

            val = getattr(operations, check_name, None)
            if val is None:
                continue

            if hasattr(prototype, 'argtypes'):
                val = prototype(partial(FUSE._wrapper, getattr(self, name)))

            setattr(fuse_ops, name, val)

        try:
            old_handler = signal(SIGINT, SIG_DFL)
        except ValueError:
            old_handler = SIG_DFL

        err = _libfuse.fuse_main_real(
            len(args), argv, ctypes.pointer(fuse_ops), ctypes.sizeof(fuse_ops), None
        )

        try:
            signal(SIGINT, old_handler)
        except ValueError:
            pass

        del self.operations  # Invoke the destructor

        if type(self.__critical_exception) is not Exception:
            raise self.__critical_exception
        if err:
            raise RuntimeError(err)

    @staticmethod
    def _normalize_fuse_options(**kargs) -> typing.Generator[str, None, None]:
        for key, value in kargs.items():
            if isinstance(value, bool):
                if value is True:
                    yield key
            else:
                yield f'{key}={value}'

    @staticmethod
    def _wrapper(func: typing.Callable, *args, **kwargs) -> int:
        'Decorator for the methods that follow'

        try:
            if func.__name__ == "init":
                # init may not fail, as its return code is just stored as
                # private_data field of struct fuse_context
                return func(*args, **kwargs) or 0

            else:
                try:
                    return func(*args, **kwargs) or 0

                except OSError as e:
                    if e.errno > 0:
                        logger.debug(
                            "FUSE operation %s raised a %s, returning errno %s.",
                            func.__name__,
                            type(e),
                            e.errno,
                        )
                        return -e.errno
                    else:
                        logger.error(
                            "FUSE operation %s raised an OSError with negative "
                            "errno %s, returning errno.EINVAL.",
                            func.__name__,
                            e.errno,
                            exc_info=True,
                        )
                        return -errno.EINVAL

                except Exception:
                    logger.error(
                        "Uncaught exception from FUSE operation %s, "
                        "returning errno.EINVAL.",
                        func.__name__,
                        exc_info=True,
                    )
                    return -errno.EINVAL

        except BaseException as e:
            if len(args) > 0 and isinstance(args[0], FUSE):
                self = args[0]
                self.__critical_exception = e
            logger.critical(
                "Uncaught critical exception from FUSE operation %s, aborting.",
                func.__name__,
                exc_info=True,
            )
            # the raised exception (even SystemExit) will be caught by FUSE
            # potentially causing SIGSEGV, so tell system to stop/interrupt FUSE
            fuse_exit()
            return -errno.EFAULT

    def _decode_optional_path(
        self, path: typing.Optional[bytes]
    ) -> typing.Optional[str]:
        # NB: this method is intended for fuse operations that
        #     allow the path argument to be NULL,
        #     *not* as a generic path decoding method
        return path.decode(self.encoding) if path else None

    def getattr(self, path: bytes, buf: typing.Any) -> None:
        return self.fgetattr(path, buf, None)

    def readlink(self, path: bytes, buf: typing.Any, bufsize: int) -> None:
        ret = self.operations.readlink(path.decode(self.encoding)).encode(self.encoding)

        # copies a string into the given buffer
        # (null terminated and truncated if necessary)
        data = ctypes.create_string_buffer(ret[: bufsize - 1])
        ctypes.memmove(buf, data, len(data))

    def mknod(self, path: bytes, mode: int, dev: typing.Any) -> int:
        return self.operations.mknod(path.decode(self.encoding), mode, dev)

    def mkdir(self, path: bytes, mode: int) -> None:
        return self.operations.mkdir(path.decode(self.encoding), mode)

    def unlink(self, path: bytes) -> None:
        return self.operations.unlink(path.decode(self.encoding))

    def rmdir(self, path: bytes) -> None:
        return self.operations.rmdir(path.decode(self.encoding))

    def symlink(self, source: bytes, target: bytes) -> None:
        'creates a symlink `target -> source` (e.g. ln -s source target)'

        return self.operations.symlink(
            target.decode(self.encoding), source.decode(self.encoding)
        )

    def rename(self, old: bytes, new: bytes) -> None:
        return self.operations.rename(
            old.decode(self.encoding), new.decode(self.encoding)
        )

    def link(self, source: bytes, target: bytes) -> None:
        'creates a hard link `target -> source` (e.g. ln source target)'

        return self.operations.link(
            target.decode(self.encoding), source.decode(self.encoding)
        )

    def chmod(self, path: bytes, mode: int):
        return self.operations.chmod(path.decode(self.encoding), mode)

    def chown(self, path: bytes, uid: int, gid: int) -> None:
        # Check if any of the arguments is a -1 that has overflowed
        if c_uid_t(uid + 1).value == 0:
            uid = -1
        if c_gid_t(gid + 1).value == 0:
            gid = -1

        return self.operations.chown(path.decode(self.encoding), uid, gid)

    def truncate(self, path: bytes, length: int) -> None:
        return self.operations.truncate(path.decode(self.encoding), length)

    def open(self, path: bytes, fip: typing.Any) -> None:
        fi = fip.contents

        if self.raw_fi:
            self.operations.open(path.decode(self.encoding), fi)
        else:
            fi.fh = self.operations.open(path.decode(self.encoding), fi.flags)

    def read(
        self, path: bytes, buf: typing.Any, size: int, offset: int, fip: typing.Any
    ):
        # fip is a pointer to a struct fuse_file_info
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        logger.debug(
            'Invoking read operation on %s(%s, %s, %s)', path, size, offset, fh
        )
        ret = self.operations.read(self._decode_optional_path(path), size, offset, fh)

        if not ret:
            return 0

        retsize = len(ret)
        logger.debug('Read operation on %s returned %d bytes', path, retsize)

        if retsize > size:
            raise RuntimeError(
                "read too much data ({} bytes, expected {})".format(retsize, size)
            )

        ctypes.memmove(buf, ret, retsize)
        return retsize

    def write(
        self,
        path: typing.Optional[bytes],
        buf: typing.Any,
        size: int,
        offset: int,
        fip: typing.Any,
    ) -> int:
        # fip is a pointer to a struct fuse_file_info
        # buf is a char*
        data = ctypes.string_at(buf, size)

        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        return self.operations.write(self._decode_optional_path(path), data, offset, fh)

    def statfs(self, path: bytes, buf: typing.Any) -> None:
        stv = buf.contents
        attrs = self.operations.statfs(path.decode(self.encoding))
        for key, val in attrs.items():
            if hasattr(stv, key):
                setattr(stv, key, val)

    def flush(self, path: typing.Optional[bytes], fip: typing.Any) -> None:
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        self.operations.flush(self._decode_optional_path(path), fh)

    def release(self, path: typing.Optional[bytes], fip: typing.Any) -> None:
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        return self.operations.release(self._decode_optional_path(path), fh)

    def fsync(self, path: typing.Optional[bytes], datasync: bool, fip: typing.Any):
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        return self.operations.fsync(self._decode_optional_path(path), datasync, fh)

    def setxattr(
        self,
        path: bytes,
        name: bytes,
        value: typing.Any,
        size: int,
        options: int,
        *args,
    ) -> None:
        return self.operations.setxattr(
            path.decode(self.encoding),
            name.decode(self.encoding),
            ctypes.string_at(value, size).decode(self.encoding),
            options,
            *args,
        )

    def getxattr(
        self, path: bytes, name: bytes, value: typing.Any, size: int, *args
    ) -> int:
        ret = self.operations.getxattr(
            path.decode(self.encoding), name.decode(self.encoding), *args
        ).encode(self.encoding)

        retsize = len(ret)
        # allow size queries
        if not value:
            return retsize

        # do not truncate
        if retsize > size:
            return -errno.ERANGE

        # Does not add trailing 0
        buf = ctypes.create_string_buffer(ret, retsize)
        ctypes.memmove(value, buf, retsize)

        return retsize

    def listxattr(self, path: bytes, namebuf: typing.Any, size: int) -> int:
        attrs = self.operations.listxattr(path.decode(self.encoding)) or []
        ret = '\x00'.join(attrs).encode(self.encoding)
        if len(ret) > 0:
            ret += '\x00'.encode(self.encoding)

        retsize = len(ret)
        # allow size queries
        if not namebuf:
            return retsize

        # do not truncate
        if retsize > size:
            return -errno.ERANGE

        buf = ctypes.create_string_buffer(ret, retsize)
        ctypes.memmove(namebuf, buf, retsize)

        return retsize

    def removexattr(self, path: bytes, name: bytes) -> None:
        return self.operations.removexattr(
            path.decode(self.encoding), name.decode(self.encoding)
        )

    def opendir(self, path: bytes, fip: typing.Any) -> None:
        # Ignore raw_fi
        fip.contents.fh = self.operations.opendir(path.decode(self.encoding))

    def readdir(
        self,
        path: bytes,
        buf: typing.Any,
        filler: typing.Any,
        offset: int,
        fip: typing.Any,
    ) -> None:
        # Ignore raw_fi
        for item in self.operations.readdir(
            path.decode(self.encoding), fip.contents.fh
        ):
            if isinstance(item, str):
                name, st, offset = item, None, 0
            else:
                name, attrs, offset = item
                if attrs:
                    st = c_stat()
                    set_st_attrs(st, attrs)
                else:
                    st = None

            if filler(buf, name.encode(self.encoding), st, offset) != 0:
                break

    def releasedir(self, path: typing.Optional[bytes], fip: typing.Any):
        # Ignore raw_fi
        return self.operations.releasedir(
            self._decode_optional_path(path), fip.contents.fh
        )

    def fsyncdir(self, path: typing.Optional[bytes], datasync: bool, fip: typing.Any):
        # Ignore raw_fi
        return self.operations.fsyncdir(
            self._decode_optional_path(path), datasync, fip.contents.fh
        )

    def init(self, conn: typing.Any) -> None:
        return self.operations.init('/')

    def destroy(self, private_data: typing.Any) -> None:
        return self.operations.destroy('/')

    def access(self, path: bytes, amode: int) -> None:
        return self.operations.access(path.decode(self.encoding), amode)

    def create(self, path: bytes, mode: int, fip: typing.Any) -> None:
        fi = fip.contents

        if self.raw_fi:
            self.operations.create(path.decode(self.encoding), mode, fi)
        else:
            fi.fh = self.operations.create(path.decode(self.encoding), mode, None)

    def ftruncate(
        self, path: typing.Optional[bytes], length: int, fip: typing.Any
    ) -> int:
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        self.operations.truncate(self._decode_optional_path(path), length, fh)
        return 0

    def fgetattr(
        self, path: typing.Optional[bytes], buf: typing.Any, fip: typing.Any
    ) -> None:
        ctypes.memset(buf, 0, ctypes.sizeof(c_stat))

        st: c_stat = buf.contents
        if not fip:
            fh = fip
        elif self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        attrs = self.operations.getattr(self._decode_optional_path(path), fh)
        set_st_attrs(st, attrs)

    def lock(
        self,
        path: typing.Optional[bytes],
        fip: typing.Any,
        cmd: bytes,
        lock: typing.Any,
    ):
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        return self.operations.lock(self._decode_optional_path(path), fh, cmd, lock)

    def utimens(self, path: bytes, buf: typing.Any) -> int:
        times: typing.Optional[typing.Tuple[int, int]] = None
        times = (
            (
                time_of_timespec(buf.contents.actime),
                time_of_timespec(buf.contents.modtime),
            )
            if buf
            else None
        )

        return self.operations.utimens(path.decode(self.encoding), times)

    def bmap(self, path: bytes, blocksize: int, idx: int) -> int:
        return self.operations.bmap(path.decode(self.encoding), blocksize, idx)

    def ioctl(
        self,
        path: bytes,
        cmd: bytes,
        arg: bytes,
        fip: typing.Any,
        flags: int,
        data: bytes,
    ):
        if self.raw_fi:
            fh = fip.contents
        else:
            fh = fip.contents.fh

        return self.operations.ioctl(
            path.decode(self.encoding), cmd, arg, fh, flags, data
        )


class Operations:
    '''
    This class should be subclassed and passed as an argument to FUSE on
    initialization. All operations should raise a FuseOSError exception on
    error.

    When in doubt of what an operation should do, check the FUSE header file
    or the corresponding system call man page.
    '''

    def __call__(self, op: str, *args) -> typing.Any:
        try:
            return getattr(self, op)(*args)
        except AttributeError:
            raise FuseOSError(errno.EFAULT)

    def access(self, path: str, amode: int) -> None:
        return

    def bmap(self, path: str, blocksize: int, idx: int) -> int:
        return 0

    def chmod(self, path: str, mode: int) -> None:
        raise FuseOSError(errno.EROFS)

    def chown(self, path: str, uid: int, gid: int) -> None:
        raise FuseOSError(errno.EROFS)

    def create(self, path: str, mode: int, fi: typing.Any) -> int:
        '''
        When raw_fi is False (default case), fi is None and create should
        return a numerical file handle.

        When raw_fi is True the file handle should be set directly by create
        and return value is not used.
        '''
        raise FuseOSError(errno.EROFS)

    def destroy(self, path: str) -> None:
        'Called on filesystem destruction. Path is always /'
        pass

    def flush(self, path: typing.Optional[str], fh: typing.Any) -> None:
        pass

    def fsync(self, path: typing.Optional[str], datasync: bool, fh: typing.Any) -> None:
        pass

    def fsyncdir(
        self, path: typing.Optional[str], datasync: bool, fh: typing.Any
    ) -> None:
        pass

    def getattr(
        self, path: typing.Optional[str], fh: typing.Any = None
    ) -> typing.Dict[str, int]:
        '''
        Returns a dictionary with keys identical to the stat C structure of
        stat(2).

        NOTE: There is an incompatibility between Linux and Mac OS X
        concerning st_nlink of directories. Mac OS X counts all files inside
        the directory, while Linux counts only the subdirectories.
        '''

        if path != '/':
            raise FuseOSError(errno.ENOENT)
        return dict(st_mode=(S_IFDIR | 0o755), st_nlink=2)

    def getxattr(self, path: str, name: str, position: int = 0) -> str:
        raise FuseOSError(ENOTSUP)

    def init(self, path: str) -> None:
        '''
        Called on filesystem initialization. (Path is always /)

        Use it instead of __init__ if you start threads on initialization.
        '''
        pass

    def ioctl(
        self, path: str, cmd: bytes, arg: bytes, fip: int, flags: int, data: bytes
    ) -> int:
        raise FuseOSError(errno.ENOTTY)

    def link(self, target: str, source: str) -> None:
        'creates a hard link `target -> source` (e.g. ln source target)'

        raise FuseOSError(errno.EROFS)

    def listxattr(self, path: str) -> typing.List[str]:
        return []

    def lock(
        self, path: typing.Optional[str], fh: typing.Any, cmd: bytes, lock: typing.Any
    ) -> int:
        return 0

    def mkdir(self, path: str, mode: int) -> None:
        raise FuseOSError(errno.EROFS)

    def mknod(self, path: str, mode: int, dev: int) -> int:
        raise FuseOSError(errno.EROFS)

    def open(self, path: str, flags: int) -> int:
        '''
        When raw_fi is False (default case), open should return a numerical
        file handle.

        When raw_fi is True the signature of open becomes:
            open(self, path, fi)

        and the file handle should be set directly. In this case, the return value is ignored.
        '''
        return 0

    def opendir(self, path: str) -> int:
        'Returns a numerical file handle.'
        return 0

    def read(
        self, path: typing.Optional[str], size: int, offset: int, fh: typing.Any
    ) -> bytes:
        'Returns a string containing the data requested.'

        raise FuseOSError(errno.EIO)

    def readdir(
        self, path: str, fh: typing.Any
    ) -> typing.Union[
        typing.List[str], typing.List[typing.Tuple[str, typing.Dict[str, int], int]]
    ]:
        '''
        Can return either a list of names, or a list of (name, attrs, offset)
        tuples. attrs is a dict as in getattr.
        '''

        return ['.', '..']

    def readlink(self, path: str) -> str:
        raise FuseOSError(errno.ENOENT)

    def release(self, path: typing.Optional[str], fh: typing.Any) -> None:
        pass

    def releasedir(self, path: typing.Optional[str], fh: typing.Any) -> None:
        pass

    def removexattr(self, path: str, name: str) -> None:
        raise FuseOSError(ENOTSUP)

    def rename(self, old: str, new: str) -> None:
        raise FuseOSError(errno.EROFS)

    def rmdir(self, path: str) -> None:
        raise FuseOSError(errno.EROFS)

    def setxattr(
        self, path: str, name: str, value: str, options: int, position: int = 0
    ) -> None:
        raise FuseOSError(ENOTSUP)

    def statfs(self, path: str) -> typing.Dict[str, typing.Union[int, float]]:
        '''
        Returns a dictionary with keys identical to the statvfs C structure of
        statvfs(3).

        On Mac OS X f_bsize and f_frsize must be a power of 2
        (minimum 512).
        '''

        return {}

    def symlink(self, target: str, source: str) -> None:
        'creates a symlink `target -> source` (e.g. ln -s source target)'

        raise FuseOSError(errno.EROFS)

    def truncate(
        self, path: typing.Optional[str], length: int, fh: typing.Any = None
    ) -> None:
        raise FuseOSError(errno.EROFS)

    def unlink(self, path: str) -> None:
        raise FuseOSError(errno.EROFS)

    def utimens(
        self, path, times: typing.Optional[typing.Tuple[float, float]] = None
    ) -> int:
        'Times is a (atime, mtime) tuple. If None use current time.'

        return 0

    def write(
        self, path: typing.Optional[str], data: bytes, offset: int, fh: typing.Any
    ) -> int:
        raise FuseOSError(errno.EROFS)
