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

from handlers import NotFound
from django.utils.translation import ugettext as _

import logging

logger = logging.getLogger(__name__)

# Details do not have types at all
# so, right now, we only process details petitions for Handling & tables info
class DetailHandler(object):
    def __init__(self, parentHandler, path, *args, **kwargs):
        self._parent = parentHandler
        self._path = path
        self._args = args
        self._kwargs = kwargs
        
    # A detail handler must also return title & fields for tables
    def getTitle(self):
        return ''
    
    def getFields(self):
        return []

class ModelHandlerMixin(object):
    '''
    Basic Handler for a model
    Basically we will need same operations for all models, so we can
    take advantage of this fact to not repeat same code again and again... 
    '''
    authenticated = True
    needs_staff = True
    detail = None # Dictionary containing detail routing 
    model = None
    
    def item_as_dict(self, item):
        pass
    
    def getItems(self, *args, **kwargs):
        for item in self.model.objects.filter(*args, **kwargs):
            try: 
                yield self.item_as_dict(item)
            except:
                logger.exception('Exception getting item from {0}'.format(self.model))
                
    def processDetail(self):
        logger.debug('Processing detail')
        try:
            item = self.model.objects.filter(pk=self._args[0])[0]
            detailCls = self.detail[self._args[1]]
            args = list(self._args[2:])
            path = self._path + '/'.join(args[:2])
            detail = detailCls(self, path, parent = item)
            return getattr(detail, self._operation)()
        except:
            raise NotFound('method not found')
        
    def get(self):
        logger.debug('method GET for {0}, {1}'.format(self.__class__.__name__, self._args))
        if len(self._args) == 0:
            return list(self.getItems())

        # If has detail and is requesting detail        
        if self.detail is not None and len(self._args) > 1:
            return self.processDetail()
        
        try:
            return list(self.getItems(pk=self._args[0]))[0]
        except:
            raise NotFound('item not found')

class ModelTypeHandlerMixin(object):
    '''
    As With models, a lot of UDS model contains info about its class.
    We take advantage of this for not repeating same code (as with ModelHandlerMixin)
    '''
    authenticated = True
    needs_staff = True
    
    def enum_types(self):
        pass
    
    def type_as_dict(self, type_):
        return { 'name' : _(type_.name()), 
                 'type' : type_.type(), 
                 'description' : _(type_.description()), 
                 'icon' : type_.icon().replace('\n', '') 
        }
            
    def getTypes(self, *args, **kwargs):
        for type_ in self.enum_types():
            yield self.type_as_dict(type_)
            
    def get(self):
        logger.debug(self._args)
        nArgs = len(self._args)
        if nArgs == 0:
            return list(self.getTypes())
        
        found = None
        for v in self.getTypes():
            if v['type'] == self._args[0]:
                found = v
                break
        
        if found is None:
            raise NotFound('type not found')
        
        logger.debug('Found type {0}'.format(v))
        if nArgs == 1:
            return found
        
        if self._args[1] == 'gui':
            gui = self.getGui(self._args[0])
            # Add name default description, at top of form
            gui.append({
                 'name': 'name', 
                 'value':'', 
                 'gui': {
                    'required':True,
                    'defvalue':'',
                    'value':'',
                    'label': _('Name'),
                    'length': 128,
                    'multiline': 0,
                    'tooltip': _('Name of this element'),
                    'rdonly': False,
                    'type': 'text',
                    'order': -2
                 }  
            })
            # And comments
            gui.append({
                 'name': 'comments', 
                 'value':'', 
                 'gui': {
                    'required':True,
                    'defvalue':'',
                    'value':'',
                    'label': _('Comments'),
                    'length': 256,
                    'multiline': 0,
                    'tooltip': _('Comments for this element'),
                    'rdonly': False,
                    'type': 'text',
                    'order': -1
                 }  
            })
            
            

            logger.debug("GUI: {0}".format(gui))
            return sorted(gui, key=lambda f: f['gui']['order']);

    
class ModelTableHandlerMixin(object):
    authenticated = True
    needs_staff = True
    detail = None
    
    # Fields should have id of the field, type and length 
    # All options can be ommited
    # Sample fields:
    #    fields = [
    #        { 'name': {'title': _('Name')} },
    #        { 'comments': {'title':  _('Comments')}},
    #        { 'services_count': {'title': _('Services'), 'type': 'numeric', 'width': '5em'}}
    #]

    fields = []
    title = ''

    def processDetail(self):
        logger.debug('Processing detail for table')
        try:
            detailCls = self.detail[self._args[1]]
            args = list(self._args[2:])
            path = self._path + '/'.join(args[:2])
            detail = detailCls(self, path, parent_id = self._args[0])
            return (detail.getTitle(), detail.getFields())
        except:
            return ([], '')
    
    def get(self):
        if len(self._args) > 1:
            title, fields = self.processDetail()
        else:
            # Convert to unicode fields (ugettext_lazy needs to be rendered before passing it to Json
            title = self.title
            fields = self.fields # Always add id column as invisible
            
        processedFields = [{ 'id' : {'visible': False, 'sortable': False, 'searchable': False } }]
            
        for f in fields:
            for k1, v1 in f.iteritems():
                dct = {}
                for k2, v2 in v1.iteritems():
                    if type(v2) in (bool, int, long, float, unicode, list, tuple, dict):
                        dct[k2] = v2
                    else:
                        dct[k2] = unicode(v2)
                processedFields.append({k1: dct})
        return { 'title': unicode(title),  'fields': processedFields };
    
