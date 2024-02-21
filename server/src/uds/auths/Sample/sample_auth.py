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
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.ui import gui
from uds.core import auths, exceptions, types, consts

if typing.TYPE_CHECKING:
    from django.http import (
        HttpRequest,
    )  # pylint: disable=ungrouped-imports
    from uds.core.types.requests import ExtendedHttpRequestWithUser
    from uds.core.auths.groups_manager import GroupsManager


logger = logging.getLogger(__name__)


class SampleAuth(auths.Authenticator):
    """
    This class represents a sample authenticator.

    As this, it will provide:
       * The authenticator functionality
          * 3 Groups, "Mortals", "Gods" and "Daemons", just random group names selected.. :-),
            plus groups that we enter at Authenticator form, from admin interface.
          * Search of groups (inside the 3 groups used in this sample plus entered)
          * Search for people (will return the search string + 000...999 as usernames)
       * The Required form description for administration interface, so admins can create
         new authenticators of this kind.

    In this sample, we will provide a simple standard auth, with owner drawn
    login form that will simply show users that has been created and allow web user
    to select one of them.

    For this class to get visible at administration client as a authenticator type,
    we MUST register it at package __init__

    :note: At class level, the translations must be simply marked as so
    using gettext_noop. This is done in this way because we will translate
    the string when it is sent to the administration client.
    """

    # : Name of type, used at administration interface to identify this
    # : authenticator (i.e. LDAP, SAML, ...)
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_name = _('Sample Authenticator')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    type_type = 'SampleAuthenticator'

    # : Description shown at administration level for this authenticator.
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_description = _('Sample dummy authenticator')

    # : Icon file, used to represent this authenticator at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    icon_file = 'auth.png'

    # : Mark this authenticator as that the users comes from outside the UDS
    # : database, that are most authenticator (except Internal DB)
    # : True is the default value, so we do not need it in fact
    # external_source = True

    # : If we need to enter the password for this user when creating a new
    # : user at administration interface. Used basically by internal authenticator.
    # : False is the default value, so this is not needed in fact
    # : needs_password = False

    # : Label for username field, shown at administration interface user form.
    label_username = _('Fake User')

    # Label for group field, shown at administration interface user form.
    label_groupname = _('Fake Group')

    # : Definition of this type of authenticator form
    # : We will define a simple form where we will use a simple
    # : list editor to allow entering a few group names

    groups = gui.EditableListField(label=_('Groups'), default=['Gods', 'Daemons', 'Mortals'])

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        """
        Simply check if we have
        at least one group in the list
        """

        # To avoid problems, we only check data if values are passed
        # If values are not passed in, form data will only be available after
        # unserialization, and at this point all will be default values
        # so self.groups.value will be []
        if values and len(self.groups.value) < 2:
            raise exceptions.ui.ValidationError(_('We need more than two groups!'))

    def search_users(self, pattern: str) -> collections.abc.Iterable[dict[str, str]]:
        """
        Here we will receive a pattern for searching users.

        This method is invoked from interface, so an administrator can search users.

        If we do not provide this method, the authenticator will not provide search
        facility for users. In our case, we will simply return a list of users
        (array of dictionaries with ids and names) with the pattern plus 1..10
        """
        return [
            {
                'id': f'{pattern}-{a}',
                'name': f'{pattern} number {a}',
            }
            for a in range(1, 10)
        ]

    def search_groups(self, pattern: str) -> collections.abc.Iterable[dict[str, str]]:
        """
        Here we we will receive a patter for searching groups.

        In this sample, we will try to locate elements that where entered at
        sample authenticator form (when created), and return the ones that
        contains the pattern indicated.
        """
        pattern = pattern.lower()
        res = []
        for g in self.groups.value:
            if g.lower().find(pattern) != -1:
                res.append({'id': g, 'name': ''})
        return res

    def authenticate(
        self,
        username: str,
        credentials: str,
        groupsManager: 'GroupsManager',
        request: 'ExtendedHttpRequest',  # pylint: disable=unused-argument
    ) -> types.auth.AuthenticationResult:
        """
        This method is invoked by UDS whenever it needs an user to be authenticated.
        It is used from web interface, but also from administration interface to
        check credentials and access of user.

        The tricky part of this method is the groupsManager, but it's easy to
        understand what is used it for.

        Imagine some authenticator, for example, an LDAP. It has its users, it has
        its groups, and it has it relations (which user belongs to which group).

        Now think about UDS. UDS know nothing about this, it only knows what
        the administator has entered at admin interface (groups mainly, but he can
        create users also).

        UDS knows about this groups, but we need to relation those with the ones
        know by the authenticator.

        To do this, we have created a simple mechanism, where the authenticator
        receives a groupsManager, that knows all groups known by UDS, and has
        the method so the authenticator can say, for the username being validated,
        to which uds groups it belongs to.

        This is done using the :py:meth:uds.core.auths.groups_manager.GroupsManager.validate
        method of the provided groups manager.

        At return, UDS will do two things:
           * If there is no group inside the groupsManager mareked as valid, it will
             denied access.
           * If there is some groups marked as valid, it will refresh the known
             UDS relations (this means that the database will be refresehd so the user
             has valid groups).

        This also means that the group membership is only checked at user login (well,
        in fact its also checked when an administrator tries to modify an user)

        So, authenticate must not also validate the user credentials, but also
        indicate the group membership of this user inside UDS.

        :note: groupsManager is an in/out parameter
        """
        if username != credentials:  # All users with same username and password are allowed
            return types.auth.FAILED_AUTH

        # Now the tricky part. We will make this user belong to groups that contains at leat
        # two letters equals to the groups names known by UDS
        # For this, we will ask the groups manager for the groups names, and will check that and,
        # if the user match this criteria, will mark that group as valid
        for g in groupsManager.enumerate_groups_name():
            if len(set(g.lower()).intersection(username.lower())) >= 2:
                groupsManager.validate(g)

        return types.auth.SUCCESS_AUTH

    def get_groups(self, username: str, groupsManager: 'auths.GroupsManager') -> None:
        """
        As with authenticator part related to groupsManager, this
        method will fill the groups to which the specified username belongs to.

        We have to fill up groupsManager from two different places, so it's not
        a bad idea to make a method that get the "real" authenticator groups and
        them simply call to :py:meth:uds.core.auths.groups_manager.GroupsManager.validate

        In our case, we simply repeat the process that we also do at authenticate
        """
        for g in groupsManager.enumerate_groups_name():
            if len(set(g.lower()).intersection(username.lower())) >= 2:
                groupsManager.validate(g)

    def get_javascript(self, request: 'HttpRequest') -> typing.Optional[str]:  # pylint: disable=unused-argument
        """
        If we override this method from the base one, we are telling UDS
        that we want to draw our own authenticator.

        This way, we can do whataver we want here (for example redirect to a site
        for a single sign on) generation our ouwn html (and javascript ofc).

        """
        # Here there is a sample, commented out
        # In this sample, we will make a list of valid users, and when clicked,
        # it will fill up original form with username and same password, and submit it.
        # res = ''
        # for u in self.dbAuthenticator().users.all():
        #    res += '<a class="myNames" id="{0}" href="">{0}</a><br/>'.format(u.name)
        #
        # res += '<script type="text/javascript">$(".myNames").click(function() { '
        # res += '$("#id_user").val(this.id); $("#id_password").val(this.id); $("#loginform").submit(); return false;});</script>'
        # return res

        # I know, this is a bit ugly, but this is just a sample :-)

        res = '<p>Login name: <input id="logname" type="text"/></p>'
        res += '<p><a href="" onclick="window.location.replace(\'' + self.callback_url() + '?user='
        res += '\' + $(\'#logname\').val()); return false;">Login</a></p>'
        return res

    def auth_callback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """
        We provide this as a sample of callback for an user.
        We will accept all petitions that has "user" parameter

        This method will get invoked by url redirections, probably by an SSO.

        The idea behind this is that we can provide:
            * Simple user/password authentications
            * Own authentications (not UDS, authenticator "owned"), but with no redirections
            * Own authentications via redirections (as most SSO will do)

        Here, we will receive the parameters for this
        """
        user = request.user.name if request.user else None

        return types.auth.AuthenticationResult(types.auth.AuthenticationState.SUCCESS, username=user)

    def create_user(self, usrData: dict[str, str]) -> None:
        """
        This method provides a "check oportunity" to authenticators for users created
        manually at administration interface.

        If we do not provide this method, the administration interface will not allow
        to create new users "by hand", i mean, the "new" options from menus will dissapear.

        usrData is a dictionary that contains the input parameters from user,
        with at least name, real_name, comments, state & password.

        We can modify this parameters, we can modify ALL, but name is not recommended to
        modify it unles you know what you are doing.

        Here, we will set the state to "Inactive" and realName to the same as username, but twice :-)
        """
        from uds.core.types.states import State  # pylint: disable=import-outside-toplevel

        usrData['real_name'] = usrData['name'] + ' ' + usrData['name']
        usrData['state'] = State.INACTIVE

    def modify_user(self, usrData: dict[str, str]) -> None:
        """
        This method provides a "check opportunity" to authenticator for users modified
        at administration interface.

        If we do not provide this method, nothing will happen (default one does nothing, but
        it's valid).

        usrData is a dictionary that contains the input parameters from user,
        with at least name, real_name, comments, state & password.

        We can modify this parameters, we can modify ALL, but name is not recommended to
        modify it unless you know what you are doing.

        Here, we will simply update the realName of the user, and (we have to take care
        this this kind of things) modify the userName to a new one, the original plus '-1'
        """
        usrData['real_name'] = usrData['name'] + ' ' + usrData['name']
        usrData['name'] += '-1'
