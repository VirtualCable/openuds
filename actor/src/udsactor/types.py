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
    data: typing.Optional[typing.Dict[str, str]] = None
