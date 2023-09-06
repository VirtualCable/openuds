# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import sys
import typing
import logging
import enum

from django.apps import apps
from django.utils.translation import gettext_lazy as _, gettext
from uds.models.config import Config as DBConfig
from uds.core.managers.crypto import CryptoManager

logger = logging.getLogger(__name__)

_saveLater: typing.List[typing.Tuple['Config.Value', typing.Any]] = []
_getLater: typing.List['Config.Value'] = []

# For custom params (for choices mainly)
_configParams = {}

# Pair of section/value removed from current UDS version
# Note: As of version 4.0, all previous REMOVED values has been moved to migration script 0043
REMOVED_CONFIG_ELEMENTS = {
    'UDS': (),
    'Cluster': (),
    'IPAUTH': (),
    'VMWare': (),
    'HyperV': (),
    'Security': (),
    'RGS': (
        'downloadUrl',
        'tunnelOpenedTime',
    ),
}


class Config:
    # Fields types, so inputs get more "beautiful"
    class FieldType(enum.IntEnum):
        UNKNOWN = -1
        TEXT = 0
        LONGTEXT = 1
        NUMERIC = 2
        BOOLEAN = 3
        CHOICE = 4  # Choice fields must set its parameters on global "configParams" (better by calling ".setParams" method)
        READ = 5  # Only can viewed, but not changed (can be changed througn API, it's just read only to avoid "mistakes")
        HIDDEN = 6  # Not visible on "admin" config edition
        PASSWORD = 7  # Password field (not encrypted, but "hashed" on database)

    class SectionType(enum.StrEnum):
        GLOBAL = 'UDS'
        SECURITY = 'Security'
        CUSTOM = 'Custom'
        ADMIN = 'Admin'
        WYSE = 'WYSE'  # Legacy
        OTHER = 'Other'

        @staticmethod
        def fromStr(value: str) -> 'Config.SectionType':
            if value in list(Config.SectionType.values()):
                return Config.SectionType(value)
            return Config.SectionType(Config.SectionType.OTHER)

        @staticmethod
        def values() -> typing.Iterable['Config.SectionType']:
            return Config.SectionType

    class Section:
        _sectionName: 'Config.SectionType'

        def __init__(self, sectionName: 'Config.SectionType') -> None:
            self._sectionName = sectionName

        def value(self, key, default='', **kwargs) -> 'Config.Value':
            return Config.value(self, key, default, **kwargs)

        def valueCrypt(self, key, default='', **kwargs) -> 'Config.Value':
            return Config.value(self, key, default, True, **kwargs)

        def valueLong(self, key, default='', **kwargs) -> 'Config.Value':
            return Config.value(self, key, default, False, True, **kwargs)

        def name(self) -> str:
            return self._sectionName

        def __str__(self) -> str:
            return self._sectionName

    class Value:
        _section: 'Config.Section'  # type: ignore  # mypy bug?
        _type: int
        _key: str
        _crypt: bool
        _longText: bool
        _default: str
        _help: str
        _data: typing.Optional[str] = None

        def __init__(
            self,
            section: 'Config.Section',
            key: str,
            default: str = '',
            crypt: bool = False,
            longText: bool = False,
            **kwargs,
        ):
            self._type = kwargs.get('type', -1)

            self._section = section
            self._key = key
            self._crypt = crypt
            self._longText = longText
            if crypt is False or not default:
                self._default = default
            else:
                self._default = CryptoManager().encrypt(default)

            self._help = kwargs.get('help', '')

            logger.debug(self)

        def get(self, force: bool = False) -> str:
            if apps.ready:
                if not GlobalConfig.isInitialized():
                    logger.debug('Initializing configuration & updating db values')
                    GlobalConfig.initialize()
            else:
                _getLater.append(self)
                return self._default

            try:
                if force or self._data is None:
                    # logger.debug('Accessing db config {0}.{1}'.format(self._section.name(), self._key))
                    readed = DBConfig.objects.get(section=self._section.name(), key=self._key)
                    self._data = readed.value
                    # Ensure password are not encrypted again on DB, even if legacy values were
                    self._crypt = (
                        (readed.crypt or self._crypt) if self._type != Config.FieldType.PASSWORD else False
                    )
                    self._longText = readed.long
                    if self._type not in (-1, readed.field_type):
                        readed.field_type = self._type
                        readed.save(update_fields=['field_type'])
                    if self._help not in ('', readed.help):
                        readed.help = self._help
                        readed.save(update_fields=['help'])  # Append help field if not exists
                    self._type = readed.field_type
                    self._help = readed.help or self._help
            except DBConfig.DoesNotExist:
                # Not found, so we create it
                if self._default and self._crypt:
                    self.set(CryptoManager().decrypt(self._default))
                elif not self._crypt:
                    self.set(self._default)
                self._data = self._default
            except Exception as e:
                logger.info('Error accessing db config %s.%s', self._section.name(), self._key)
                logger.exception(e)
                self._data = self._default

            if self._crypt:
                return CryptoManager().decrypt(typing.cast(str, self._data))
            return typing.cast(str, self._data)

        def setParams(self, params: typing.Any) -> None:
            _configParams[self._section.name() + self._key] = params

        def getInt(self, force: bool = False) -> int:
            try:
                return int(self.get(force))
            except Exception:
                logger.error(
                    'Value for %s.%s is invalid (integer expected)',
                    self._section,
                    self._key,
                )
                try:
                    return int(self._default)
                except Exception:
                    logger.error(
                        'Default value for %s.%s is also invalid (integer expected)',
                        self._section,
                        self._key,
                    )
                    return -1

        def getBool(self, force: bool = False) -> bool:
            if self.get(force) == '0':
                return False
            return True

        def key(self) -> str:
            return self._key

        def section(self) -> str:
            return self._section.name()

        def isCrypted(self) -> bool:
            return self._crypt

        def isLongText(self) -> bool:
            return self._longText

        def getType(self) -> int:
            return self._type

        def getParams(self) -> typing.Any:
            return _configParams.get(self._section.name() + self._key, None)

        def getHelp(self) -> str:
            return gettext(self._help)

        def set(self, value: typing.Union[str, bool, int]) -> None:
            if GlobalConfig.isInitialized() is False:
                _saveLater.append((self, value))
                return

            if isinstance(value, bool):
                value = ['0', '1'][value]

            if isinstance(value, int):
                value = str(value)

            if self._crypt:
                value = CryptoManager().encrypt(value)

            if self._type == Config.FieldType.PASSWORD:
                value = CryptoManager().hash(value)

            logger.debug('Saving config %s.%s as %s', self._section.name(), self._key, value)
            try:
                obj, _ = DBConfig.objects.get_or_create(section=self._section.name(), key=self._key)
                obj.value, obj.crypt, obj.long, obj.field_type, obj.help = (
                    str(value),
                    self._crypt,
                    self._longText,
                    self._type,
                    self._help,
                )
                obj.save()
            except Exception:
                if 'migrate' in sys.argv:  # During migration, set could be saved as part of initialization...
                    return
                logger.exception('Exception')
                # Probably a migration issue, just ignore it
                logger.info(
                    "Could not save configuration key %s.%s",
                    self._section.name(),
                    self._key,
                )
            finally:
                self._data = str(value)

        def __str__(self) -> str:
            return f'{self._section.name()}.{self._key}'

    @staticmethod
    def section(sectionType: SectionType):
        return Config.Section(sectionType)

    @staticmethod
    def value(
        section: Section, key: str, default: str, crypt: bool = False, longText: bool = False, **kwargs
    ) -> 'Config.Value':
        return Config.Value(section, key, default, crypt, longText, **kwargs)

    @staticmethod
    def enumerate() -> typing.Iterable['Config.Value']:
        GlobalConfig.initialize()  # Ensures DB contains all values
        for cfg in DBConfig.objects.all().order_by('key'):  # @UndefinedVariable
            # Skip sections with name starting with "__" (not to be editted on configuration)
            if cfg.section.startswith('__'):  # Hidden section:
                continue
            # Hidden field, not to be edited by admin interface
            if cfg.field_type == Config.FieldType.HIDDEN:
                continue
            logger.debug('%s.%s:%s,%s', cfg.section, cfg.key, cfg.value, cfg.field_type)
            if cfg.crypt:
                val = Config.section(Config.SectionType.fromStr(cfg.section)).valueCrypt(cfg.key)
            else:
                val = Config.section(Config.SectionType.fromStr(cfg.section)).value(cfg.key)
            yield val

    @staticmethod
    def update(section: 'Config.SectionType', key: str, value: str, checkType: bool = False) -> bool:
        # If cfg value does not exists, simply ignore request
        try:
            cfg: DBConfig = DBConfig.objects.filter(section=section, key=key)[
                0  # type: ignore  # Slicing is not supported by pylance right now
            ]
            if checkType and cfg.field_type in (
                Config.FieldType.READ,
                Config.FieldType.HIDDEN,
            ):
                return False  # Skip non writable elements

            if cfg.crypt:
                # If field type is a password, store hashed value
                if cfg.field_type == Config.FieldType.PASSWORD.value:
                    value = CryptoManager().hash(value)
                else:
                    value = CryptoManager().encrypt(value)  # Rest, encrypt value (symetrically)

            cfg.value = value
            cfg.save()
            logger.debug('Updated value for %s.%s to %s', section, key, value)
            return True
        except Exception:
            return False

    @staticmethod
    def getConfigValues(
        addCrypt: bool = False,
    ) -> typing.Mapping[str, typing.Mapping[str, typing.Mapping[str, typing.Any]]]:
        """
        Returns a dictionary with all config values
        """
        res: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        for cfg in Config.enumerate():
            # Skip removed configuration values, even if they are in database
            logger.debug('Key: %s, val: %s', cfg.section(), cfg.key())
            if cfg.key() in REMOVED_CONFIG_ELEMENTS.get(cfg.section(), ()):
                continue

            if cfg.isCrypted() is True and addCrypt is False:
                continue

            if cfg.getType() == Config.FieldType.PASSWORD and addCrypt is False:
                continue

            # add section if it do not exists
            if cfg.section() not in res:
                res[cfg.section()] = {}
            res[cfg.section()][cfg.key()] = {
                'value': cfg.get(),
                'crypt': cfg.isCrypted(),
                'longText': cfg.isLongText(),
                'type': cfg.getType(),
                'params': cfg.getParams(),
                'help': cfg.getHelp(),
            }
        logger.debug('Configuration: %s', res)
        return res


