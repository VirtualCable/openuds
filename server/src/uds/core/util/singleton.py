import typing

class Singleton(type):
    '''
    Metaclass for singleton pattern
    Usage:
    
    class MyClass(metaclass=Singleton):
        ...
    '''
    __instance: typing.Optional[typing.Any]

    # We use __init__ so we customise the created class from this metaclass    
    def __init__(self, *args, **kwargs) -> None:
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs) -> typing.Any:
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
        return self.__instance
