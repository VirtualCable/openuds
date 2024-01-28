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

    def register(self, type_name: str, type_: type[V]) -> None:
        '''
        Inserts an object into the factory.
        '''
        if type_name in self._objects:
            logger.debug('%s already registered as %s', type_, self._objects[type_name])
            return

        self._objects[type_name.lower()] = type_

    def get_type(self, type_name: str) -> typing.Optional[type[V]]:
        '''
        Returns an object from the factory.
        '''
        return self._objects.get(type_name.lower())

    def has(self, type_name: str) -> bool:
        '''
        Returns an object from the factory.
        '''
        return type_name.lower() in self._objects

    def items(self) -> collections.abc.ItemsView[str, type[V]]:
        '''
        Returns an object from the factory.
        '''
        return self._objects.items()

    def keys(self) -> collections.abc.KeysView[str]:
        '''
        Returns an object from the factory.
        '''
        return self._objects.keys()

    def values(self) -> collections.abc.ValuesView[type[V]]:
        '''
        Returns an object from the factory.
        '''
        return self._objects.values()

    # aliases for get
    lookup = get_type
    __getitem__ = get_type
    __setitem__ = register
    __contains__ = has

    # Note that there is no remove method, as we don't intend to remove once added to a factory


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
        super().register(type_.get_type().lower(), type_)
