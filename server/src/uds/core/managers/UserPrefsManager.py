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
from django.utils.translation import ugettext as _, ugettext_lazy
from uds.core.ui import gui

if typing.TYPE_CHECKING:
    from uds.models import User

logger = logging.getLogger(__name__)


class UserPrefsManager:
    _manager: typing.Optional['UserPrefsManager'] = None
    _prefs: typing.Dict[str, typing.Dict]

    def __init__(self):
        self._prefs = {}

    @staticmethod
    def manager() -> 'UserPrefsManager':
        if UserPrefsManager._manager is None:
            UserPrefsManager._manager = UserPrefsManager()
        return UserPrefsManager._manager

    def __nameFor(self, module, name):
        return module + "_" + name

    def registerPrefs(self, modName: str, friendlyModName: str, prefs: typing.Any) -> None:
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
        for up in user.preferences.filter(module=modName):
            prefs[up.name] = up.value
        for p in self._prefs[modName]['prefs']:
            if p.getName() not in prefs:
                prefs[p.getName()] = p.getDefValue()
        logger.debug('Preferences: %s', prefs)
        return prefs

    def setPreferenceForUser(self, user: 'User', modName: str, prefName: str, value: str):
        try:
            user.preferences.create(module=modName, name=prefName, value=value)
        except Exception:  # Already exits, update it
            user.preferences.filter(module=modName, name=prefName).update(value=value)

    def getHtmlForUserPreferences(self, user: 'User'):
        # First fill data for all preferences
        data = {}
        for up in user.preferences.all().order_by('module'):
            data[self.__nameFor(up.module, up.name)] = up.value
        res = ''
        for mod, v in sorted(self._prefs.items()):
            form = forms.Form()
            for p in v['prefs']:
                name = self.__nameFor(mod, p.getName())
                val = data[name] if name in data else p.getDefValue()
                form.fields[name] = p.formField(val)
            res += '<fieldset class="prefset"><legend>' + v['friendlyName'] + '</legend>' + form.as_p() + '</fieldset>'
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
                grp.append({'name': name, 'gui': p.guiField(val).guiDescription(), 'value': val})
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
                prefs.append({'module': mod, 'name': p.getName(), 'value': form.cleaned_data[name]})
        user.preferences.all().delete()
        try:
            for p in prefs:
                user.preferences.create(module=p['module'], name=p['name'], value=p['value'])
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
                    prefs.append({'module': mod, 'name': p.getName(), 'value': data[name]})
        user.preferences.all().delete()
        for p in prefs:
            user.preferences.create(module=p['module'], name=p['name'], value=p['value'])


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


class UserTextPreference(UserPreference):
    TYPE = 'text'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._length = kwargs.get('length', None)

    def formField(self, value):
        return forms.CharField(label=_(self._label), initial=value, attrs={'class': self._css})


class UserNumericPreference(UserPreference):
    TYPE = 'numeric'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._min = kwargs.get('minvalue', None)
        self._max = kwargs.get('maxvalue', None)

    def formField(self, value):
        return forms.IntegerField(label=_(self._label), initial=value, min_value=self._min, max_value=self._max,
                                  widget=forms.TextInput(attrs={'class': self._css}))  # pylint: disable=unexpected-keyword-arg, no-value-for-parameter


class UserChoicePreference(UserPreference):
    TYPE = 'choice'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._values = kwargs['values']

    def formField(self, value):
        return forms.ChoiceField(label=_(self._label), initial=value, choices=self._values,
                                 widget=forms.Select(attrs={'class': self._css}))  # pylint: disable=unexpected-keyword-arg, no-value-for-parameter

    def guiField(self, value):
        vals = []
        for v in self._values:
            vals.append({'id': v[0], 'text': _(v[1])})
        return gui.ChoiceField(label=_(self._label), rdonly=False, values=vals, defvalue=value, tooltip=_(self._label))


class UserCheckboxPreference(UserPreference):
    TYPE = 'checkbox'

    def formField(self, value):
        if value is None:
            value = False
        logger.debug('Value type: %s', type(value))
        return forms.BooleanField(label=_(self._label), initial=value)


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
    def getWidthHeight(prefsDict):
        """
        Get width based on screenSizePref value
        """
        try:
            return {
                CommonPrefs.SZ_640x480: (640, 480),
                CommonPrefs.SZ_800x600: (800, 600),
                CommonPrefs.SZ_1024x768: (1024, 768),
                CommonPrefs.SZ_1366x768: (1366, 768),
                CommonPrefs.SZ_1920x1080: (1920, 1080),
                CommonPrefs.SZ_FULLSCREEN: (-1, -1)
            }[prefsDict[CommonPrefs.SZ_PREF]]
        except Exception:
            return CommonPrefs.SZ_1024x768

    @staticmethod
    def getDepth(prefsDict):
        """
        Get depth based on depthPref value
        """
        try:
            return {
                CommonPrefs.DEPTH_8: 8,
                CommonPrefs.DEPTH_16: 16,
                CommonPrefs.DEPTH_24: 24,
                CommonPrefs.DEPTH_32: 32
            }[prefsDict[CommonPrefs.DEPTH_PREF]]
        except Exception:
            return CommonPrefs.DEPTH_24

    screenSizePref = UserChoicePreference(name=SZ_PREF,
                                          label=ugettext_lazy('Screen Size'),
                                          defvalue=SZ_FULLSCREEN,
                                          values=((SZ_640x480, '640x480'),
                                                  (SZ_800x600, '800x600'),
                                                  (SZ_1024x768, '1024x768'),
                                                  (SZ_1366x768, '1366x768'),
                                                  (SZ_1920x1080, '1920x1080'),
                                                  (SZ_FULLSCREEN, ugettext_lazy('Full Screen')))
                                          )
    depthPref = UserChoicePreference(name=DEPTH_PREF, label=ugettext_lazy('Screen colors'),
                                     defvalue=DEPTH_24,
                                     values=((DEPTH_8, ugettext_lazy('8 bits')),
                                             (DEPTH_16, ugettext_lazy('16 bits')),
                                             (DEPTH_24, ugettext_lazy('24 bits')),
                                             (DEPTH_32, ugettext_lazy('32 bits')))
                                     )

    bypassPluginDetectionPref = UserChoicePreference(name=BYPASS_PREF,
                                                     label=ugettext_lazy('Plugin detection'),
                                                     defvalue='0',
                                                     values=(('0', ugettext_lazy('Detect plugin')),
                                                             ('1', ugettext_lazy('Bypass plugin detection')))
                                                     )
