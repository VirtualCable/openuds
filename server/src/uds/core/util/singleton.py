import typing

class Singleton(type):
    '''
    Metaclass for singleton pattern
    Usage:
    
    class MyClass(metaclass=Singleton):
        ...
    '''
    _instance: typing.Optional[typing.Any]

    # We use __init__ so we customise the created class from this metaclass    
    def __init__(self, *args, **kwargs) -> None:
        self._instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs) -> typing.Any:
        if self._instance is None:
            self._instance = super().__call__(*args, **kwargs)
        return self._instance
