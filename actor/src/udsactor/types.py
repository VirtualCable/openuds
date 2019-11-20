import typing

class InterfaceInfo(typing.NamedTuple):
    name: str
    mac: typing.Optional[str]
    ip: typing.Optional[str]