class GlobalConfig:
    """
    Simple helper to keep track of global configuration
    """

    SESSION_EXPIRE_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'sessionExpireTime',
        '24',
        type=Config.FieldType.NUMERIC,
        help=_('Session expire time in hours after publishing'),
    )  # Max session duration (in use) after a new publishment has been made
    # Delay between cache checks. reducing this number will increase cache generation speed but also will load service providers
    CACHE_CHECK_DELAY: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'cacheCheckDelay',
        '19',
        type=Config.FieldType.NUMERIC,
        help=_(
            'Delay between cache checks. Reducing this number will increase cache generation speed but also will load service providers'
        ),
    )
    # Delayed task number of threads PER SERVER, with higher number of threads, deplayed task will complete sooner, but it will give more load to overall system
    DELAYED_TASKS_THREADS: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'delayedTasksThreads',
        '4',
        type=Config.FieldType.NUMERIC,
        help=_(
            'Delayed task number of threads PER SERVER, with higher number of threads, deployed task will complete sooner, but it will give more load to overall system'
        ),
    )
    # Number of scheduler threads running PER SERVER, with higher number of threads, deplayed task will complete sooner, but it will give more load to overall system
    SCHEDULER_THREADS: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'schedulerThreads',
        '3',
        type=Config.FieldType.NUMERIC,
        help=_(
            'Number of scheduler threads running PER SERVER, with higher number of threads, deployed task will complete sooner, but it will give more load to overall system'
        ),
    )
    # Waiting time before removing "errored" and "removed" publications, cache, and user assigned machines. Time is in seconds
    CLEANUP_CHECK: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'cleanupCheck',
        '3607',
        type=Config.FieldType.NUMERIC,
        help=_(
            'Waiting time before removing "errored" and "removed" publications, cache, and user assigned machines. Time is in seconds'
        ),
    )
    # Time to maintaing "info state" items before removing it, in seconds
    KEEP_INFO_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'keepInfoTime',
        '14401',
        type=Config.FieldType.NUMERIC,
        help=_('Time to maintaing "info state" items before removing it, in seconds'),
    )  # Defaults to 2 days 172800?? better 4 hours xd
    # Number of services to initiate removal per run of CacheCleaner
    USER_SERVICE_CLEAN_NUMBER: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'userServiceCleanNumber',
        '8',
        type=Config.FieldType.NUMERIC,
        help=_('Number of services to initiate removal per run of CacheCleaner'),
    )  # Defaults to 3 per wun
    # Removal Check time for cache, publications and deployed services
    REMOVAL_CHECK: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'removalCheck',
        '31',
        type=Config.FieldType.NUMERIC,
        help=_('Removal Check time for cache, publications and deployed services'),
    )  # Defaults to 30 seconds
    SUPER_USER_LOGIN: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'superUser', 'root', type=Config.FieldType.TEXT, help=_('Superuser username')
    )
    # Superuser password (do not need to be at database!!!)
    SUPER_USER_PASS: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'rootPass', 'udsmam0', type=Config.FieldType.PASSWORD, help=_('Superuser password')
    )
    SUPER_USER_ALLOW_WEBACCESS: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'allowRootWebAccess',
        '1',
        type=Config.FieldType.BOOLEAN,
        help=_('Allow root user to access using web interface'),
    )
    # Enhaced security
    ENHANCED_SECURITY: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Enable Enhanced Security',
        '1',
        type=Config.FieldType.BOOLEAN,
        help=_('Enable enhanced security modules'),
    )
    # Paranoid security
    ENFORCE_ZERO_TRUST: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Enforce Zero-Trust Mode', '0', type=Config.FieldType.BOOLEAN
    )
    # Time an admi session can be idle before being "logged out"
    # ADMIN_IDLE_TIME: Config.Value = Config.section(Config.SectionType.SECURITY).value('adminIdleTime', '14400', type=Config.FieldType.NUMERIC_FIELD)  # Defaults to 4 hous
    # Time betwen checks of unused services by os managers
    # Unused services will be invoked for every machine assigned but not in use AND that has been assigned at least this time
    # (only if os manager asks for this characteristic)
    CHECK_UNUSED_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'checkUnusedTime',
        '631',
        type=Config.FieldType.NUMERIC,
        help=_('Time betwen checks of unused user services by os managers'),
    )  # Defaults to 10 minutes
    CHECK_UNUSED_DELAY: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'checkUnusedDelay',
        '300',
        type=Config.FieldType.NUMERIC,
        help=_('Time betwen checks of unused user services by os managers'),
    )  # Defaults to 10 minutes
    # Default CSS Used: REMOVED! (keep the for for naw, for reference, but will be cleaned on future...)
    # CSS: Config.Value = Config.section(Config.SectionType.GLOBAL).value('css', settings.STATIC_URL + 'css/uds.css', type=Config.FieldType.TEXT_FIELD)
    # Max logins before blocking an account
    MAX_LOGIN_TRIES: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'maxLoginTries',
        '5',
        type=Config.FieldType.NUMERIC,
        help=_('Max logins before blocking an account for a while'),
    )
    # Block time in second for an user that makes too many mistakes, 5 minutes default
    LOGIN_BLOCK: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'loginBlockTime',
        '300',
        type=Config.FieldType.NUMERIC,
        help=_('Block time in second for an user that has too many login failures'),
    )
    LOGIN_BLOCK_IP: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Block ip on login failure',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Block ip on login failure'),
    )
    # Do autorun of service if just one service.
    # 0 = No autorun, 1 = Autorun at login
    # In a future, maybe necessary another value "2" that means that autorun always
    AUTORUN_SERVICE: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'autorunService',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Do autorun of service if just one service'),
    )
    # Redirect HTTP to HTTPS
    REDIRECT_TO_HTTPS: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'redirectToHttps',
        '1',
        type=Config.FieldType.BOOLEAN,
        help=_('Redirect HTTP to HTTPS on connection to UDS'),
    )
    # Max time needed to get a service "fully functional" before it's considered "failed" and removed
    # The time is in seconds
    MAX_INITIALIZING_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'maxInitTime',
        '3601',
        type=Config.FieldType.NUMERIC,
        help=_(
            'Max time needed to get a service "fully functional" before it\'s considered "failed" and removed'
        ),
    )
    MAX_REMOVAL_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'maxRemovalTime',
        '14400',
        type=Config.FieldType.NUMERIC,
        help=_('Max time needed to get a service "fully removed" before it\'s considered "failed" and purged'),
    )
    # Maximum logs per every log-capable administration element
    INDIVIDIAL_LOG_MAX_ELEMENTS: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'maxLogPerElement',
        '100',
        type=Config.FieldType.NUMERIC,
        help=_('Maximum logs per every log-capable administration element'),
    )
    # Maximum logs per every log-capable administration element
    GENERAL_LOG_MAX_ELEMENTS: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'Max entries for general UDS logs',
        '32000',
        type=Config.FieldType.NUMERIC,
        help=_('Maximum logs entries for general UDS logs (0 = unlimited, use with care)'),
    )

    # Time to restrain a user service in case it gives some errors at some point
    RESTRAINT_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'restrainTime',
        '600',
        type=Config.FieldType.NUMERIC,
        help=_('Time to restrain a user service in case it gives some errors at some point'),
    )
    # Number of errors that must occurr in RESTRAIN_TIME to restrain an user service
    RESTRAINT_COUNT: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'restrainCount',
        '3',
        type=Config.FieldType.NUMERIC,
        help=_('Number of errors that must occurr in "restrainTime" to restrain an user service'),
    )

    # Statistics duration, in days
    STATS_DURATION: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'statsDuration',
        '365',
        type=Config.FieldType.NUMERIC,
        help=_('Statistics duration, in days'),
    )
    # Statisctis accumulation frequency, in seconds
    STATS_ACCUM_FREQUENCY: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'statsAccumFrequency',
        '14400',
        type=Config.FieldType.NUMERIC,
        help=_('Frequency of stats collection in seconds. Default is 4 hours (14400 seconds)'),
    )
    # Statisctis accumulation chunk size, in days
    STATS_ACCUM_MAX_CHUNK_TIME = Config.section(Config.SectionType.GLOBAL).value(
        'statsAccumMaxChunkTime',
        '7',
        type=Config.FieldType.NUMERIC,
        help=_('Maximum number of time to accumulate on one run. Default is 7 (1 week)'),
    )

    # If disallow login showing authenticatiors
    DISALLOW_GLOBAL_LOGIN: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'disallowGlobalLogin',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('If disallow login showing authenticatiors'),
    )

    # Allos preferences access to users
    NOTIFY_REMOVAL_BY_PUB: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'Notify on new publication',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Notify user of existence of a new version of a service on new publication'),
    )

    # Allowed "trusted sources" for request
    TRUSTED_SOURCES: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Trusted Hosts',
        '*',
        type=Config.FieldType.TEXT,
        help=_('Networks considered "trusted" for tunnel requests'),
    )

    # Allow clients to notify their own ip (if set), or use always the request extracted IP
    HONOR_CLIENT_IP_NOTIFY: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'honorClientNotifyIP',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Allow clients to notify their own ip (if set), or use always the request extracted IP'),
    )

    # If there is a proxy in front of us
    BEHIND_PROXY: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Behind a proxy',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('If there is a proxy in front of us (i.e. HAProxy, or any NLB)'),
    )

    # If we use new logout mechanics
    EXCLUSIVE_LOGOUT: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Exclusive Logout',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_(
            'If we use new logout mechanics for osmanagers, where only when the logged in users reaches 0, it is considered "logged out"'
        ),
    )

    # Enable/Disable Actor attack detection ip blocking
    BLOCK_ACTOR_FAILURES: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Block actor failures',
        '1',
        type=Config.FieldType.BOOLEAN,
        help=_('Enable/Disable Actor attack detection ip blocking'),
    )

    # Max session length configuration values
    SESSION_DURATION_ADMIN: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Session timeout for Admin',
        '14400',
        type=Config.FieldType.NUMERIC,
        help=_('Max session length for Admin'),
    )
    SESSION_DURATION_USER: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Session timeout for User',
        '14400',
        type=Config.FieldType.NUMERIC,
        help=_('Max session length for User'),
    )

    RELOAD_TIME: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'Page reload Time',
        '300',
        type=Config.FieldType.NUMERIC,
        help=_('Page reload Time (legacy)'),
    )

    # Custom message for error when limiting by calendar
    LIMITED_BY_CALENDAR_TEXT: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'Calendar access denied text',
        '',
        type=Config.FieldType.TEXT,
        help=_('Custom message for error when limiting by calendar'),
    )  # Defaults to Nothing

    # If convert username to lowercase
    LOWERCASE_USERNAME: Config.Value = Config.section(Config.SectionType.SECURITY).value(
        'Convert username to lowercase',
        '1',
        type=Config.FieldType.BOOLEAN,
        help=_('If convert username to lowercase on logins'),
    )

    # Global UDS ID (common for all servers on the same cluster)
    UDS_ID: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'UDS ID',
        CryptoManager().uuid(),
        type=Config.FieldType.READ,
        help=_('Global UDS ID (common for all servers on the same cluster)'),
    )

    # Site display name & copyright info
    SITE_NAME: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Site name',
        'UDS Enterprise',
        type=Config.FieldType.TEXT,
        help=_('Site display name'),
    )
    SITE_COPYRIGHT: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Site copyright info',
        '© Virtual Cable S.L.U.',
        type=Config.FieldType.TEXT,
        help=_('Site copyright info'),
    )
    SITE_COPYRIGHT_LINK: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Site copyright link',
        'https://www.udsenterprise.com',
        type=Config.FieldType.TEXT,
        help=_('Site copyright link'),
    )
    SITE_LOGO_NAME: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Logo name', 'UDS', type=Config.FieldType.TEXT, help=_('Top navbar logo name')
    )
    SITE_CSS: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'CSS',
        '',
        type=Config.FieldType.LONGTEXT,
        help=_('Custom CSS styles applied to the user accesible site'),
    )
    SITE_INFO: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Site information',
        '',
        type=Config.FieldType.LONGTEXT,
        help=_('Site information'),
    )
    SITE_FILTER_ONTOP: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Show Filter on Top',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Show Filter box for user services on Top or bottom of the page'),
    )
    SITE_FILTER_MIN: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Min. Services to show filter',
        '8',
        type=Config.FieldType.NUMERIC,
        help=_('Minimal User Services needed to show filter'),
    )
    LOGOUT_URL: Config.Value = Config.section(Config.SectionType.CUSTOM).value(
        'Logout URL',
        '',
        type=Config.FieldType.TEXT,
        help=_('Redirect URL after logout. If empty, the user will be redirected to the login page.'),
    )

    EXPERIMENTAL_FEATURES: Config.Value = Config.section(Config.SectionType.GLOBAL).value(
        'Experimental Features',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Enable experimental features. USE WITH CAUTION!!'),
    )

    # Admin config variables
    ADMIN_PAGESIZE: Config.Value = Config.section(Config.SectionType.ADMIN).value(
        'List page size',
        '10',
        type=Config.FieldType.NUMERIC,
        help=_('Number of items per page in admin tables'),
    )
    ADMIN_TRUSTED_SOURCES: Config.Value = Config.section(Config.SectionType.ADMIN).value(
        'Trusted Hosts for Admin',
        '*',
        type=Config.FieldType.TEXT,
        help=_('List of trusted hosts/networks allowed to access the admin interface'),
    )
    ADMIN_ENABLE_USERSERVICES_VNC: Config.Value = Config.section(Config.SectionType.ADMIN).value(
        'Enable VNC for user services',
        '0',
        type=Config.FieldType.BOOLEAN,
        help=_('Enable VNC menu for user services'),
    )

    _initDone = False

    @staticmethod
    def isInitialized():
        return GlobalConfig._initDone

    @staticmethod
    def initialize() -> None:
        if GlobalConfig._initDone is False:
            GlobalConfig._initDone = True
            try:
                # Tries to initialize database data for global config so it is stored asap and get cached for use
                for v in GlobalConfig.__dict__.values():
                    if isinstance(v, Config.Value):
                        v.get()
                        logger.debug('Initialized global config value %s=%s', v.key(), v.get())

                for c in _getLater:
                    logger.debug('Get later: %s', c)
                    c.get()

                _getLater[:] = []

                for c, v in _saveLater:
                    logger.debug('Saving delayed value: %s', c)
                    c.set(v)
                _saveLater[:] = []

                # Process some global config parameters
                # GlobalConfig.UDS_THEME.setParams(['html5', 'semantic'])

            except Exception:
                logger.debug('Config table do not exists!!!, maybe we are installing? :-)')
