# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _

from uds.core.util import OsDetector
from uds.core import Module
from uds.core.transports import protocols
from uds.core.util import encoders
from uds.core.util import connection

import logging

logger = logging.getLogger(__name__)

DIRECT_GROUP = _('Direct')
TUNNELED_GROUP = _('Tunneled')


class Transport(Module):
    """
    An OS Manager is responsible for communication the service the different actions to take (i.e. adding a windows machine to a domain)
    The Service (i.e. virtual machine) communicates with the OSManager via a published web method, that must include the unique ID.
    In order to make easier to agents identify themselfs, the Unique ID can be a list with various Ids (i.e. the macs of the virtual machine).
    Server will iterate thought them and look for an identifier associated with the service. This list is a comma separated values (i.e. AA:BB:CC:DD:EE:FF,00:11:22:...)
    Remember also that we inherit the test and check methods from BaseModule
    """
    # Transport informational related data, inherited from BaseModule
    typeName = 'Base Transport Manager'
    typeType = 'Base Transport'
    typeDescription = 'Base Transport'
    iconFile = 'transport.png'
    # Supported names for OS (used right now, but lots of more names for sure)
    # Windows
    # Macintosh
    # Linux
    supportedOss = OsDetector.desktopOss  # Supported operating systems

    # If this transport is visible via Web, via Thin Client or both
    webTransport = False
    tcTransport = False

    # If the link to use transport is provided by transport itself
    ownLink = False

    # Protocol "type". This is not mandatory, but will help
    protocol = protocols.NONE

    # For allowing grouping transport on dashboard "new" menu, and maybe other places
    group = DIRECT_GROUP

    def __init__(self, environment, values):
        super(Transport, self).__init__(environment, values)
        self.initialize(values)

    def initialize(self, values):
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            Values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        """
        pass

    def destroy(self):
        """
        Invoked when Transport is deleted
        """
        pass

    def testServer(self, userService, ip, port, timeout=4):
        proxy = userService.deployed_service.service.proxy
        if proxy is not None:
            return proxy.doTestServer(ip, port, timeout)
        return connection.testServer(ip, str(port), timeout)

    def isAvailableFor(self, userService, ip):
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        return False

    def getCustomAvailableErrorMsg(self, userService, ip):
        """
        Returns a customized error message, that will be used when a service fails to check "isAvailableFor"
        Override this in yours transports if needed
        """
        return "Not accessible (using service ip {0})".format(ip)

    @classmethod
    def supportsProtocol(cls, protocol):
        if isinstance(protocol, (list, tuple)):
            for v in protocol:
                if cls.supportsProtocol(v) is True:
                    return True
            return False
        return protocol.lower() == cls.protocol.lower()

    @classmethod
    def supportsOs(cls, osName):
        """
        Helper method to check if transport supports requested operating system.
        Class method
        """
        logger.debug('Checking suported os {0} against {1}'.format(osName, cls.supportedOss))
        return cls.supportedOss.count(osName) > 0

    @classmethod
    def providesConnetionInfo(cls):
        """
        Helper method to check if transport provides information about connection
        """
        return cls.getConnectionInfo != Transport.getConnectionInfo

    def getConnectionInfo(self, service, user, password):
        """
        This method must provide information about connection.
        We don't have to implement it, but if we wont to allow some types of connections
        (such as Client applications, some kinds of TC, etc... we must provide it or those
        kind of terminals/application will not work

        Args:
            userService: DeployedUserService for witch we are rendering the connection (db model), or DeployedService (db model)
            user: user (dbUser) logged in
            pass: password used in authentication

        The expected result from this method is a dictionary, containing at least:
            'protocol': protocol to use, (there are a few standard defined in 'protocols.py', if yours does not fit those, use your own name
            'username': username (transformed if needed to) used to login to service
            'password': password (transformed if needed to) used to login to service
            'domain': domain (extracted from username or wherever) that will be used. (Not necesarily an AD domain)

        :note: The provided service can be an user service or an deployed service (parent of user services).
               I have implemented processUserPassword in both so in most cases we do not need if the service is
               DeployedService or UserService. In case of processUserPassword for an DeployedService, no transformation
               is done, because there is no relation at that level between user and service.
        """
        return {'protocol': self.protocol, 'username': '', 'password': '', 'domain': ''}

    def processedUser(self, userService, user):
        """
        Used to "transform" username that will be sent to service
        This is used to make the "user" that will receive the service match with that sent in notification
        @return: transformed username
        """
        return user.name

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        """
        If this is an uds transport, this will return the tranport script needed for executing
        this on client
        """
        return "raise Exception('The transport {transport} is not supported on your platform.'.format(transport=params['transport']))", \
            'EH/91J7u9+/sHtB5+EUVRDW1+jqF0LuZzfRi8qxyIuSdJuWt'\
            '8V8Yngu24p0NNr13TaxPQ1rpGN8x0NsU/Ma8k4GGohc+zxdf'\
            '4xlkwMjAIytp8jaMHKkzvcihiIAMtaicP786FZCwGMmFTH4Z'\
            'A9i7YWaSzT95h84kirAG67J0GWKiyATxs6mtxBNaLgqU4juA'\
            'Qn98hYp5ffWa5FQDSAmheiDyQbCXMRwtWcxVHVQCAoZbsvCe'\
            'njKc+FaeKNmXsYOgmcj+pz8IViNOyTbueP9u7lTzuBlIyV+7'\
            'OlBPTqb5yA5wOBicKIpplPd8V71Oh3pdpRvdlvVbbwNfsCl5'\
            'v6s1X20MxaQOSwM5z02eY1lJSbLIp8d9WRkfVty0HP/4Z8JZ'\
            'kavkWNaGiKXEZXqojx/ZdzvTfvBkYrREQ8lMCIvtawBTysus'\
            'IV4vHnDRdSmRxpYdj+1SNfzB0s1VuY6F7bSdBvgzja4P3Zbo'\
            'Z63yNGuBhIsqUDA2ARmiMHRx9jr6eilFBKhoyWgNi9izTkar'\
            '3iMYtXfvcFnmz4jvuJHUccbpUo4O31K2G7OaqlLylQ5dCu62'\
            'JuVuquKKSfiwOIdYcdPJ6gvpgkQQDPqt7wN+duyZA0FI5F4h'\
            'O6acQZmbjBCqZoo9Qsg7k9cTcalNkc5flEYAk1mULnddgDM6'\
            'YGmoJgVnDr0=', {'transport': transport.name}

    def getEncodedTransportScript(self, userService, transport, ip, os, user, password, request):
        """
        Encodes the script so the client can understand it
        """
        script, signature, params = self.getUDSTransportScript(userService, transport, ip, os, user, password, request)
        logger.debug('Transport script: {}'.format(script))
        return encoders.encode(encoders.encode(script, 'bz2'), 'base64', asText=True).replace('\n', ''), signature, params

    def getLink(self, userService, transport, ip, os, user, password, request):
        """
        Must override if transport does provides its own link
        If transport provides own link, this method provides the link itself
        """
        return None

    def __str__(self):
        return "Base OS Manager"
