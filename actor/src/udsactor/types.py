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
    custom: typing.Optional[typing.Mapping[str, typing.Any]]

class ActorDataConfigurationType(typing.NamedTuple):
    unique_id: typing.Optional[str] = None
    os: typing.Optional[ActorOsConfigurationType] = None

class ActorConfigurationType(typing.NamedTuple):
    host: str
    validateCertificate: bool
    actorType: typing.Optional[str] = None
    master_token: typing.Optional[str] = None
    own_token: typing.Optional[str] = None
    restrict_net: typing.Optional[str] = None

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
    alias_token: typing.Optional[str] = None

class LoginResultInfoType(typing.NamedTuple):
    ip: str
    hostname: str
    dead_line: typing.Optional[int]
    max_idle: typing.Optional[int]
    session_id: typing.Optional[str]

    @property
    def logged_in(self) -> bool:
        return bool(self.session_id)

class ClientInfo(typing.NamedTuple):
    url: str
    session_id: str

class CertificateInfoType(typing.NamedTuple):
    private_key: str
    server_certificate: str
    password: str
    ciphers: str
