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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

import logging
import six
import oca

from defusedxml import minidom
# Python bindings for OpenNebula
from .common import sanitizeName

__updated__ = '2016-02-09'

logger = logging.getLogger(__name__)


def getTemplates(api, force=False):
    logger.debug('Api: {}'.format(api))
    templatesPool = oca.VmTemplatePool(api)
    templatesPool.info()

    for t in templatesPool:
        if t.name[:4] != 'UDSP':
            yield (t.id, t.name)


def create(api, fromTemplateId, name, toDataStore):
    '''
    Publish the machine (makes a template from it so we can create COWs) and returns the template id of
    the creating machine

    Args:
        fromTemplateId: id of the base template
        name: Name of the machine (care, only ascii characters and no spaces!!!)

    Returns
        Raises an exception if operation could not be acomplished, or returns the id of the template being created.

    Note:
        Maybe we need to also clone the hard disk?
    '''
    try:
        # First, we clone the themplate itself
        templateId = api.call('template.clone', int(fromTemplateId), name)

        # Now copy cloned images if possible
        try:
            imgs = oca.ImagePool(api)
            imgs.info()
            imgs = dict(((i.name, i.id) for i in imgs))

            info = api.call('template.info', templateId)
            template = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]
            logger.debug('XML: {}'.format(template.toxml()))

            counter = 0
            for dsk in template.getElementsByTagName('DISK'):
                counter += 1
                imgIds = dsk.getElementsByTagName('IMAGE_ID')
                if len(imgIds) == 0:
                    fromId = False
                    node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                    imgName = node.data
                    # Locate
                    imgId = imgs[imgName]
                else:
                    fromId = True
                    node = imgIds[0].childNodes[0]
                    imgId = node.data

                logger.debug('Found {} for cloning'.format(imgId))

                # Now clone the image
                imgName = sanitizeName(name + ' DSK ' + six.text_type(counter))
                newId = api.call('image.clone', int(imgId), imgName, int(toDataStore))
                if fromId is True:
                    node.data = six.text_type(newId)
                else:
                    node.data = imgName

            # Now update the clone
            api.call('template.update', templateId, template.toxml())
        except Exception:
            logger.exception('Exception cloning image')

        return six.text_type(templateId)
    except Exception as e:
        logger.error('Creating template on OpenNebula: {}'.format(e))
        raise

def remove(api, templateId):
    '''
    Removes a template from ovirt server

    Returns nothing, and raises an Exception if it fails
    '''
    try:
        # First, remove Images (wont be possible if there is any images already in use, but will try)
        # Now copy cloned images if possible
        try:
            imgs = oca.ImagePool(api)
            imgs.info()
            imgs = dict(((i.name, i.id) for i in imgs))

            info = api.call('template.info', int(templateId))
            template = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]
            logger.debug('XML: {}'.format(template.toxml()))

            for dsk in template.getElementsByTagName('DISK'):
                imgIds = dsk.getElementsByTagName('IMAGE_ID')
                if len(imgIds) == 0:
                    node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                    imgId = imgs[node.data]
                else:
                    node = imgIds[0].childNodes[0]
                    imgId = node.data

                logger.debug('Found {} for cloning'.format(imgId))

                # Now delete the image
                api.call('image.delete', int(imgId))

        except:
            logger.exception('Exception cloning image')

        api.call('template.delete', int(templateId))
    except Exception as e:
        logger.error('Creating template on OpenNebula: {}'.format(e))

def deployFrom(api, templateId, name):
    '''
    Deploys a virtual machine on selected cluster from selected template

    Args:
        name: Name (sanitized) of the machine
        comments: Comments for machine
        templateId: Id of the template to deploy from
        clusterId: Id of the cluster to deploy to
        displayType: 'vnc' or 'spice'. Display to use ad OpenNebula admin interface
        memoryMB: Memory requested for machine, in MB
        guaranteedMB: Minimum memory guaranteed for this machine

    Returns:
        Id of the machine being created form template
    '''
    vmId = api.call('template.instantiate', int(templateId), name, False, '')
    return six.text_type(vmId)
