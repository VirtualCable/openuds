import typing
import enum

from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model


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

    def get_max_elements(self) -> int:
        """
        if True, this type of log will be limited by number of log entries
        """
        from uds.core.util.config import GlobalConfig  # pylint: disable=import-outside-toplevel

        if self == LogObjectType.SYSLOG:
            return GlobalConfig.GENERAL_LOG_MAX_ELEMENTS.getInt()
        return GlobalConfig.INDIVIDIAL_LOG_MAX_ELEMENTS.getInt()

# Dict for translations
MODEL_TO_TYPE: typing.Mapping[typing.Type['Model'], LogObjectType] = {
    models.UserService: LogObjectType.USERSERVICE,
    models.ServicePoolPublication: LogObjectType.PUBLICATION,
    models.ServicePool: LogObjectType.SERVICEPOOL,
    models.Service: LogObjectType.SERVICE,
    models.Provider: LogObjectType.PROVIDER,
    models.User: LogObjectType.USER,
    models.Group: LogObjectType.GROUP,
    models.Authenticator: LogObjectType.AUTHENTICATOR,
    models.MetaPool: LogObjectType.METAPOOL,
}
