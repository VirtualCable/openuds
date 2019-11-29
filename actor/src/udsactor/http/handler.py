import typing

if typing.TYPE_CHECKING:
    from ..service import CommonService

class Handler:
    _service: 'CommonService'
    _method: str
    _params: typing.MutableMapping[str, str]

    def __init__(self, service: 'CommonService', method: str, params: typing.MutableMapping[str, str]):
        self._service = service
        self._method = method
        self._params = params

    
