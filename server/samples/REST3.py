# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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

from __future__ import unicode_literals

from httplib2 import Http
import json
import sys

rest_url = 'http://172.27.0.1:8000/rest/'



headers = {}

# Hace login con el root, puede usarse cualquier autenticador y cualquier usuario, pero en la 1.5 solo está implementado poder hacer
# este tipo de login con el usuario "root"
def login():
    global headers
    h = Http()

    # parameters = '{ "auth": "admin", "username": "root", "password": "temporal" }'
    parameters = '{ "auth": "interna", "username": "admin", "password": "temporal" }'

    resp, content = h.request(rest_url + 'auth/login', method='POST', body=parameters)

    if resp['status'] != '200':  # Authentication error due to incorrect parameters, bad request, etc...
        print "Authentication error"
        return -1

    # resp contiene las cabeceras, content el contenido de la respuesta (que es json), pero aún está en formato texto
    res = json.loads(content)
    print "Authentication response: {}".format(res)
    if res['result'] != 'ok':  # Authentication error
        print "Authentication error"
        sys.exit(1)

    headers['X-Auth-Token'] = res['token']
    headers['content-type'] = 'application/json'

    return 0

def logout():
    global headers
    h = Http()

    resp, content = h.request(rest_url + 'auth/logout', headers=headers)

    if resp['status'] != '200':  # Logout error due to incorrect parameters, bad request, etc...
        print "Error requesting logout"
        return -1

    # Return value of logout method is nonsense (returns always done right now, but it's not important)

    return 0

def list_supported_auths_and_fields():
    h = Http()
    
    resp, content = h.request(rest_url + 'authenticators/types', headers=headers)
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)
        
    r = json.loads(content)
    
    for auth in r:  # r is an array
        print '* {}'.format(auth['name'])
        for fld in auth: # every auth is converted to a dictionary in python by json.load
            # Skip icon
            if fld != 'icon':
                print " > {}: {}".format(fld, auth[fld])
        resp, content = h.request(rest_url + 'authenticators/gui/{}'.format(auth['type']), headers=headers)
        if resp['status'] != '200':
            print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
            sys.exit(1)
            
        print " > GUI"
        rr = json.loads(content)
        for field in rr:
            print "   - Name: {}".format(field['name'])
            print "   - Value: {}".format(field['value'])
            print "   - GUI: "
            for gui in field['gui']:
                print "     + {}: {}".format(gui, field['gui'][gui])
        print " > Simplified fields:"
        for field in rr:
            print "   - Name: {}, Type: {}, is Required?: {}".format(field['name'], field['gui']['type'], field['gui']['required'])

def create_simpleldap_auth():
    h = Http()

    # Keep in mind that parameters are related to kind of authenticator.
    # To ensure what parameters you need, yo can invoke first its gui
    # Take a look at list_supported_auths_and_fields method
    data = {"tags":["Tag1","Tag2","Tag3"],"name":"name_Field","comments":"comments__Field","priority":"1","small_name":"label_Field","host":"host_Field","port":"389","ssl":False,"timeout":"10","username":"username__Field","password":"password_Field","ldapBase":"base_Field","userClass":"userClass_Field","userIdAttr":"userIdAttr_Field","userNameAttr":"userName_Field","groupClass":"groupClass_Field","groupIdAttr":"groupId_Field","memberAttr":"groupMembership_Field","data_type":"SimpleLdapAuthenticator"}
    resp, content = h.request(rest_url + 'authenticators','PUT', headers=headers, body=json.dumps(data))
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)
        
    # Expected content is something like this:
    # {
    # "numeric_id": 18, 
    # "groupIdAttr": "groupId_Field", 
    # "port": "389", 
    # "memberAttr": "groupMembership_Field", 
    # "id": "790b9d85-67ec-51dc-847f-dee1daa96a7c", 
    # "userClass": "userClass_Field", 
    # "permission": 96, 
    # "comments": "comments__Field", 
    # "users_count": 0, 
    # "priority": "1", 
    # "type": "SimpleLdapAuthenticator", 
    # "username": "username__Field", 
    # "ldapBase": "base_Field", "userNameAttr": 
    # "userName_Field", 
    # "tags": ["Tag1", "Tag2", "Tag3"], 
    # "groupClass": "groupClass_Field", 
    # "ssl": false, 
    # "host": "host_Field", 
    # "userIdAttr": "userIdAttr_Field", 
    # "password": "password_Field", 
    # "small_name": "label_Field", 
    # "name": "name_Field", 
    # "timeout": "10"
    # }
    r = json.loads(content)
    print "Correctly created {} with id {}".format(r['name'], r['id'])
    print "The record created was: {}".format(r)
    return r

