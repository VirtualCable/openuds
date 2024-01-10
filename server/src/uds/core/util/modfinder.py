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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import os.path
import pkgutil
import sys
import importlib
import logging
import typing
import collections.abc

from django.conf import settings

from uds.core import module

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=module.Module)
V = typing.TypeVar('V')

patterns: list[typing.Any] = []


if typing.TYPE_CHECKING:
    from uds.core.util.factory import ModuleFactory


def get_urlpatterns_from_modules() -> list[typing.Any]:
    """Loads dipatcher modules urls to add to django urlpatterns

    Returns:
        list[typing.Any]: List of urlpatterns to add to django urlpatterns
    """
    logger.debug('Looking for dispatching modules')
    if not patterns:
        logger.debug('Looking for patterns')
        try:
            modName = 'uds.dispatchers'
            pkgpath = os.path.dirname(typing.cast(str, sys.modules[modName].__file__))
            for _, name, _ in pkgutil.iter_modules([pkgpath]):
                fullModName = f'{modName}.{name}.urls'
                try:
                    mod = importlib.import_module(fullModName)
                    urlpatterns: list[typing.Any] = getattr(mod, 'urlpatterns')
                    logger.debug('Loaded mod %s, url %s', mod, urlpatterns)
                    # Append patters from mod
                    for up in urlpatterns:
                        patterns.append(up)
                except Exception:
                    logger.error('No patterns found in %s', fullModName)
        except Exception:
            logger.exception('Processing dispatchers loading')

    importlib.invalidate_caches()

    return patterns


def import_modules(mod_name: str, *, package_name: typing.Optional[str] = None) -> None:
    """Dinamycally import children of package

    Args:
        mod_name (str): Name of the module to import
        package_name (str, optional): Name of the package inside the module to import. Defaults to None. If None, the module itself is imported

    Notes:
        This function is used to dinamycally import all submodules inside a submodule (with optional package name).
        
    """
    # Dinamycally import children of this package.
    pkgpath = os.path.dirname(typing.cast(str, sys.modules[mod_name].__file__))
    if package_name:  # Append package name to path and module name
        pkgpath = os.path.join(pkgpath, package_name)
        mod_name = f'{mod_name}.{package_name}'

    logger.info('* Importing modules from %s', pkgpath)
    for _, name, _ in pkgutil.iter_modules([pkgpath]):
        try:
            logger.info('   - Importing module %s.%s ', mod_name, name)
            importlib.import_module('.' + name, mod_name)  # import module
        except Exception as e:
            if settings.DEBUG:
                logger.exception('***** Error importing module %s.%s: %s *****', mod_name, name, e)
            logger.error('   - Error importing module %s.%s: %s', mod_name, name, e)
    logger.info('* Done importing modules from %s', pkgpath)

    importlib.invalidate_caches()


def dynamically_load_and_register_packages(
    adder: collections.abc.Callable[[type[V]], None],
    type_: type[V],
    modName: str,
    *,
    packageName: typing.Optional[str] = None,
    checker: typing.Optional[collections.abc.Callable[[type[V]], bool]] = None,
) -> None:
    '''  Loads all packages from a given package that are subclasses of the given type

    Args:
        adder (collections.abc.Callable[[type[V]], None]): Function to use to add the objects, must support "insert" method
        type_ (type[V]): Type of the objects to load
        modName (str): Name of the package to load
        packageName (str, optional): Name of the package inside the module to import. Defaults to None. If None, the module itself is imported
        checker (collections.abc.Callable[[type[V]], bool], optional): Function to use to check if the class is registrable. Defaults to None.

    Notes:
        The checker function must return True if the class is registrable, False otherwise.

        Example:
            def checker(cls: MyBaseclass) -> bool:
                # Will receive all classes that are subclasses of MyBaseclass
                return cls.__name__.startswith('MyClass')
    '''
    # Ensures all modules under modName (and optionally packageName) are imported
    import_modules(modName, package_name=packageName)

    checkFnc = checker or (lambda x: True)

    def process(classes: collections.abc.Iterable[type[V]]) -> None:
        cls: type[V]
        for cls in classes:
            clsSubCls = cls.__subclasses__()

            if clsSubCls:
                process(clsSubCls)  # recursive add sub classes

            if not checkFnc(cls):
                logger.debug('Node is a not accepted, skipping: %s.%s', cls.__module__, cls.__name__)
                continue

            logger.info('   - Registering %s.%s', cls.__module__, cls.__name__)
            try:
                adder(cls)
            except Exception as e:
                if settings.DEBUG:
                    logger.exception('***** Error registering %s.%s: %s *****', cls.__module__, cls.__name__, e)
                logger.error('   - Error registering %s.%s: %s', cls.__module__, cls.__name__, e)

    logger.info('* Start registering %s', modName)
    process(type_.__subclasses__())
    logger.info('* Done Registering %s', modName)


def dynamically_load_and_register_modules(
    factory: 'ModuleFactory[T]',
    type_: type[T],
    modName: str,
) -> None:
    ''' Loads and registers all modules from a given package that are subclasses of the given type

    This is an specialisation of dynamicLoadAndRegisterPackages that uses a ModuleFactory to register the modules

    Args:
        factory (ModuleFactory): Factory to use to create the objects, must support "insert" method
        type_ (type[T]): Type of the objects to load
        modName (str): Name of the package to load
    '''
    dynamically_load_and_register_packages(
        factory.insert, type_, modName, checker=lambda x: not x.is_base
    )
