# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2018 Virtual Cable S.L.
# All rights reserved.
#

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import codecs
import logging
import typing

from django.utils.translation import ugettext_noop as _, ugettext_lazy
from uds.core import osmanagers
from uds.core.services import types as serviceTypes
from uds.core.ui import gui
from uds.core.managers import userServiceManager
from uds.core.util.state import State
from uds.core.util import log
from uds.models import TicketStore

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService

logger = logging.getLogger(__name__)


def scrambleMsg(msg: str) -> str:
    """
    Simple scrambler so password are not seen at source page
    """
    data = msg.encode('utf8')
    res = b''
    n = 0x32
    for c in data[::-1]:
        res += bytes([c ^ n])
        n = (n + c) & 0xFF
    return codecs.encode(res, 'hex').decode()


class WindowsOsManager(osmanagers.OSManager):
    typeName = _('Windows Basic OS Manager')
    typeType = 'WindowsManager'
    typeDescription = _('Os Manager to control windows machines without domain.')
    iconFile = 'wosmanager.png'
    servicesType = (serviceTypes.VDI,)

    onLogout = gui.ChoiceField(
        label=_('Logout Action'),
        order=10,
        rdonly=True,
        tooltip=_('What to do when user logs out from service'),
        values=[
            {'id': 'keep', 'text': ugettext_lazy('Keep service assigned')},
            {'id': 'remove', 'text': ugettext_lazy('Remove service')},
            {
                'id': 'keep-always',
                'text': ugettext_lazy('Keep service assigned even on new publication'),
            },
        ],
        defvalue='keep',
    )

    idle = gui.NumericField(
        label=_("Max.Idle time"),
        length=4,
        defvalue=-1,
        rdonly=False,
        order=11,
        tooltip=_(
            'Maximum idle time (in seconds) before session is automatically closed to the user (<= 0 means no max. idle time)'
        ),
        required=True,
    )

    deadLine = gui.CheckBoxField(
        label=_('Calendar logout'),
        order=90,
        tooltip=_(
            'If checked, UDS will try to logout user when the calendar for his current access expires'
        ),
        tab=gui.ADVANCED_TAB,
        defvalue=gui.TRUE,
    )

    _onLogout: str
    _idle: int
    _deadLine: bool

    @staticmethod
    def validateLen(length):
        try:
            length = int(length)
        except Exception:
            raise osmanagers.OSManager.ValidationException(
                _('Length must be numeric!!')
            )
        if length > 6 or length < 1:
            raise osmanagers.OSManager.ValidationException(
                _('Length must be betwen 1 and 6')
            )
        return length

    def __setProcessUnusedMachines(self):
        self.processUnusedMachines = self._onLogout == 'remove'

    def __init__(self, environment, values):
        super(WindowsOsManager, self).__init__(environment, values)
        if values is not None:
            self._onLogout = values['onLogout']
            self._idle = int(values['idle'])
            self._deadLine = gui.strToBool(values['deadLine'])
        else:
            self._onLogout = ''
            self._idle = -1
            self._deadLine = True

        self.__setProcessUnusedMachines()

    def isRemovableOnLogout(self, userService: 'UserService') -> bool:
        """
        Says if a machine is removable on logout
        """
        if not userService.in_use:
            if (self._onLogout == 'remove') or (
                not userService.isValidPublication() and self._onLogout == 'keep'
            ):
                return True

        return False

    def release(self, userService: 'UserService') -> None:
        pass

    def ignoreDeadLine(self) -> bool:
        return not self._deadLine

    def getName(self, userService: 'UserService') -> str:
        return userService.getName()

    def infoVal(self, userService: 'UserService') -> str:
        return 'rename:' + self.getName(userService)

    def infoValue(self, userService: 'UserService') -> str:
        return 'rename\r' + self.getName(userService)

    def notifyIp(
        self, uid: str, userService, data: typing.Dict[str, typing.Any]
    ) -> None:
        userServiceInstance = userService.getInstance()

        ip = ''
        # Notifies IP to deployed
        for p in data['ips']:
            if p[0].lower() == uid.lower():
                userServiceInstance.setIp(p[1])
                ip = p[1]
                break

        self.logKnownIp(userService, ip)
        userService.updateData(userServiceInstance)

    def doLog(self, userService: 'UserService', data: str, origin=log.OSMANAGER):
        # Stores a log associated with this service
        try:
            msg, levelStr = data.split('\t')
            try:
                level = int(levelStr)
            except Exception:
                logger.debug('Do not understand level %s', levelStr)
                level = log.INFO

            log.doLog(userService, level, msg, origin)
        except Exception:
            logger.exception('WindowsOs Manager message log: ')
            log.doLog(
                userService, log.ERROR, "do not understand {0}".format(data), origin
            )

    # default "ready received" does nothing
    def readyReceived(self, userService, data):
        pass

    def loginNotified(self, userService, userName=None):
        if '\\' not in userName:
            osmanagers.OSManager.loggedIn(userService, userName)

    def logoutNotified(self, userService, userName=None):
        osmanagers.OSManager.loggedOut(userService, userName)
        if self.isRemovableOnLogout(userService):
            userService.release()

    def readyNotified(self, userService):
        return

    def actorData(
        self, userService: 'UserService'
    ) -> typing.MutableMapping[str, typing.Any]:
        return {'action': 'rename', 'name': userService.getName()}

    def process(
        self,
        userService: 'UserService',
        message: str,
        data: typing.Any,
        options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> str:  # pylint: disable=too-many-branches
        """
        We understand this messages:
        * msg = info, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class) (old method)
        * msg = information, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class) (new method)
        * msg = logon, data = Username, Informs that the username has logged in inside the machine
        * msg = logoff, data = Username, Informs that the username has logged out of the machine
        * msg = ready, data = None, Informs machine ready to be used
        """
        logger.info(
            "Invoked WindowsOsManager for %s with params: %s,%s",
            userService,
            message,
            data,
        )

        if message in ('ready', 'ip') and not isinstance(
            data, dict
        ):  # Old actors, previous to 2.5, convert it information..
            data = {
                'ips': [v.split('=') for v in data.split(',')],
                'hostname': userService.friendly_name,
            }

        # We get from storage the name for this userService. If no name, we try to assign a new one
        ret = "ok"
        notifyReady = False
        doRemove = False
        state = userService.os_state
        if message == "info":
            ret = self.infoVal(userService)
            state = State.PREPARING
        elif message == "information":
            ret = self.infoValue(userService)
            state = State.PREPARING
        elif message == "log":
            self.doLog(userService, str(data), log.ACTOR)
        elif message in ("logon", 'login'):
            if '\\' not in data:
                osmanagers.OSManager.loggedIn(userService, str(data))
            userService.setInUse(True)
            # We get the userService logged hostname & ip and returns this
            ip, hostname = userService.getConnectionSource()
            deadLine = userService.deployed_service.getDeadline()
            if (
                typing.cast(str, userService.getProperty('actor_version', '0.0.0'))
                >= '2.0.0'
            ):
                ret = "{0}\t{1}\t{2}".format(
                    ip, hostname, 0 if deadLine is None else deadLine
                )
            else:
                ret = "{0}\t{1}".format(ip, hostname)
        elif message in ('logoff', 'logout'):
            osmanagers.OSManager.loggedOut(userService, str(data))
            doRemove = self.isRemovableOnLogout(userService)
        elif message == "ip":
            # This ocurss on main loop inside machine, so userService is usable
            state = State.USABLE
            self.notifyIp(userService.unique_id, userService, data)
        elif message == "ready":
            self.toReady(userService)
            state = State.USABLE
            notifyReady = True
            self.notifyIp(userService.unique_id, userService, data)
            self.readyReceived(userService, data)

        userService.setOsState(state)

        # If notifyReady is not true, save state, let UserServiceManager do it for us else
        if doRemove is True:
            userService.release()
        else:
            if notifyReady is False:
                userService.save(
                    update_fields=['in_use', 'in_use_date', 'os_state', 'state', 'data']
                )
            else:
                logger.debug('Notifying ready')
                userServiceManager().notifyReadyFromOsManager(userService, '')
        logger.debug('Returning %s to %s message', ret, message)
        if options is not None and options.get('scramble', True) is False:
            return ret
        return scrambleMsg(ret)

    def processUserPassword(
        self, userService: 'UserService', username: str, password: str
    ) -> typing.Tuple[str, str]:
        if userService.getProperty('sso_available') == '1':
            # Generate a ticket, store it and return username with no password
            domain = ''
            if '@' in username:
                username, domain = username.split('@')
            elif '\\' in username:
                username, domain = username.split('\\')

            creds = {'username': username, 'password': password, 'domain': domain}
            ticket = TicketStore.create(
                creds, validatorFnc=None, validity=300
            )  # , owner=SECURE_OWNER, secure=True)
            return ticket, ''

        return osmanagers.OSManager.processUserPassword(
            self, userService, username, password
        )

    def processUnused(self, userService: 'UserService') -> None:
        """
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        """
        if self.isRemovableOnLogout(userService):
            log.doLog(
                userService,
                log.INFO,
                'Unused user service for too long. Removing due to OS Manager parameters.',
                log.OSMANAGER,
            )
            userService.remove()

    def isPersistent(self):
        return self._onLogout == 'keep-always'

    def checkState(self, userService: 'UserService') -> str:
        # will alway return true, because the check is done by an actor callback
        logger.debug('Checking state for service %s', userService)
        return State.RUNNING

    def maxIdle(self):
        """
        On production environments, will return no idle for non removable machines
        """
        if (
            self._idle <= 0
        ):  # or (settings.DEBUG is False and self._onLogout != 'remove'):
            return None

        return self._idle

    def marshal(self) -> bytes:
        """
        Serializes the os manager data so we can store it in database
        """
        return '\t'.join(
            ['v3', self._onLogout, str(self._idle), gui.boolToStr(self._deadLine)]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        vals = data.decode('utf8').split('\t')
        self._idle = -1
        self._deadLine = True
        try:
            if vals[0] == 'v1':
                self._onLogout = vals[1]
            elif vals[0] == 'v2':
                self._onLogout, self._idle = vals[1], int(vals[2])
            elif vals[0] == 'v3':
                self._onLogout, self._idle, self._deadLine = (
                    vals[1],
                    int(vals[2]),
                    gui.strToBool(vals[3]),
                )
        except Exception:
            logger.exception(
                'Exception unmarshalling. Some values left as default ones'
            )

        self.__setProcessUnusedMachines()

    def valuesDict(self) -> gui.ValuesDictType:
        return {
            'onLogout': self._onLogout,
            'idle': str(self._idle),
            'deadLine': gui.boolToStr(self._deadLine),
        }
