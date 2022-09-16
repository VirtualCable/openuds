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
import logging
import typing
import yaml
import collections

from django.core.management.base import BaseCommand
from uds.core.util import config
from uds import models


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from django.db import models as dbmodels


def getSerializedFromManagedObject(
    mod: 'models.ManagedObjectModel',
    removableFields: typing.Optional[typing.List[str]] = None,
) -> typing.Mapping[str, typing.Any]:
    try:
        obj = mod.getInstance()
        gui = {i['name']: i['gui']['type'] for i in obj.guiDescription()}
        values = obj.valuesDict()
        # Remove password fields
        for k, v in gui.items():
            if v == 'password':
                values[k] = '********'
        # Some names are know "secret data"
        for i in ('serverCertificate', 'privateKey'):
            if i in values:
                values[i] = '********'
        # remove removable fields
        for i in removableFields or []:
            if i in values:
                del values[i]
        # Append typeName to list
        values['typeName'] = str(obj.typeName)
        values['comments'] = mod.comments

        return values
    except Exception:
        return {}


def getSerializedFromModel(
    mod: 'dbmodels.Model', removableFields: typing.Optional[typing.List[str]] = None, passwordFields: typing.Optional[typing.List[str]] = None
) -> typing.Mapping[str, typing.Any]:
    removableFields = removableFields or []
    passwordFields = passwordFields or []
    try:
        values = mod._meta.managers[0].filter(pk=mod.pk).values()[0]
        for i in ['uuid', 'id'] + removableFields:
            if i in values:
                del values[i]

        for i in passwordFields:
            if i in values:
                values[i] = '********'
        return values
    except Exception:
        return {}


