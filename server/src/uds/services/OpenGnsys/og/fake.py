# -*- coding: utf-8 -*-

#
# Copyright (c) 2017 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals
from . import urls
import copy
import random
import six
import logging

__updated__ = '2017-05-19'

logger = logging.getLogger(__name__)

AUTH = {
    "userid": 1001,
    "apikey": "fakeAPIKeyJustForDeveloping"
}

INFO = {
  "project": "OpenGnsys",
  "version": "1.1.0pre",
  "release": "r5299",
  "services": [
    "server",
    "repository",
    "tracker"
  ],
  "oglive": [
    {
      "distribution": "xenial",
      "kernel": "4.8.0-39-generic",
      "architecture": "amd64",
      "revision": "r5225",
      "directory": "ogLive-xenial-4.8.0-amd64-r5225",
      "iso": "ogLive-xenial-4.8.0-39-generic-amd64-r5225.iso"
    },
    {
      "iso": "ogLive-precise-3.2.0-23-generic-r4820.iso",
      "directory": "ogLive-precise-3.2.0-i386-r4820",
      "revision": "r4820",
      "architecture": "i386",
      "kernel": "3.2.0-23-generic",
      "distribution": "precise"
    }  ]
}

OUS = [
  {
    "id": "1",
    "name": "Unidad Organizativa (Default)"
  },
  {
    "id": "2",
    "name": "Unidad Organizatva VACIA"
  },
]

LABS = [
  {
    "id": "1",
    "name": "Sala de control",
    "inremotepc": True,
    "group": {
      "id": "0"
    },
    "ou": {
      "id": "1"
    }
  },
  {
    "id": "2",
    "name": "Sala de computación cuántica",
    "inremotepc": True,
    "group": {
      "id": "0"
    },
    "ou": {
      "id": "1"
    }
  }
]

IMAGES = [
  {
    "id": "1",
    "name": "Basica1604",
    "inremotepc": True,
    "ou": {
      "id": "1"
    }
  },
  {
    "id": "2",
    "name": "Ubuntu16",
    "inremotepc": True,
    "ou": {
      "id": "1"
    }
  },
  {
    "id": "3",
    "name": "Ubuntu64 Not in Remote",
    "inremotepc": False,
    "ou": {
      "id": "1"
    }
  },
  {
    "id": "4",
    "name": "Ubuntu96 Not In Remote",
    "inremotepc": False,
    "ou": {
      "id": "1"
    }
  },
]

RESERVE = {
  "id": 4,
  "name": "pcpruebas",
  "mac": "4061860521FE",
  "ip": "10.1.14.31",
  "lab": {
    "id": 1
  },
  "ou": {
    "id": 1
  }
}

UNRESERVE = ''

STATUS_OFF = {
  "id": 4,
  "ip": "10.1.14.31",
  "status": "off",
  "loggedin": False
}

# A couple of status for testing
STATUS_READY_LINUX = {
  "id": 4,
  "ip": "10.1.14.31",
  "status": "linux",
  "loggedin": False
}

STATUS_READY_WINDOWS = {
  "id": 4,
  "ip": "10.1.14.31",
  "status": "windows",
  "loggedin": False
}

# FAKE post
def post(path, data, errMsg):
    logger.info('FAKE POST request to {} with {} data. ({})'.format(path, data, errMsg))
    if path == urls.LOGIN:
        return AUTH
    elif path == urls.RESERVE.format(ou=1, image=1) or path == urls.RESERVE.format(ou=1, image=2):
        res = copy.deepcopy(RESERVE)
        res['name'] += six.text_type(random.randint(5000, 100000))
        res['mac'] = ''.join(random.choice('0123456789ABCDEF') for __ in range(12))
        return res

    raise Exception('Unknown FAKE URL on POST: {}'.format(path))

# FAKE get
def get(path, errMsg):
    logger.info('FAKE GET request to {}. ({})'.format(path, errMsg))
    if path == urls.INFO:
        return INFO
    elif path == urls.OUS:
        return OUS
    elif path == urls.LABS.format(ou=1):
        return LABS
    elif path == urls.LABS.format(ou=2):
        return []  # Empty
    elif path == urls.IMAGES.format(ou=1):
        return IMAGES
    elif path == urls.IMAGES.format(ou=2):
        return []
    elif path[-6:] == 'status':
        rnd = random.randint(0, 100)
        if rnd < 25:
            return STATUS_READY_LINUX
        return STATUS_OFF

    raise Exception('Unknown FAKE URL on GET: {}'.format(path))

def delete(path, errMsg):
    logger.info('FAKE DELETE request to {}. ({})'.format(path, errMsg))
    # Right now, only "unreserve" uses delete, so simply return
    return UNRESERVE
    # raise Exception('Unknown FAKE URL on DELETE: {}'.format(path))
