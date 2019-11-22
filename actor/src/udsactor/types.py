import typing

class InterfaceInfoType(typing.NamedTuple):
    name: str
    mac: typing.Optional[str]
    ip: typing.Optional[str]

class AuthenticatorType(typing.NamedTuple):
    authId: str
    authSmallName: str
    auth: str
    type: str
    priority: int
    isCustom: bool

class ActorConfigurationType(typing.NamedTuple):
    host: str
    validateCertificate: bool
    master_token: typing.Optional[str] = None
    own_token: typing.Optional[str] = None

    pre_command: typing.Optional[str] = None
    runonce_command: typing.Optional[str] = None
    post_command: typing.Optional[str] = None

    log_level: int = 0

    data: typing.Optional[typing.Dict[str, str]] = None
