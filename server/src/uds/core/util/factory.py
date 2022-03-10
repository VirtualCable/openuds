import typing

from uds.core.util import singleton
from uds.core import module

import logging

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=module.Module)


class ModuleFactory(typing.Generic[T], metaclass=singleton.Singleton):
    '''
    Module Factory class.
    '''

    _objects: typing.MutableMapping[str, typing.Type[T]]

    def __init__(self) -> None:
        self._objects = {}

    def providers(self) -> typing.Mapping[str, typing.Type[T]]:
        '''
        Returns all providers.
        '''
        return self._objects

    def insert(self, type_: typing.Type[T]) -> None:
        '''
        Inserts an object into the factory.
        '''
        # logger.debug('Adding %s as %s', type_.type(), type_.__module__)
        typeName = type_.type().lower()

        if typeName in self._objects:
            logger.debug('%s already registered as %s', type_, self._objects[typeName])
            return

        self._objects[typeName] = type_

    def get(self, typeName: str) -> typing.Optional[typing.Type[T]]:
        '''
        Returns an object from the factory.
        '''
        return self._objects.get(typeName.lower())

    # aliases for get
    lookup = get
    __getitem__ = get
