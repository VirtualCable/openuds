# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 Virtual Cable S.L.
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
Base module for all authenticators

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from uds.core import Module
from django.utils.translation import ugettext_noop as translatable
from GroupsManager import GroupsManager
from Exceptions import InvalidUserException
import logging

logger = logging.getLogger(__name__)

class Authenticator(Module):
    '''
    This class represents the base interface to implement authenticators.
    
    An authenticator is responsible for managing user and groups of a kind
    inside UDS. As so, it must provide a number of method and mechanics to
    allow UDS to manage users and groups using that kind of authenticator.
    
    Some samples of authenticators are LDAP, Internal Database, SAML, CAS, ...
    
    As always, if you override __init__, do not forget to invoke base __init__ as this::
        
       super(self.__class__, self).__init__(self, dbAuth, environment, values)

    This is a MUST, so internal structured gets filled correctly, so don't forget it!.
       
    The preferred method of doing initialization is to provide the :py:meth:`.initialize`,
    and do not override __init__ method. This (initialize) will be invoked after
    all internal initialization.
       
    There are basically two kind of authenticators, that are "Externals" and
    "Internals". 

    Internal authenticators are those where and administrator has created manually
    the user at admin interface. The users are not created from an external source,
    so if an user do not exist at UDS database, it will not be valid. 
    In other words, if you have an authenticator where you must create users,
    you can modify them, you must assign passwords manually, and group membership
    also must be assigned manually, the authenticator is not an externalSource.
    
    As you can notice, almost avery authenticator except internal db will be
    external source, so, by default, attribute that indicates that is an external
    source is set to True.
    
    
    In fact, internal source authenticator is intended to allow UDS to identify 
    if the users come from internal DB (just the case of local authenticator),
    or the users come from other sources. Also, this allos UDS to know when to
    "update" group membership information for an user whenever it logs in.
    
    External authenticator are in fact all authenticators except local database,
    so we have defined isExternalSource as True by default, that will be most 
    cases.
    
    :note: All attributes that are "translatable" here means that they will be
           translated when provided to administration interface, so remember
           to mark them in your own authenticators as "translatable" using
           ugettext_noop. We have aliased it here to "translatable" so it's 
           easier to understand.
    '''
    
    #: Name of type, used at administration interface to identify this 
    #: authenticator (i.e. LDAP, SAML, ...)
    #: This string will be translated when provided to admin interface
    #: using ugettext, so you can mark it as "translatable" at derived classes (using ugettext_noop)
    #: if you want so it can be translated.
    typeName = translatable('Base Authenticator')
    
    #: Name of type used by Managers to identify this type of service
    #: We could have used here the Class name, but we decided that the 
    #: module implementator will be the one that will provide a name that
    #: will relation the class (type) and that name.
    typeType = 'BaseAuthenticator'
    
    #: Description shown at administration level for this authenticator.
    #: This string will be translated when provided to admin interface
    #: using ugettext, so you can mark it as "translatable" at derived classes (using ugettext_noop)
    #: if you want so it can be translated.
    typeDescription = translatable('Base Authenticator')
    
    
    #: Icon file, used to represent this authenticator at administration interface
    #: This file should be at same folder as this class is, except if you provide
    #: your own :py:meth:uds.core.BaseModule.BaseModule.icon method.
    iconFile = 'auth.png'
    
    #: Mark this authenticator as that the users comes from outside the UDS
    #: database, that are most authenticator (except Internal DB) 
    #: So, isInternalSource means that "user is kept at database only"
    isExternalSource = True
    
    #: If we need to enter the password for this user when creating a new
    #: user at administration interface. Used basically by internal authenticator.
    needsPassword = False
    
    #: Label for username field, shown at administration interface user form.
    userNameLabel = translatable('User name')
    
    #: Label for group field, shown at administration interface user form.
    groupNameLabel = translatable('Group name')
    
    #: Label for password field, , shown at administration interface user form.
    #: Not needed for external authenticators (where credentials are stored with
    #: an already existing user.
    passwordLabel = translatable('Password')
    
    from User import User
    from Group import Group
    
    #: The type of user provided, normally standard user will be enough.
    #: This is here so if we need it in some case, we can write our own
    #: user class
    userType = User
    
    #: The type of group provided, normally standard group will be enough
    #: This is here so if we need it in some case, we can write our own
    #: group class
    groupType = Group
    
    def __init__(self, dbAuth, environment, values):
        '''
        Instantiathes the authenticator.
        @param dbAuth: Database object for the authenticator
        @param environment: Environment for the authenticator
        @param values: Values passed to element
        '''
        self._dbAuth = dbAuth
        super(Authenticator, self).__init__(environment, values)
        self.initialize(values)
    
    def initialize(self, values):
        '''
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done
        
        Args:
            Values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.
            
        Default implementation does nothing
        '''
        pass
    
    def dbAuthenticator(self):
        '''
        Helper method to access the Authenticator database object
        '''
        return self._dbAuth

    def recreateGroups(self, user):
        '''
        Helper method, not needed to be overriden.
        It simply checks if the source is external and if so, recreates
        the user groups for storing them at database.
        
        user param is a database user object
        '''
        if self.isExternalSource == True:
            groupsManager = GroupsManager(self._dbAuth)
            self.getGroups(user.name, groupsManager)
            user.groups = [ g.dbGroup() for g in groupsManager.getValidGroups()]
            
    def callbackUrl(self):
        '''
        Helper method to return callback url for self (authenticator).
        
        This method will allow us to know where to do redirection in case
        we need to use callback for authentication
        '''
        from auth import authCallbackUrl
        return authCallbackUrl(self.dbAuthenticator())
    
    def infoUrl(self):
        '''
        Helper method to return info url for this authenticator
        '''
        from auth import authInfoUrl
        return authInfoUrl(self.dbAuthenticator())
    
    def searchUsers(self, pattern):
        '''
        If you provide this method, the user will be allowed to search users,
        that is, the search button at administration interface, at user form,
        will be enabled.
        
        Returns an array of users that match the supplied pattern
        If none found, returns empty array.
        
        Must return is an array of dictionaries that must contains 'id' and 'name'
        example: [ {'id': 'user1', 'name': 'Nombre 1'} ]
        
        Args:
            pattern: Pattern to search for (simple pattern, string)
        
        Returns    
            a list of found users for the pattern specified
        '''
        return []
        
    def searchGroups(self, pattern):
        '''
        Returns an array of groups that match the supplied pattern
        If none found, returns empty array. Items returned are BaseGroups (or derived)
        If you override this method, the admin interface will allow the use of
        "search" at group form. If not overriden, the search will not be allowed.
        
        Must return array of dictionaries that must contains 'id' and 'name'
        example: [ {'id': 'user1', 'name': 'Nombre 1'} ]
        
        Default implementation returns empty array, but is never used because if
        not overriden, search of groups will not be allowed.
        '''
        return []
        
    def authenticate(self, username, credentials, groupsManager):
        '''
        This method must be overriden, and is responsible for authenticating
        users. 
        
        We can have to different situations here:
        
           * The authenticator is external source, what means that users may 
             be unknown to system before callig this
           * The authenticator isn't external source, what means that users have 
             been manually added to system and are known before this call.
             This will only happen at Internal DB Authenticator.
             
        We receive the username, the credentials used (normally password, but can 
        be a public key or something related to pk) and a group manager.
        
        The group manager is responsible for letting know the authenticator which 
        groups we currently has active.
        
        Args:
            username: User name to authenticate
            credentilas: Credentials for this user, (password, pki, or whatever needs to be used)
            groupManager: Group manager to modify with groups to which this users belongs to.
        
        Returns:
            True if authentication success, False if don't. 
            
        See uds.core.auths.GroupsManager
        
        :note: This method must check not only that the user has valid credentials, but also
               check the valid groups from groupsManager.
               If this method returns false, of method getValidGroups of the groupsManager
               passed into this method has no elements, the user will be considered invalid.
               So remember to check validity of groups this user belongs to (inside the authenticator,
               not inside UDS) using groupsManager.validate(group to which this users belongs to).
               
               This is done in this way, because UDS has only a subset of groups for this user, and
               we let the authenticator decide inside wich groups of UDS this users is included.
        '''
        return False
    
    def getForAuth(self, username):
        '''
        Process the username for this authenticator and returns it.
        This transformation is used for transports only, not for transforming
        anything at login time. Transports that will need the username, will invoke
        this method.
        For example, ad authenticator can add '@domain' so transport use the complete
        'user@domain' instead of 'user'.
        
        Right now, all authenticators keep this value "as is", i mean, it simply
        returns the unprocessed username
        '''
        return username
    
    def getGroups(self, username, groupsManager):
        '''
        Looks for the real groups to which the specified user belongs
        Returns a list of groups. 
        Remember to override it in derived authentication if needed (external auths will need this, for internal authenticators this is never used)
        '''
        return []
    
    def getHtml(self, request):
        '''
        If you override this method, and returns something different of None,
        UDS will consider your authenticator as "Owner draw", that is, that it
        will not use the standard form for user authentication.
        
        Args:
            Request is the DJango request received for generating this html,
            with included user ip at request.ip.
            
        We have here a few things that we should know for creating our own
        html for authenticator:
        
            * We use jQuery, so your javascript can use it
            * The id of the username input field is **id_user**
            * The id of the password input field is **id_password**
            * The id of the login form is **loginform**
            * The id of the "back to login" link is **backToLogin**
         
        This is what happens when an authenticator that has getHtml method is
        selected in the front end (from the combo shown):
        
            * The div with id **login** is hidden.
            * The div with id **nonStandard** is shown
            * Using Ajax, the html provided by this method is requested for
              the authenticator
            * The returned html is rendered inside **nonStandardLogin** div.
            * The **nonStandard** div is shown. 
        
        **nonStandard** div has two inner divs, **nonStandardLogin** and
        **divBackToLogin**. If there is no standard auths, divBackToLogin is
        erased.
        
        With this, and :py:meth:.authCallback method, we can add SSO engines
        to UDS with no much problems.
        '''
        return None
    
    def authCallback(self, parameters):
        '''
        There is a view inside UDS, an url, that will redirect the petition
        to this callback.
        
        If someone gets authenticated via this callback, the method will return
        an "username" must be return. This username will be used to:
           
           * Add user to UDS
           * Get user groups.
           
        So, if this callback is called, also get the membership to groups of the user, and keep them.
        This method will have to keep track of those until UDS request that groups
        using getGroups. (This is easy, using storage() provided with the environment (env())
        
        If this returns None, or empty, the authentication will be considered "invalid"
        and an error will be shown.
        
        :note: Keeping user information about group membership inside storage is highly recommended.
               There will be calls to getGroups one an again, and also to getRealName, not just
               at login, but at future (from admin interface, at user editing for example)
        '''
        return None

    def getInfo(self, parameters):
        '''
        This method is invoked whenever the authinfo url is invoked, with the name of the authenticator
        If this is implemented, information returned by this will be shown via web.
        
        :note: You can return here a single element or a list (or tuple), where first element will be content itself, 
               and second will be the content type (i.e. "text/plain"). 
        '''
        return None
    
    def getRealName(self, username):
        '''
        Tries to get the real name of an user
        
        Default implementation returns just the same user name that is passed in.
        '''
        return username

    def createUser(self, usrData):
        '''
        This method is used when creating an user to allow the authenticator:
        
            * Check that the name inside usrData is fine
            * Fill other (not name, if you don't know what are you doing) usrData dictionary values.
        
        This will be invoked from admin interface, when admin wants to create a new user
            
        modified usrData will be used to store values at database.
        
        Args:
            usrData: Contains data received from user directly, that is a dictionary
                     with at least: name, realName, comments, state & password.
                     This is an in/out parameter, so you can modify, for example,
                     **realName** 
            
        Returns:
            Raises an exception if things didn't went fine, 
            return value is ignored, but modified usrData is used if this does not
            raises an exception. 
            
            Take care with whatever you modify here, you can even modify provided
            name (login name!) to a new one!
            
        :note: If you have an SSO where you can't create an user from admin interface,
               raise an exception here indicating that the creation can't be done.
               Default implementation simply raises "AuthenticatorException" and
               says that user can't be created manually
               
        '''
        raise InvalidUserException(translatable('Users can\'t be created inside this authenticator'))
        

    def modifyUser(self, usrData):
        '''
        This method is used when modifying an user to allow the authenticator:
        
            * Check that the name inside usrData is fine
            * Fill other (not name, if you don't know what are you doing) usrData dictionary values.
        
        Args:
            usrData: Contains data received from user directly, that is a dictionary
                     with at least: name, realName, comments, state & password.
                     This is an in/out parameter, so you can modify, for example,
                     **realName** 
             

        Returns:
            Raises an exception if things didn't went fine, 
            return value is ignored, but modified usrData is used if this does not
            raises an exception. 
            
            Take care with whatever you modify here, you can even modify provided
            name (login name!) to a new one!
        
        :note: By default, this will do nothing, as we can only modify "accesory" internal
               data of users.
        '''
        pass


    def createGroup(self, groupData):
        '''
        This method is used when creating a new group to allow the authenticator:
        
            * Check that the name inside groupData is fine
            * Fill other (not name, if you don't know what are you doing) usrData dictionary values.
        
        This will be invoked from admin interface, when admin wants to create a new group.
            
        modified groupData will be used to store values at database.
        
        Args:
            groupData: Contains data received from user directly, that is a dictionary
                       with at least: name, comments and active.
                       This is an in/out parameter, so you can modify, for example,
                       **comments** 
            
        Returns:
            Raises an exception if things didn't went fine, 
            return value is ignored, but modified groupData is used if this does not
            raises an exception. 
            
            Take care with whatever you modify here, you can even modify provided
            name (group name) to a new one!
        '''
        pass

    def removeUser(self, username):
        '''
        Remove user is used whenever from the administration interface, or from other
        internal workers, an user needs to be removed.
        
        This is a notification method, whenever an user gets removed from UDS, this 
        will get called. 
        
        You can do here whatever you want, but you are not requested to do anything
        at your authenticators.
        
        If this method raises an exception, the user will not be removed from UDS
        '''
        pass

    # We don't have a "modify" group option. Once u have created it, the only way of changing it if removing it an recreating it with another name
        
    def removeGroup(self, groupname):
        '''
        Remove user is used whenever from the administration interface, or from other
        internal workers, an group needs to be removed.
        
        This is a notification method, whenever an group gets removed from UDS, this 
        will get called. 
        
        You can do here whatever you want, but you are not requested to do anything
        at your authenticators.
        
        If this method raises an exception, the group will not be removed from UDS
        '''
        pass
