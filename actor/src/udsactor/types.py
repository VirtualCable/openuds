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

class ActorOsConfigurationType(typing.NamedTuple):
    action: str
    name: str
    username: typing.Optional[str] = None
    password: typing.Optional[str] = None
    new_password: typing.Optional[str] = None
    ad: typing.Optional[str] = None
    ou: typing.Optional[str] = None

class ActorDataConfigurationType(typing.NamedTuple):
    unique_id: typing.Optional[str] = None
    max_idle: typing.Optional[int] = None
    os: typing.Optional[ActorOsConfigurationType] = None

class ActorConfigurationType(typing.NamedTuple):
    host: str
    validateCertificate: bool
    master_token: typing.Optional[str] = None
    own_token: typing.Optional[str] = None

    pre_command: typing.Optional[str] = None
    runonce_command: typing.Optional[str] = None
    post_command: typing.Optional[str] = None

    log_level: int = 0

    config: typing.Optional[ActorDataConfigurationType] = None

    data: typing.Optional[typing.Dict[str, typing.Any]] = None

class InitializationResultType(ActorDataConfigurationType):
    own_token: typing.Optional[str] = None
