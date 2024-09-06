# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Authentication modules for uds are contained inside this module.
To create a new authentication module, you will need to follow this steps:
    1.- Create the authentication module, probably based on an existing one
    2.- Insert the module as child of this module
    3.- Import the class of your authentication module at __init__. For example::
        from Authenticator import SimpleAthenticator
    4.- Done. At Server restart, the module will be recognized, loaded and treated

The registration of modules is done locating subclases of :py:class:`uds.core.auths.Authentication`

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from uds.core.util import modfinder

logger = logging.getLogger(__name__)


def initialize() -> None:
    """
    This imports all packages that are descendant of this package, and, after that,
    it register all subclases of mfas.MFA 
    """
    from uds.core import mfas  # pylint: disable=import-outside-toplevel

    modfinder.dynamically_load_and_register_modules(mfas.factory(), mfas.MFA, __name__)


initialize()