class Command(BaseCommand):
    help = "Outputs all UDS Trees of elements in YAML format"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        logger.debug("Show Tree")
        # firt, genertate Provider-service-servicepool tree
        cntr = 0

        def counter(s: str) -> str:
            nonlocal cntr
            cntr += 1
            return f'{cntr:02d}.-{s}'

        tree = {}
        try:
            providers = {}
            for provider in models.Provider.objects.all():

                services = {}
                for service in provider.services.all():

                    servicePools = {}
                    for servicePool in service.deployedServices.all():
                        # get publications
                        publications = {}
                        for publication in servicePool.publications.all():
                            # Get all changelogs for this publication
                            try:
                                changelogs = models.ServicePoolPublicationChangelog.objects.filter(
                                    publication=publication
                                ).values(
                                    'stamp', 'revision', 'log'
                                )
                                changelogs = list(changelogs)
                            except Exception:
                                changelogs = []

                            publications[publication.revision] = getSerializedFromModel(
                                publication, ['data']
                            )
                            publications[publication.revision][
                                'changelogs'
                            ] = changelogs

                        # get assigned groups
                        groups = []
                        for group in servicePool.assignedGroups.all():
                            groups.append(group.pretty_name)

                        # get calendar actions
                        calendarActions = {}
                        for calendarAction in models.CalendarAction.objects.filter(
                            service_pool=servicePool
                        ):
                            calendarActions[calendarAction.calendar.name] = {
                                'action': calendarAction.action,
                                'params': calendarAction.prettyParams,
                                'at_start': calendarAction.at_start,
                                'events_offset': calendarAction.events_offset,
                                'last_execution': calendarAction.last_execution,
                                'next_execution': calendarAction.next_execution,
                            }

                        # get calendar access
                        calendarAccess = {}
                        for ca in models.CalendarAccess.objects.filter(
                            service_pool=servicePool
                        ):
                            calendarAccess[ca.calendar.name] = ca.access

                        servicePools[servicePool.name] = {
                            '_': getSerializedFromModel(servicePool),
                            'calendarAccess': calendarAccess,
                            'calendarActions': calendarActions,
                            'groups': groups,
                            'publications': publications,
                        }

                    services[service.name] = {
                        '_': getSerializedFromManagedObject(service),
                        'servicePools': servicePools,
                    }

                providers[provider.name] = {
                    '_': getSerializedFromManagedObject(provider),
                    'services': services,
                }

            tree[counter('PROVIDERS')] = providers

            # authenticators
            authenticators = {}
            for authenticator in models.Authenticator.objects.all():
                # Groups
                # groups = {}
                # for group in authenticator.groups.all():
                #     groups[group.name] = getSerializedFromModel(group)
                authenticators[authenticator.name] = {
                    '_': getSerializedFromManagedObject(authenticator),
                    # 'groups': groups,
                }

            tree[counter('AUTHENTICATORS')] = authenticators

            # transports
            transports = {}
            for transport in models.Transport.objects.all():
                transports[transport.name] = getSerializedFromManagedObject(transport)

            tree[counter('TRANSPORTS')] = transports

            # Networks
            networks = {}
            for network in models.Network.objects.all():
                networks[network.name] = {
                    'networks': network.net_string,
                    'transports': [t.name for t in network.transports.all()],
                }

            tree[counter('NETWORKS')] = networks

            # os managers
            osManagers = {}
            for osManager in models.OSManager.objects.all():
                osManagers[osManager.name] = getSerializedFromManagedObject(osManager)

            tree[counter('OSMANAGERS')] = osManagers

            # calendars
            calendars = {}
            for calendar in models.Calendar.objects.all():
                # calendar rules
                rules = {}
                for rule in models.CalendarRule.objects.filter(calendar=calendar):
                    rules[rule.name] = getSerializedFromModel(
                        rule, ['calendar_id', 'name']
                    )

                calendars[calendar.name] = {
                    '_': getSerializedFromModel(calendar),
                    'rules': rules,
                }

            tree[counter('CALENDARS')] = calendars

            # Metapools
            metapools = {}
            for metapool in models.MetaPool.objects.all():
                metapools[metapool.name] = getSerializedFromModel(metapool)

            tree[counter('METAPOOLS')] = metapools

            # accounts
            accounts = {}
            for account in models.Account.objects.all():
                accounts[account.name] = {
                    '_': getSerializedFromModel(account),
                    'usages': list(
                        account.usages.all().values(
                            'user_name', 'pool_name', 'start', 'end'
                        )
                    ),
                }

            tree[counter('ACCOUNTS')] = accounts

            # Service pool groups
            servicePoolGroups = {}
            for servicePoolGroup in models.ServicePoolGroup.objects.all():
                servicePoolGroups[servicePoolGroup.name] = {
                    'comments': servicePoolGroup.comments,
                    'servicePools': [sp.name for sp in servicePoolGroup.servicesPools.all()],  # type: ignore
                }

            tree[counter('SERVICEPOOLGROUPS')] = servicePoolGroups

            # Gallery
            gallery = {}
            for galleryItem in models.Image.objects.all():
                gallery[galleryItem.name] = {
                    'size': f'{galleryItem.width}x{galleryItem.height}',
                    'stamp': galleryItem.stamp,
                    'length': len(galleryItem.data),
                }

            tree[counter('GALLERY')] = gallery

            # Actor tokens
            actorTokens = {}
            for actorToken in models.ActorToken.objects.all():
                actorTokens[actorToken.hostname] = getSerializedFromModel(actorToken, passwordFields=['token'])

            tree[counter('ACTORTOKENS')] = actorTokens

            # Tunnel tokens
            tunnelTokens = {}
            for tunnelToken in models.TunnelToken.objects.all():
                tunnelTokens[tunnelToken.hostname] = getSerializedFromModel(tunnelToken, passwordFields=['token'])

            tree[counter('TUNNELTOKENS')] = tunnelTokens

            self.stdout.write(yaml.safe_dump(tree, default_flow_style=False))

        except Exception as e:
            print('The command could not be processed: {}'.format(e))
            logger.exception('Exception processing %s', args)
