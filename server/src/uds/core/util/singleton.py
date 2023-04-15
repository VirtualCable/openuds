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
    def __init__(cls, *args, **kwargs) -> None:
        cls._instance = None
        super().__init__(*args, **kwargs)

    def __call__(cls, *args, **kwargs) -> typing.Any:
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance
