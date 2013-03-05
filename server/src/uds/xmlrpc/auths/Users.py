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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.db import IntegrityError
from uds.models import User as DbUser, Group as DbGroup, Authenticator as DbAuthenticator, State
from uds.core.managers.CryptoManager import CryptoManager
from ..util.Exceptions import DuplicateEntryException, InsertException
from uds.core.auths.Exceptions import AuthenticatorException, InvalidUserException
from AdminAuth import needs_credentials
from Groups import dictFromGroup
from uds.core.auths.User import User
import hashlib
import logging

logger = logging.getLogger(__name__)
INVALID_PASS = '@#&&/%&$%&/adffa'

def dictFromUser(usr, groups = None):
    dict = { 'idParent' : str(usr.manager.id), 'nameParent' : usr.manager.name,  'id' : str(usr.id), 'name' : usr.name, 'realName' : usr.real_name,
                    'comments' : usr.comments, 'state' :  usr.state, 'lastAccess' : usr.last_access, 'password' : INVALID_PASS, 'oldPassword' : INVALID_PASS,
                    'staffMember' : usr.staff_member, 'isAdmin' : usr.is_admin }
    if groups != None:
        dict['groups'] = groups
    logger.debug('Dict: {0}'.format(dict))
    return dict

@needs_credentials
def getUsers(credentials, idParent):
    '''
    Returns the users contained at idParent authenticator
    '''
    auth = DbAuthenticator.objects.get(pk=idParent)
    res = []
    for usr in auth.users.order_by('name'):
        try:
            res.append(dictFromUser(usr))
        except Exception, e:
            logger.debug(e)
    return res

@needs_credentials
def getUser(credentials, id):
    '''
    '''
    usr = User(DbUser.objects.get(pk=id))
    
    grps = []
    for g in usr.groups():
        grps.append(dictFromGroup(g.dbGroup()))
    logger.debug(grps)
    return dictFromUser(usr.dbUser(), grps)

@needs_credentials
def createUser(credentials, usr):
    '''
    Creates a new user associated with an authenticator
    '''
    auth = DbAuthenticator.objects.get(pk=usr['idParent'])
    try:
        authInstance = auth.getInstance()
        authInstance.createUser(usr) # Remenber, this throws an exception if there is an error
        staffMember = isAdmin = False
        if credentials.isAdmin is True:
            staffMember = usr['staffMember']
            isAdmin = usr['isAdmin']
        password = ''
        if authInstance.needsPassword is True:
            password = CryptoManager.manager().hash(usr['password'])
            
        user = auth.users.create(name = usr['name'], real_name = usr['realName'], comments = usr['comments'], state = usr['state'], 
                                 password = password, staff_member = staffMember, is_admin = isAdmin)
        
        if authInstance.isExternalSource == False:
            for grp in usr['groups']:
                group = DbGroup.objects.get(pk=grp['id'])
                user.groups.add(group)
    except IntegrityError, e:
        raise DuplicateEntryException(usr['name'])
    except Exception as e:
        logger.exception(e)
        raise InsertException(str(e))
    return True

@needs_credentials
def modifyUser(credentials, usr):
    '''
    Modifies an existing service provider with specified id and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    try:
        user = DbUser.objects.get(pk=usr['id'])
        auth = user.manager.getInstance()
        auth.modifyUser(usr) # Notifies authenticator
        logger.debug(usr)
        user.name = usr['name']
        user.real_name = usr['realName']
        user.comments = usr['comments']
        if credentials.isAdmin is True:
            logger.debug('Is an admin')
            user.is_admin = usr['isAdmin']
            user.staff_member = usr['staffMember']
        if usr['password'] != usr['oldPassword']:
            user.password = CryptoManager.manager().hash(usr['password'])
        user.state =  usr['state']
        user.save()
        # Now add/removes groups acordly
        if auth.isExternalSource == False:
            newGrps = {}
            knownGrps = user.groups.all()
            # Add new groups, and keep a dict of all groups selected
            for g in usr['groups']:
                newGrps[int(g['id'])] = g['name']
                grp = DbGroup.objects.get(pk=g['id'])
                if (grp in knownGrps) == False:
                    user.groups.add(grp)
            # Remove unselected groups
            for g in knownGrps:
                if newGrps.has_key(g.id) == False:
                    user.groups.remove(g)
            # Add new groups
    except Exception as e:
        logger.exception(e)
        raise(InsertException(str(e)))
    return True

@needs_credentials
def removeUsers(credentials, ids):
    '''
    Deletes a group
    '''
    DbUser.objects.filter(id__in=ids).delete()
    return True

@needs_credentials
def getUserGroups(credentials, id):
    '''
    Get groups assigned to this user
    '''
    user = DbUser.objects.get(pk=id)
    auth = user.manager.getInstance() 
    res = []
    #if auth.isExternalSource == False:
    for grp in user.getGroups():
        res.append(dictFromGroup(grp))
    return res
    
@needs_credentials
def changeUsersState(credentials, ids, newState):
    '''
    Changes the state of the specified group
    '''
    #state = State.ACTIVE if newState == True else State.INACTIVE
    DbUser.objects.filter(id__in=ids).update(state = newState)
    return True

# Registers XML RPC Methods
def registerUserFunctions(dispatcher):
    dispatcher.register_function(getUsers, 'getUsers')
    dispatcher.register_function(getUser, 'getUser')
    dispatcher.register_function(getUserGroups, 'getUserGroups')
    dispatcher.register_function(createUser, 'createUser')
    dispatcher.register_function(modifyUser, 'modifyUser')
    dispatcher.register_function(removeUsers, 'removeUsers')
    dispatcher.register_function(changeUsersState, 'changeUsersState')
    