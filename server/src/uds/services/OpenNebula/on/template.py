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

from defusedxml import minidom

from . import types
from .common import sanitized_name

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import client

logger = logging.getLogger(__name__)


def enumerate_templates(
    api: 'client.OpenNebulaClient', force: bool = False
) -> collections.abc.Iterable[types.TemplateType]:
    for t in api.enum_templates():
        if t.name[:4] != 'UDSP':
            yield t


def create(
    api: 'client.OpenNebulaClient', from_template_id: str, name: str, dst_dataestor: str
) -> str:
    """
    Publish the machine (makes a template from it so we can create COWs) and returns the template id of
    the creating machine

    Args:
        fromTemplateId: id of the base template
        name: Name of the machine (care, only ascii characters and no spaces!!!)

    Returns
        Raises an exception if operation could not be acomplished, or returns the id of the template being created.

    Note:
        Maybe we need to also clone the hard disk?
    """
    template_id = None
    try:
        # First, we clone the themplate itself
        # templateId = api.call('template.clone', int(fromTemplateId), name)
        template_id = api.clone_template(from_template_id, name)

        # Now copy cloned images if possible
        imgs = {i.name: i.id for i in api.enum_images()}

        info = api.template_info(template_id).xml
        template: typing.Any = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]  # pyright: ignore
        logger.debug('XML: %s', template.toxml())    # pyright: ignore

        for counter, dsk in enumerate(template.getElementsByTagName('DISK')):    # pyright: ignore
            images_ids = dsk.getElementsByTagName('IMAGE_ID')
            if not images_ids:
                from_id = False
                try:
                    node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                except IndexError:
                    continue  # Skip this unknown node
                image_name = node.data
                # Locate
                try:
                    image_id = imgs[image_name.strip()]
                except KeyError:
                    raise Exception(
                        'Image "{}" could not be found!. Check the opennebula template'.format(
                            image_name.strip()
                        )
                    )
            else:
                from_id = True
                node = images_ids[0].childNodes[0]
                image_id = node.data

            logger.debug('Found %s for cloning', image_id)

            # if api.imageInfo(imgId)[0]['IMAGE']['STATE'] != '1':
            #    raise Exception('The base machines images are not in READY state')

            # Now clone the image
            image_name = sanitized_name(name + ' DSK ' + str(counter))
            new_id = api.clone_image(
                image_id, image_name, dst_dataestor
            )  # api.call('image.clone', int(imgId), imgName, int(toDataStore))
            # Now Store id/name
            if from_id is True:
                node.data = str(new_id)
            else:
                node.data = image_name

        # Now update the clone
        # api.call('template.update', templateId, template.toxml())
        api.update_template(template_id, template.toxml())

        return template_id
    except Exception as e:
        logger.exception('Creating template on OpenNebula')
        try:
            api.delete_template(
                template_id
            )  # Try to remove created template in case of fail
        except Exception:
            pass
        raise e


def remove(api: 'client.OpenNebulaClient', template_id: str) -> None:
    """
    Removes a template from ovirt server

    Returns nothing, and raises an Exception if it fails
    """
    try:
        # First, remove Images (wont be possible if there is any images already in use, but will try)
        # Now copy cloned images if possible
        try:
            imgs = {i.name: i.id for i in api.enum_images()}

            info = api.template_info(template_id).xml
            template: typing.Any = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]  # pyright: ignore
            logger.debug('XML: %s', template.toxml())

            for dsk in template.getElementsByTagName('DISK'):
                images_ids = dsk.getElementsByTagName('IMAGE_ID')
                if not images_ids:
                    try:
                        node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                    except IndexError:
                        continue
                    image_id = imgs[node.data]
                else:
                    node = images_ids[0].childNodes[0]
                    image_id = node.data

                logger.debug('Found %s for cloning', image_id)

                # Now delete the image
                api.delete_image(image_id)  # api.call('image.delete', int(imgId))
        except Exception:
            logger.exception('Removing image')

        api.delete_template(template_id)  # api.call('template.delete', int(templateId))
    except Exception:
        logger.error('Removing template on OpenNebula')


def deploy_from(api: 'client.OpenNebulaClient', template_id: str, name: str) -> str:
    """
    Deploys a virtual machine on selected cluster from selected template

    Args:
        name: Name (sanitized) of the machine
        comments: Comments for machine
        templateId: Id of the template to deploy from

    Returns:
        Id of the machine being created form template
    """
    vmid = api.instantiate_template(
        template_id, name, False, '', False
    )  # api.call('template.instantiate', int(templateId), name, False, '')
    return vmid


def check_published(api: 'client.OpenNebulaClient', template_id: str) -> bool:
    """
    checks if the template is fully published (images are ready...)
    """
    try:
        images = {i.name: i.id for i in api.enum_images()}

        info = api.template_info(template_id).xml
        template: typing.Any = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]  # pyright: ignore
        logger.debug('XML: %s', template.toxml())

        for dsk in template.getElementsByTagName('DISK'):
            images_ids = dsk.getElementsByTagName('IMAGE_ID')
            if not images_ids:
                try:
                    node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                except IndexError:
                    continue
                image_id = images[node.data]
            else:
                node = images_ids[0].childNodes[0]
                image_id = node.data

            logger.debug('Found %s for checking', image_id)

            state = api.image_info(image_id).state
            if state in (types.ImageState.INIT, types.ImageState.LOCKED):
                return False
            if state != types.ImageState.READY:  # If error is not READY
                raise Exception(
                    'Error publishing. Image is in an invalid state. (Check it and delete it if not needed anymore)'
                )

            # Ensure image is non persistent. This may be invoked more than once, but it does not matters
            api.make_persistent_image(image_id, False)

    except Exception:
        logger.exception('Exception checking published')
        raise

    return True
