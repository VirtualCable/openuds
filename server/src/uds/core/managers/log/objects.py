import typing
import collections.abc
import functools
import enum

from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

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
            return GlobalConfig.GENERAL_LOG_MAX_ELEMENTS.getInt()
        return GlobalConfig.INDIVIDIAL_LOG_MAX_ELEMENTS.getInt()

# Dict for translations
MODEL_TO_TYPE: collections.abc.Mapping[type['Model'], LogObjectType] = {
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