def delete_auth(auth_id):
    h = Http()

    # Sample delete URL for an auth
    #     http://172.27.0.1:8000/rest/authenticators/790b9d85-67ec-51dc-847f-dee1daa96a7c
    # Method MUST be DELETE
    resp, content = h.request(rest_url + 'authenticators/{}'.format(auth_id), 'DELETE', headers=headers)
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)
        
    print "Correctly deleted {}".format(auth_id)

def create_internal_auth():
    h = Http()
    
    data = {"tags":[""],"name":"name_Field","comments":"comments_Field","priority":"1","small_name":"label_Field","differentForEachHost":False,"reverseDns":False,"acceptProxy":False,"data_type":"InternalDBAuth"}
    resp, content = h.request(rest_url + 'authenticators','PUT', headers=headers, body=json.dumps(data))
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)
        
    r = json.loads(content)
    print "Correctly created {} with id {}".format(r['name'], r['id'])
    print "The record created was: {}".format(r)
    return r

def create_internal_group(auth_id):
    h = Http()
    
    # Type can also be a metagroup, composed of groups, but for this sample a group is enoutgh
    data = {"type":"group","name":"groupname_Field","comments":"comments_Field","state":"A"}
    resp, content = h.request(rest_url + 'authenticators/{}/groups'.format(auth_id),'PUT', headers=headers, body=json.dumps(data))
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)

    r = json.loads(content)
    print "Correctly created {} with id {}".format(r['name'], r['id'])
    print "The record created was: {}".format(r)
    return r
        
def delete_group(auth_id, group_id):
    h = Http()

    # Method MUST be DELETE
    resp, content = h.request(rest_url + 'authenticators/{}/groups/{}'.format(auth_id, group_id), 'DELETE', headers=headers)
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)
        
    print "Correctly deleted {}".format(auth_id)
    

def create_internal_user(auth_id, group_id):
    # Note: internal users NEEDS to store password on UDS, description of auth describes if password field is needed (in this case, we need it)
    #       Also, if authenticator is marked as "external" on its description, the groups field will be ignored.
    #       On internal auths, we can incluide de ID of the groups we want this user to belong to, or it will not belong to any group
    h = Http()
    
    data = {"id":"","name":"username_Field","real_name":"name_Field","comments":"comments_Field","state":"A","staff_member":False, "is_admin":False,"password":"password_Field","groups":[group_id]}

    resp, content = h.request(rest_url + 'authenticators/{}/users'.format(auth_id),'PUT', headers=headers, body=json.dumps(data))
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)

    r = json.loads(content)
    print "Correctly created {} with id {}".format(r['name'], r['id'])
    print "The record created was: {}".format(r)
    return r

def delete_user(auth_id, user_id):
    # Deleting user will result in deleting in cascade all asigned resources (machines, apps, etc...)
    
    h = Http()

    # Method MUST be DELETE
    resp, content = h.request(rest_url + 'authenticators/{}/users/{}'.format(auth_id, user_id), 'DELETE', headers=headers)
    if resp['status'] != '200':
        print "Error in request: \n-------------------\n{}\n{}\n----------------".format(resp, content)
        sys.exit(1)
        
    print "Correctly deleted {}".format(auth_id)

def list_currents_auths():
    pass

if __name__ == '__main__':
    if login() == 0:  # If we can log in, will get the pools correctly
        print "Listing supported auths and related info"
        list_supported_auths_and_fields()
        print "*******************************"
        print "Creating a simple ldap authenticator"
        auth = create_simpleldap_auth()
        print "*******************************"
        print "Deleting the created simple ldap authenticator"
        delete_auth(auth['id'])
        print "*******************************"
        print "Creating internal auth"
        auth = create_internal_auth()
        print "*******************************"
        print "Creating internal group"
        print "*******************************"
        group = create_internal_group(auth['id'])
        print "Creating internal user"
        print "*******************************"
        user = create_internal_user(auth['id'], group['id'])
        print "*******************************"
        print "Deleting user"
        delete_user(auth['id'], user['id'])
        print "*******************************"
        print "Deleting Group"
        delete_group(auth['id'], group['id'])
        print "*******************************"
        print "Deleting the created internal auth"
        delete_auth(auth['id'])
