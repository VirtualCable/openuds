# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
Report modules for UDS are contained inside this package.
To create a new rwpoer module, you will need to follow this steps:
    1.- Create the report module inside one of the existing (or new one) packages
    2.- Import the class of your report module at __init__. For example::
        from Report import SimpleReport
    3.- Done. At Server restart, the module will be recognized, loaded and treated

The registration of modules is done locating subclases of :py:class:`uds.core.reports.Report`

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core import reports
from uds.core.util import modfinder

logger = logging.getLogger(__name__)

available_reports: list[type['reports.Report']] = []


def __load_modules() -> None:
    """
    This imports all packages that are descendant of this package, and, after that,
    """
    already_seen: typing.Set[str] = set()

    def _add_report_class(cls: type[reports.Report]) -> None:
        already_seen.add(cls.uuid)
        available_reports.append(cls)
        
    def _checker(cls: type[reports.Report]) -> bool:
        return bool(cls.uuid) and cls.uuid not in already_seen

    modfinder.dynamically_load_and_register_packages(
        _add_report_class,
        reports.Report,
        __name__,
        checker=_checker,
    )

__load_modules()
