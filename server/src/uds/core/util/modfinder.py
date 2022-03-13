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

from uds.core import module

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=module.Module)
V = typing.TypeVar('V')

patterns: typing.List[typing.Any] = []


if typing.TYPE_CHECKING:
    from uds.core.util.factory import ModuleFactory


def loadModulesUrls() -> typing.List[typing.Any]:
    logger.debug('Looking for dispatching modules')
    if not patterns:
        logger.debug('Looking for patterns')
        try:
            modName = 'uds.dispatchers'
            pkgpath = os.path.dirname(typing.cast(str, sys.modules[modName].__file__))
            for _, name, _ in pkgutil.iter_modules([pkgpath]):
                fullModName = '{}.{}.urls'.format(modName, name)
                try:
                    mod = importlib.import_module(fullModName)
                    urlpatterns: typing.List[typing.Any] = getattr(mod, 'urlpatterns')
                    logger.debug('Loaded mod %s, url %s', mod, urlpatterns)
                    # Append patters from mod
                    for up in urlpatterns:
                        patterns.append(up)
                except Exception:
                    logger.exception('Loading patterns')
        except Exception:
            logger.exception('Processing dispatchers loading')

    importlib.invalidate_caches()

    return patterns


def importModules(modName: str, *, packageName: typing.Optional[str] = None) -> None:
    # Dinamycally import children of this package.
    pkgpath = os.path.dirname(typing.cast(str, sys.modules[modName].__file__))
    if packageName:
        pkgpath = os.path.join(pkgpath, packageName)
        modName = '{}.{}'.format(modName, packageName)

    logger.info('* Importing modules from %s', pkgpath)
    for _, name, _ in pkgutil.iter_modules([pkgpath]):
        logger.info('   - Importing module %s.%s ', modName, name)
        importlib.import_module('.' + name, modName)  # import module
    logger.info('* Done importing modules from %s', pkgpath)

    importlib.invalidate_caches()


def dynamicLoadAndRegisterPackages(
    adder: typing.Callable[[typing.Type[V]], None],
    type_: typing.Type[V],
    modName: str,
    *,
    packageName: typing.Optional[str] = None,
    checker: typing.Optional[typing.Callable[[typing.Type[V]], bool]] = None,
) -> None:
    '''
    Loads all packages from a given package that are subclasses of the given type
    param adder: Function to use to add the objects, must support "insert" method
    param type_: Type of the objects to load
    param modName: Name of the package to load
    param checker: Function to use to check if the class is registrable
    '''
    importModules(modName, packageName=packageName)

    checkFnc = checker or (lambda x: True)

    def process(classes: typing.Iterable[typing.Type]) -> None:
        cls: typing.Type[V]
        for cls in classes:
            clsSubCls = cls.__subclasses__()

            if clsSubCls:
                process(clsSubCls)

            if not checkFnc(cls):
                logger.debug('Node is a base, skipping: %s', cls.__module__)
                continue

            logger.info('   - Registering %s.%s', cls.__module__, cls.__name__)
            adder(cls)

    logger.info('* Start registering %s', modName)
    process(type_.__subclasses__())
    logger.info('* Done Registering %s', modName)


def dynamicLoadAndRegisterModules(
    factory: 'ModuleFactory',
    type_: typing.Type[T],
    modName: str,
) -> None:
    '''
    Loads all modules from a given package that are subclasses of the given type
    param factory: Factory to use to create the objects, must support "insert" method
    param type_: Type of the objects to load
    param modName: Name of the package to load
    '''
    dynamicLoadAndRegisterPackages(
        factory.insert, type_, modName, checker=lambda x: not x.isBase
    )
