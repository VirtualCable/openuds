# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import os.path
import pkgutil
import sys
import importlib
import logging
import typing
import collections.abc

from django.conf import settings

if typing.TYPE_CHECKING:
    from uds.core.util.factory import ModuleFactory
    from uds.core import module

from uds.core import module

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound='module.Module')
V = typing.TypeVar('V')

patterns: list[typing.Any] = []


def get_urlpatterns_from_modules() -> list[typing.Any]:
    """Loads dipatcher modules urls to add to django urlpatterns

    Returns:
        list[typing.Any]: List of urlpatterns to add to django urlpatterns
    """
    logger.debug('Looking for dispatching modules')
    if not patterns:
        logger.debug('Looking for patterns')
        try:
            module_name = 'uds.dispatchers'
            package_path = os.path.dirname(typing.cast(str, sys.modules[module_name].__file__))
            for _, name, _ in pkgutil.iter_modules([package_path]):
                module_fullname = f'{module_name}.{name}.urls'
                try:
                    mod = importlib.import_module(module_fullname)
                    urlpatterns: list[typing.Any] = getattr(mod, 'urlpatterns')
                    logger.debug('Loaded mod %s, url %s', mod, urlpatterns)
                    # Append patters from mod
                    for up in urlpatterns:
                        patterns.append(up)
                except Exception:
                    logger.error('No patterns found in %s', module_fullname)
        except Exception:
            logger.exception('Processing dispatchers loading')

    importlib.invalidate_caches()

    return patterns


def import_modules(module_name: str, *, package_name: typing.Optional[str] = None) -> None:
    """Dinamycally import children of package

    Args:
        mod_name (str): Name of the module to import
        package_name (str, optional): Name of the package inside the module to import. Defaults to None. If None, the module itself is imported

    Notes:
        This function is used to dinamycally import all submodules inside a submodule (with optional package name).

    """
    # Dinamycally import children of the package.
    package_path = os.path.dirname(typing.cast(str, sys.modules[module_name].__file__))
    if package_name:  # Append package name to path and module name
        package_path = os.path.join(package_path, package_name)
        module_name = f'{module_name}.{package_name}'

    logger.info('* Importing modules from %s', package_path)
    for _, name, _ in pkgutil.iter_modules([package_path]):
        try:
            logger.info('   - Importing module %s.%s ', module_name, name)
            importlib.import_module('.' + name, module_name)  # import module
        except Exception as e:
            if settings.DEBUG:
                logger.exception('***** Error importing module %s.%s: %s *****', module_name, name, e)
            logger.error('   - Error importing module %s.%s: %s', module_name, name, e)
    logger.info('* Done importing modules from %s', package_path)

    importlib.invalidate_caches()


def dynamically_load_and_register_packages(
    adder: collections.abc.Callable[[type[V]], None],
    type_: type[V],
    module_name: str,
    *,
    package_name: typing.Optional[str] = None,
    checker: typing.Optional[collections.abc.Callable[[type[V]], bool]] = None,
) -> None:
    '''Loads all packages from a given package that are subclasses of the given type

    Args:
        adder (collections.abc.Callable[[type[V]], None]): Function to use to add the objects, must support "insert" method
        type_ (type[V]): Type of the objects to load
        module_name (str): Name of the package to load
        package_name (str, optional): Name of the package inside the module to import. Defaults to None. If None, the module itself is imported
        checker (collections.abc.Callable[[type[V]], bool], optional): Function to use to check if the class is registrable. Defaults to None.

    Notes:
        The checker function must return True if the class is registrable, False otherwise.

        Example:
            def checker(cls: MyBaseclass) -> bool:
                # Will receive all classes that are subclasses of MyBaseclass
                return cls.__name__.startswith('MyClass')
    '''
    # Ensures all modules under modName (and optionally packageName) are imported
    import_modules(module_name, package_name=package_name)

    check_function: collections.abc.Callable[[type[V]], bool] = checker or (lambda x: True)

    def _process(classes: collections.abc.Iterable[type[V]]) -> None:
        cls: type[V]
        for cls in classes:
            clsSubCls = cls.__subclasses__()

            if clsSubCls:
                _process(clsSubCls)  # recursive add sub classes

            if not check_function(cls):
                logger.debug('Node is a not accepted, skipping: %s.%s', cls.__module__, cls.__name__)
                continue

            logger.info('   - Registering %s.%s', cls.__module__, cls.__name__)
            try:
                adder(cls)
            except Exception as e:
                if settings.DEBUG:
                    logger.exception('***** Error registering %s.%s: %s *****', cls.__module__, cls.__name__, e)
                logger.error('   - Error registering %s.%s: %s', cls.__module__, cls.__name__, e)

    logger.info('* Start registering %s', module_name)
    _process(type_.__subclasses__())
    logger.info('* Done Registering %s', module_name)


def dynamically_load_and_register_modules(
    factory: 'ModuleFactory[T]',
    type_: type[T],
    module_name: str,
) -> None:
    '''Loads and registers all modules from a given package that are subclasses of the given type

    This is an specialisation of dynamicLoadAndRegisterPackages that uses a ModuleFactory to register the modules

    Args:
        factory (ModuleFactory): Factory to use to create the objects, must support "insert" method
        type_ (type[T]): Type of the objects to load
        module_name (str): Name of the package to load
    '''

    def _checker(cls: type[T]) -> bool:
        # Will receive all classes that are subclasses of type_ and is not the marked as base
        # We could have check here if it has subclasses, but we want the versatility of the mark
        # to allow overriding a service, for example, with some new functionality but not disabling the original one
        return not cls.is_base

    dynamically_load_and_register_packages(
        factory.insert,
        type_,
        module_name,
        checker=_checker,
    )
