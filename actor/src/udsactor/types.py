import typing

MANAGED = 'managed'
UNMANAGED = 'unmanaged'

class InterfaceInfoType(typing.NamedTuple):
    name: str
    mac: str
    ip: str

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
    os: typing.Optional[ActorOsConfigurationType] = None

class ActorConfigurationType(typing.NamedTuple):
    host: str
    validateCertificate: bool
    actorType: typing.Optional[str] = None
    master_token: typing.Optional[str] = None
    own_token: typing.Optional[str] = None

    pre_command: typing.Optional[str] = None
    runonce_command: typing.Optional[str] = None
    post_command: typing.Optional[str] = None

    log_level: int = 2

    config: typing.Optional[ActorDataConfigurationType] = None

    data: typing.Optional[typing.Dict[str, typing.Any]] = None

class InitializationResultType(typing.NamedTuple):
    own_token: typing.Optional[str] = None
    unique_id: typing.Optional[str] = None
    os: typing.Optional[ActorOsConfigurationType] = None

class LoginResultInfoType(typing.NamedTuple):
    ip: str
    hostname: str
    dead_line: typing.Optional[int]
    max_idle: typing.Optional[int]  # Not provided by broker

class CertificateInfoType(typing.NamedTuple):
    private_key: str
    server_certificate: str
    password: str
