import typing
import collections.abc
import functools
import enum

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model


class LogLevel(enum.IntEnum):
    OTHER = 10000
    DEBUG = 20000
    INFO = 30000
    WARNING = 40000
    ERROR = 50000
    CRITICAL = 60000

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    @staticmethod
    def from_str(level: str) -> 'LogLevel':
        try:
            return LogLevel[level.upper()]
        except Exception:
            # logger.error('Error getting log level from string: %s', e)
            return LogLevel.OTHER

    @staticmethod
    def from_int(level: int) -> 'LogLevel':
        try:
            return LogLevel(level)
        except ValueError:
            return LogLevel.OTHER

    @staticmethod
    def from_actor_level(level: int) -> 'LogLevel':
        """
        Returns the log level for actor log level
        """
        return [LogLevel.DEBUG, LogLevel.INFO, LogLevel.ERROR, LogLevel.CRITICAL][level % 4]

    @staticmethod
    def from_logging_level(level: int) -> 'LogLevel':
        """
        Returns the log level for logging log level
        """
        return [
            LogLevel.OTHER,
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ][level // 10]

    # Return all Log levels as tuples of (level value, level name)
    @staticmethod
    def all() -> list[tuple[int, str]]:
        return [(level.value, level.name) for level in LogLevel]

    # Rteturns "interesting" log levels
    @staticmethod
    def interesting() -> list[tuple[int, str]]:
        """Returns "interesting" log levels

        Interesting log levels are those that are ABOBE INFO level (that is, errors, etc..)
        """
        return [(level.value, level.name) for level in LogLevel if level.value > LogLevel.INFO.value]


class LogSource(enum.StrEnum):
    INTERNAL = 'internal'
    ACTOR = 'actor'
    TRANSPORT = 'transport'
    OSMANAGER = 'osmanager'
    UNKNOWN = 'unknown'
    WEB = 'web'
    ADMIN = 'admin'
    SERVICE = 'service'
    SERVER = 'server'
    REST = 'rest'
    LOGS = 'logs'
    MODULE = 'module'


# Note: Once assigned a value, do not change it, as it will break the log
class LogObjectType(enum.IntEnum):
    USERSERVICE = 0
    PUBLICATION = 1
    SERVICEPOOL = 2
    SERVICE = 3
    PROVIDER = 4
    USER = 5
    GROUP = 6
    AUTHENTICATOR = 7
    METAPOOL = 8
    SYSLOG = 9
    SERVER = 10

    @functools.lru_cache(maxsize=16)
    def get_max_elements(self) -> int:
        """
        Returns the max number of elements to be stored for this type of log
        """
        from uds.core.util.config import GlobalConfig  # pylint: disable=import-outside-toplevel

        if self == LogObjectType.SYSLOG:
            return GlobalConfig.GENERAL_LOG_MAX_ELEMENTS.as_int()
        return GlobalConfig.INDIVIDIAL_LOG_MAX_ELEMENTS.as_int()

    @staticmethod
    def get_type_from_model(model: 'Model') -> 'LogObjectType|None':
        """
        Returns the type of log object from the model
        """
        from uds import models

        # Dict for translations
        _MODEL_TO_TYPE: typing.Final[collections.abc.Mapping[type['Model'], 'LogObjectType']] = {
            models.UserService: LogObjectType.USERSERVICE,
            models.ServicePoolPublication: LogObjectType.PUBLICATION,
            models.ServicePool: LogObjectType.SERVICEPOOL,
            models.Service: LogObjectType.SERVICE,
            models.Server: LogObjectType.SERVER,
            models.Provider: LogObjectType.PROVIDER,
            models.User: LogObjectType.USER,
            models.Group: LogObjectType.GROUP,
            models.Authenticator: LogObjectType.AUTHENTICATOR,
            models.MetaPool: LogObjectType.METAPOOL,
        }

        return _MODEL_TO_TYPE.get(type(model), None)
