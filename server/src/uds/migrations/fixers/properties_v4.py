import typing
import collections.abc
import logging

if typing.TYPE_CHECKING:
    import uds.models

logger = logging.getLogger(__name__)


def migrate(apps: typing.Any, schema_editor: typing.Any) -> None:
    """
    Migrates old properties to new ones
    """
    try:
        UserServiceProperty = apps.get_model('uds', 'UserServiceProperty')
        Properties: type['uds.models.Properties'] = apps.get_model('uds', 'Properties')
        # For testing
        # from uds.models import UserServiceProperty, Properties

        for prop in UserServiceProperty.objects.all():
            Properties.objects.create(
                owner_id=prop.user_service.uuid, owner_type='userservice', key=prop.name, value=prop.value
            )
    except Exception:
        logger.error('Error migrating properties', exc_info=True)


def rollback(apps: typing.Any, schema_editor: typing.Any) -> None:
    """
    rollback migration
    """
    try:
        UserServiceProperty = apps.get_model('uds', 'UserServiceProperty')
        Properties: type['uds.models.Properties'] = apps.get_model('uds', 'Properties')
        UserService: type['uds.models.UserService'] = apps.get_model('uds', 'UserService')
        # For testing
        # from uds.models import UserServiceProperty, Properties, UserService

        for prop in Properties.objects.filter(owner_type='userservice'):
            userService = UserService.objects.get(uuid=prop.owner_id)
            UserServiceProperty.objects.create(name=prop.key, value=prop.value, user_service=userService)
    except Exception:
        logger.error('Error migrating properties', exc_info=True)
