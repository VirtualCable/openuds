# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

import logging

logger = logging.getLogger(__name__)
'''
Service modules for uds are contained inside this package.
To create a new service module, you will need to follow this steps:
    1.- Create the service module, probably based on an existing one
    2.- Insert the module package as child of this package
    3.- Import the class of your service module at __init__. For example::
        from Service import SimpleService
    4.- Done. At Server restart, the module will be recognized, loaded and treated

The registration of modules is done locating subclases of :py:class:`uds.core.auths.Authentication`

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''


def __init__():
    """
    This imports all packages that are descendant of this package, and, after that,
    it register all subclases of service provider as
    """
    import os.path
    import pkgutil
    import sys

    # Dinamycally import children of this package. The __init__.py files must register, if needed, inside ServiceProviderFactory
    pkgpath = os.path.dirname(sys.modules[__name__].__file__)
    for _, name, _ in pkgutil.iter_modules([pkgpath]):
        try:
            logger.info('Loading dispatcher {}'.format(name))
            __import__(name, globals(), locals(), [], 1)
        except Exception:
            logger.exception('Loading dispatcher {}'.format(name))

    logger.debug('Dispatchers initialized')


__init__()
