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



# FAKE post
def post(path, data):
    if path == urls.LOGIN:
        return AUTH

    raise Exception('Unknown FAKE URL on POST')

# FAKE get
def get(path):
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

    raise Exception('Unknown FAKE URL on GET')
