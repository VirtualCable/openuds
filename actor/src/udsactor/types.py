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
