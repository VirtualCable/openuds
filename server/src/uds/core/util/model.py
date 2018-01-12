"""
Created on Sep 15, 2014

@author: dkmaster
"""
from __future__ import unicode_literals
from uds.core.managers import cryptoManager

import six


def generateUuid():
    """
    Generates a ramdom uuid for models default
    """
    return cryptoManager().uuid().lower()


def processUuid(uuid):
    if isinstance(uuid, six.binary_type):
        uuid = uuid.decode('utf8')
    return uuid.lower()
