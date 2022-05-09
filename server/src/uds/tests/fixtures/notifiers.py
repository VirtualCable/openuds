import typing

from uds import models
from uds.core.util import states
from uds.core.managers.crypto import CryptoManager

# Counters so we can reinvoke the same method and generate new data
glob = {'user_id': 0, 'group_id': 0}


def createEmailNotifier(
    host: typing.Optional[str] = None,
    port: int = 0,
    username: typing.Optional[str] = None,
    password: typing.Optional[str] = None,
    fromEmail: typing.Optional[str] = None,
    toEmail: typing.Optional[str] = None,
    enableHtml: bool = False,
    security: typing.Optional[str] = None,
) -> models.Notifier:
    from uds.notifiers.email.notifier import EmailNotifier

    notifier = models.Notifier()
    notifier.name = 'Testing email notifier'
    notifier.comments = 'Testing email notifier'
    notifier.data_type = EmailNotifier.typeType
    instance: EmailNotifier = typing.cast(EmailNotifier, notifier.getInstance())
    # Fill up fields
    instance.hostname.value = (host or 'localhost') + (
        '' if port == 0 else ':' + str(port)
    )
    instance.username.value = username or ''
    instance.password.value = password or ''
    instance.fromEmail.value = fromEmail or 'from@email.com'
    instance.toEmail.value = toEmail or 'to@email.com'
    instance.enableHTML.value = enableHtml
    instance.security.value = security or 'none'
    # Save
    notifier.data = instance.serialize()
    notifier.save()

    return notifier
