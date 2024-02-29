import typing


class Singleton(type):
    '''
    Metaclass for singleton pattern
    Usage:

    class MyClass(metaclass=Singleton):
        ...
    '''

    _instance: typing.Optional[typing.Any]

    # Ensure "_instance" is not inherited
    def __init__(cls: 'Singleton', *args: typing.Any, **kwargs: typing.Any) -> None:
        """
        Initialize the Singleton metaclass for each class that uses it
        """
        cls._instance = None
        super().__init__(*args, **kwargs)

    def __call__(cls: 'Singleton', *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance
