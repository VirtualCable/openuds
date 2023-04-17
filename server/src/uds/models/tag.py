# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging


from django.db import models
from .uuid_model import UUIDModel

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.models import (
        Account,
        Authenticator,
        Calendar,
        MetaPool,
        Network,
        Notifier,
        OSManager,
        Provider,
        Service,
        ServicePool,
        Transport,
    )


class Tag(UUIDModel):
    """
    Tag model associated with an object.

    Tags are used to group objects in the system for REST api mainly and search on admin interface.
    """

    tag = models.CharField(max_length=32, db_index=True, unique=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["Tag"]'

    # Every single related class has a relation with this
    # Its inverse is "xxx_set" class
    account_set: 'models.manager.RelatedManager[Account]'
    authenticator_set: 'models.manager.RelatedManager[Authenticator]'
    calendar_set: 'models.manager.RelatedManager[Calendar]'
    metapool_set: 'models.manager.RelatedManager[MetaPool]'
    network_set: 'models.manager.RelatedManager[Network]'
    notifier_set: 'models.manager.RelatedManager[Notifier]'
    osmanager_set: 'models.manager.RelatedManager[OSManager]'
    provider_set: 'models.manager.RelatedManager[Provider]'
    service_set: 'models.manager.RelatedManager[Service]'
    servicepool_set: 'models.manager.RelatedManager[ServicePool]'
    transport_set: 'models.manager.RelatedManager[Transport]'

    class Meta:
        """
        Meta class to declare db table
        """

        db_table = 'uds_tag'
        app_label = 'uds'

    @property
    def vtag(self) -> str:
        return self.tag.capitalize()

    def __str__(self) -> str:
        return 'Tag: {} {}'.format(self.uuid, self.tag)


class TaggingMixin(models.Model):
    tags = models.ManyToManyField(Tag)

    class Meta:
        abstract = True
