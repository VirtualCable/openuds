import typing
import collections.abc
import logging

from uds.core.util import singleton
from uds.core import module


logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=module.Module)
V = typing.TypeVar('V')


class Factory(typing.Generic[V], metaclass=singleton.Singleton):
    '''
    Generic factory class.
    '''

    _objects: collections.abc.MutableMapping[str, type[V]]

    def __init__(self) -> None:
        self._objects = {}

    def objects(self) -> collections.abc.Mapping[str, type[V]]:
        '''
        Returns all providers.
        '''
        return self._objects

    def put(self, typeName: str, type_: type[V]) -> None:
        '''
        Inserts an object into the factory.
        '''
        if typeName in self._objects:
            logger.debug('%s already registered as %s', type_, self._objects[typeName])
            return

        self._objects[typeName.lower()] = type_

    def get(self, typeName: str) -> typing.Optional[type[V]]:
        '''
        Returns an object from the factory.
        '''
        return self._objects.get(typeName.lower())

    # aliases for get
    lookup = get
    __getitem__ = get


class ModuleFactory(Factory[T]):
    '''
    Module Factory class.
    '''

    def providers(self) -> collections.abc.Mapping[str, type[T]]:
        '''
        Returns all providers.
        '''
        return super().objects()

    def insert(self, type_: type[T]) -> None:
        '''
        Inserts an object into the factory.
        '''
        # logger.debug('Adding %s as %s', type_.type(), type_.__module__)
        super().put(type_.getType().lower(), type_)
