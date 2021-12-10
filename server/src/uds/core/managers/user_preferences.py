# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# This module is deprecated and probably will be removed soon

import logging
import typing

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from uds.core.util import singleton

if typing.TYPE_CHECKING:
    from uds.models import User

logger = logging.getLogger(__name__)

# UserPrefs is DEPRECATED
# Currently not used anywhere
class UserPrefsManager(metaclass=singleton.Singleton):
    _prefs: typing.Dict[str, typing.Dict]

    def __init__(self):
        self._prefs = {}

    @staticmethod
    def manager() -> 'UserPrefsManager':
        return UserPrefsManager()

    def __nameFor(self, module, name):
        return module + "_" + name

    def registerPrefs(
        self, modName: str, friendlyModName: str, prefs: typing.Any
    ) -> None:
        """
        Register an array of preferences for a module
        """
        self._prefs[modName] = {'friendlyName': friendlyModName, 'prefs': prefs}

    def getPreferencesForUser(self, modName: str, user: 'User'):
        """
        Gets the preferences for an specified module for the user
        """
        # logger.debug('Self prefs: %s', self._prefs)
        prefs = {}
        for up in user.preferences.filter(module=modName):  # type: ignore
            prefs[up.name] = up.value
        for p in self._prefs[modName]['prefs']:
            if p.getName() not in prefs:
                prefs[p.getName()] = p.getDefValue()
        logger.debug('Preferences: %s', prefs)
        return prefs

    def setPreferenceForUser(
        self, user: 'User', modName: str, prefName: str, value: str
    ):
        try:
            user.preferences.create(module=modName, name=prefName, value=value)  # type: ignore
        except Exception:  # Already exits, update it
            user.preferences.filter(module=modName, name=prefName).update(value=value)  # type: ignore

    def getHtmlForUserPreferences(self, user: 'User'):
        # First fill data for all preferences
        data = {}
        for up in user.preferences.all().order_by('module'):  # type: ignore
            data[self.__nameFor(up.module, up.name)] = up.value
        res = ''
        for mod, v in sorted(self._prefs.items()):
            form = forms.Form()
            for p in v['prefs']:
                name = self.__nameFor(mod, p.getName())
                val = data[name] if name in data else p.getDefValue()
                form.fields[name] = p.formField(val)
            res += (
                '<fieldset class="prefset"><legend>'
                + v['friendlyName']
                + '</legend>'
                + form.as_p()
                + '</fieldset>'
            )
        return res

    def getGuiForUserPreferences(self, user=None):
        data = {}
        if user is not None:
            for up in user.preferences.all():
                data[self.__nameFor(up.module, up.name)] = up.value
        res = []
        for mod, v in self._prefs.items():
            grp = []
            for p in v['prefs']:
                name = self.__nameFor(mod, p.getName())
                val = data[name] if name in data else p.getDefValue()
                grp.append(
                    {
                        'name': name,
                        'gui': p.guiField(val).guiDescription(),
                        'value': val,
                    }
                )
            res.append({'moduleLabel': v['friendlyName'], 'prefs': grp})
        return res

    def processRequestForUserPreferences(self, user, data):
        """
        Returns a list of errors in case of error, else return None
        """
        # First, read fields form every single "section"
        logger.debug('Processing %s', self._prefs)
        prefs = []
        for mod, v in self._prefs.items():
            logger.debug(mod)
            form = forms.Form(data)
            for p in v['prefs']:
                name = self.__nameFor(mod, p.getName())
                form.fields[name] = p.formField(None)
            if form.is_valid() is False:
                logger.debug("errors")
                return form.errors
            for p in v['prefs']:
                name = self.__nameFor(mod, p.getName())
                logger.debug(name)
                prefs.append(
                    {
                        'module': mod,
                        'name': p.getName(),
                        'value': form.cleaned_data[name],
                    }
                )
        user.preferences.all().delete()
        try:
            for p in prefs:
                user.preferences.create(
                    module=p['module'], name=p['name'], value=p['value']
                )
        except Exception:  # User does not exists
            logger.info('Trying to dave user preferences failed (probably root user?)')
        return None

    def processGuiForUserPreferences(self, user, data):
        """
        Processes the preferences got from user
        """
        logger.debug('Processing data %s', data)
        prefs = []
        for mod, v in self._prefs.items():
            logger.debug(mod)
            for p in v['prefs']:
                name = self.__nameFor(mod, p.getName())
                if name in data:
                    prefs.append(
                        {'module': mod, 'name': p.getName(), 'value': data[name]}
                    )
        user.preferences.all().delete()
        for p in prefs:
            user.preferences.create(
                module=p['module'], name=p['name'], value=p['value']
            )


class UserPreference(object):
    TYPE = 'abstract'

    def __init__(self, **kwargs):
        self._name = kwargs['name']
        self._label = kwargs['label']
        self._defValue = kwargs.get('defvalue', None)
        self._css = 'form-control'

    def getName(self):
        return self._name

    def getDefValue(self):
        return self._defValue

    def formField(self, value):
        """
        Returns a form field to add to the preferences form
        """
        raise NotImplementedError('Can\'t create an abstract preference!!!')

    def guiField(self, value):
        """
        returns a gui field
        """
        return None


class CommonPrefs(object):
    SZ_PREF = 'screenSize'
    SZ_640x480 = '1'
    SZ_800x600 = '2'
    SZ_1024x768 = '3'
    SZ_1366x768 = '4'
    SZ_1920x1080 = '5'
    SZ_FULLSCREEN = 'F'

    DEPTH_PREF = 'screenDepth'
    DEPTH_8 = '1'
    DEPTH_16 = '2'
    DEPTH_24 = '3'
    DEPTH_32 = '4'

    BYPASS_PREF = 'bypassPluginDetection'

    @staticmethod
    def getWidthHeight(size: str) -> typing.Tuple[int, int]:
        """
        Get width based on screenSizePref value
        """
        return {
            CommonPrefs.SZ_640x480: (640, 480),
            CommonPrefs.SZ_800x600: (800, 600),
            CommonPrefs.SZ_1024x768: (1024, 768),
            CommonPrefs.SZ_1366x768: (1366, 768),
            CommonPrefs.SZ_1920x1080: (1920, 1080),
            CommonPrefs.SZ_FULLSCREEN: (-1, -1),
        }.get(size, (1024, 768))

    @staticmethod
    def getDepth(depth: str) -> int:
        """
        Get depth based on depthPref value
        """
        return {
            CommonPrefs.DEPTH_8: 8,
            CommonPrefs.DEPTH_16: 16,
            CommonPrefs.DEPTH_24: 24,
            CommonPrefs.DEPTH_32: 32,
        }.get(depth, 24)
