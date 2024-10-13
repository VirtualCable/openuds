import typing
import logging

if typing.TYPE_CHECKING:
    import uds.models

logger = logging.getLogger(__name__)


def migrate(apps: typing.Any, schema_editor: typing.Any) -> None:
    """
    Migrates old properties to new ones
    """
    try:
        db_alias = schema_editor.connection.alias
        UserServiceProperty = apps.get_model('uds', 'UserServiceProperty')
        Properties: type['uds.models.Properties'] = apps.get_model('uds', 'Properties')
        # For testing
        # from uds.models import UserServiceProperty, Properties

        for prop in UserServiceProperty.objects.using(db_alias).all():
            Properties.objects.using(db_alias).create(
                owner_id=prop.user_service.uuid, owner_type='userservice', key=prop.name, value=prop.value
            )
    except Exception:
        logger.error('Error migrating properties', exc_info=True)


def rollback(apps: typing.Any, schema_editor: typing.Any) -> None:
    """
    rollback migration
    """
    try:
        db_alias = schema_editor.connection.alias
        UserServiceProperty = apps.get_model('uds', 'UserServiceProperty')
        Properties: type['uds.models.Properties'] = apps.get_model('uds', 'Properties')
        UserService: type['uds.models.UserService'] = apps.get_model('uds', 'UserService')
        # For testing
        # from uds.models import UserServiceProperty, Properties, UserService

        for prop in Properties.objects.using(db_alias).filter(owner_type='userservice'):
            userservice = UserService.objects.using(db_alias).get(uuid=prop.owner_id)
            UserServiceProperty.objects.using(db_alias).create(name=prop.key, value=prop.value, user_service=userservice)
    except Exception:
        logger.error('Error migrating properties', exc_info=True)
