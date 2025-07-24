# -*- coding: utf-8 -*-

#
# Copyright (c) 2022-2023 Virtual Cable S.L.U.
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
import argparse
import logging
import typing
import datetime
import collections.abc

import yaml

from django.core.management.base import BaseCommand

from uds.core.util import cluster, log, model, config
from uds import models
from uds.core import types


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from django.db import models as dbmodels

CONSIDERED_OLD: typing.Final[datetime.timedelta] = datetime.timedelta(days=365)


def get_serialized_from_managed_object(
    mod: 'models.ManagedObjectModel',
    removable_fields: typing.Optional[list[str]] = None,
    callback: typing.Optional[typing.Callable[[models.ManagedObjectModel, dict[str, typing.Any]], None]] = None,
) -> collections.abc.Mapping[str, typing.Any]:
    try:
        obj: 'Module' = mod.get_instance()
        gui_types: dict[str, str] = {
            i['name']: str(i['gui']['type']) for i in obj.gui_description(skip_init_gui=True)
        }
        values = obj.get_fields_as_dict()
        # Remove password fields
        for fld, fld_type in gui_types.items():
            if fld_type == 'password':
                values[fld] = '********'
        # Some names are know "secret data"
        for i in ('serverCertificate', 'privateKey', 'server_certificate', 'private_key'):
            if i in values:
                values[i] = '********'
        # remove removable fields
        for i in removable_fields or []:
            if i in values:
                del values[i]
        # Append type_name to list
        values['id'] = mod.id
        values['uuid'] = mod.uuid
        values['type_name'] = str(obj.type_name)
        values['comments'] = mod.comments

        # May alter values with callback
        if callback:
            callback(mod, values)

        return values
    except Exception:
        return {}


def get_serialized_from_model(
    mod: 'dbmodels.Model',
    removable_fields: typing.Optional[list[str]] = None,
    password_fields: typing.Optional[list[str]] = None,
    exclude_uuid: bool = True,
) -> collections.abc.Mapping[str, typing.Any]:
    removable_fields = removable_fields or []
    password_fields = password_fields or []
    try:
        values = mod._meta.managers[0].filter(pk=mod.pk).values()[0]
        for i in (['uuid', 'id'] if exclude_uuid else []) + removable_fields:
            if i in values:
                del values[i]

        for i in password_fields:
            if i in values:
                values[i] = '********'
        return values
    except Exception:
        return {}


class Command(BaseCommand):
    help = "Outputs all UDS Trees of elements in YAML format"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            '--all-userservices',
            action='store_true',
            dest='alluserservices',
            default=False,
            help='Shows ALL user services, not just the ones with errors',
        )
        # Maximum items allowed for groups and user services
        parser.add_argument(
            '--max-items',
            action='store',
            dest='maxitems',
            default=400,
            help='Maximum elements exported for groups and user services',
        )

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def handle(self, *args: typing.Any, **options: typing.Any) -> None:
        logger.debug("Show Tree")
        # firt, genertate Provider-service-servicepool tree
        cntr = 0

        def counter(s: str) -> str:
            nonlocal cntr
            cntr += 1
            return f'{cntr:02d}.-{s}'

        max_items = int(options['maxitems'])
        now = model.sql_now()

        tree: dict[str, typing.Any] = {}
        try:
            providers: dict[str, typing.Any] = {}
            for provider in models.Provider.objects.all():
                services: dict[str, typing.Any] = {}
                services_count = 0
                servicepools_count = 0
                userservices_count = 0
                for service in provider.services.all():
                    servicepools: dict[str, typing.Any] = {}
                    partial_servicepools_count = 0
                    partial_userservices_count = 0
                    for servicepool in service.servicepools.all():
                        # get assigned user services with ERROR status
                        userservices: dict[str, typing.Any] = {}
                        fltr = servicepool.userServices.all()
                        if not options['alluserservices']:
                            fltr = fltr.filter(state=types.states.State.ERROR)
                        for item in fltr[:max_items]:  # at most max_items items
                            logs = [
                                f'{l["date"]}: {types.log.LogLevel.from_int(l["level"])} [{l["source"]}] - {l["message"]}'
                                for l in log.get_logs(item)
                            ]
                            userservices[item.friendly_name] = {
                                '_': {
                                    'id': item.uuid,
                                    'unique_id': item.unique_id,
                                    'friendly_name': item.friendly_name,
                                    'state': str(types.states.State.from_str(item.state).localized),
                                    'os_state': str(types.states.State.from_str(item.os_state).localized),
                                    'state_date': item.state_date,
                                    'creation_date': item.creation_date,
                                    'revision': item.publication and item.publication.revision or '',
                                    'is_cache': item.cache_level != 0,
                                    'ip': item.properties.get('ip', 'unknown'),
                                    'actor_version': item.properties.get('actor_version', 'unknown'),
                                },
                                'logs': logs,
                            }

                        partial_userservices_count = len(userservices)
                        userservices_count += partial_userservices_count

                        # get publications
                        publications: dict[str, typing.Any] = {}
                        changelogs = models.ServicePoolPublicationChangelog.objects.filter(
                            publication=servicepool
                        ).values('stamp', 'revision', 'log')

                        for publication in servicepool.publications.all():
                            publications[str(publication.revision)] = get_serialized_from_model(
                                publication, ['data']
                            )

                        # get calendar actions
                        calendar_actions: dict[str, typing.Any] = {}
                        for calendar_action in models.CalendarAction.objects.filter(service_pool=servicepool):
                            calendar_actions[calendar_action.calendar.name] = {
                                'action': calendar_action.action,
                                'params': calendar_action.pretty_params,
                                'at_start': calendar_action.at_start,
                                'events_offset': calendar_action.events_offset,
                                'last_execution': calendar_action.last_execution,
                                'next_execution': calendar_action.next_execution,
                            }

                        servicepools[f'{servicepool.name} ({partial_userservices_count})'] = {
                            '_': get_serialized_from_model(servicepool),
                            'userservices': userservices,
                            'transports': [t.name for t in servicepool.transports.all()],
                            'groups': [g.pretty_name for g in servicepool.assignedGroups.all()],
                            'calendar_access': {
                                ca.calendar.name: ca.access
                                for ca in models.CalendarAccess.objects.filter(service_pool=servicepool)
                            },
                            'calendar_actions': calendar_actions,
                            'publications': publications,
                            'publication_changelog': list(changelogs),
                        }

                    partial_servicepools_count = len(servicepools)
                    servicepools_count += partial_servicepools_count

                    services[f'{service.name} ({partial_servicepools_count}, {partial_userservices_count})'] = {
                        '_': get_serialized_from_managed_object(service),
                        'service_pools': servicepools,
                    }

                services_count += len(services)
                providers[f'{provider.name} ({services_count}, {servicepools_count}, {userservices_count})'] = {
                    '_': get_serialized_from_managed_object(provider),
                    'services': services,
                }

            tree[counter('PROVIDERS')] = providers

            # authenticators
            authenticators: dict[str, typing.Any] = {}
            for authenticator in models.Authenticator.objects.all():
                # Groups
                grps: dict[str, typing.Any] = {}
                for group in authenticator.groups.all()[:max_items]:  # at most max_items items
                    grps[group.name] = get_serialized_from_model(group, ['manager_id', 'name'])
                users_count: int = authenticator.users.count()
                last_year_users_count: int = authenticator.users.filter(
                    last_access__gt=now - CONSIDERED_OLD
                ).count()
                authenticators[authenticator.name] = {
                    '_': get_serialized_from_managed_object(authenticator),
                    'groups': grps,
                    'users_count': users_count,
                    'last_year_users_count': last_year_users_count,
                }

            tree[counter('AUTHENTICATORS')] = authenticators

            # transports
            def trans_callback(mod: models.ManagedObjectModel, values: dict[str, typing.Any]) -> None:
                # Add transport type
                if 'tunnel' in values:
                    tunnel = models.Server.objects.filter(
                        type=types.servers.ServerType.TUNNEL, uuid=values['tunnel']
                    ).first()
                    if tunnel:
                        values['tunnel'] = get_serialized_from_model(tunnel, exclude_uuid=False)
                    elif values['tunnel']:
                        values['tunnel'] += ' (not found)'

            transports: dict[str, typing.Any] = {}
            for transport in models.Transport.objects.all():
                transports[transport.name] = get_serialized_from_managed_object(
                    transport, callback=trans_callback
                )

            # Tunnel servers
            tunnels: dict[str, typing.Any] = {}
            for tunnel in models.Server.objects.filter(type=types.servers.ServerType.TUNNEL):
                tunnels[tunnel.hostname] = get_serialized_from_model(tunnel, exclude_uuid=False)

            # Networks
            networks: dict[str, typing.Any] = {}
            for network in models.Network.objects.all():
                networks[network.name] = {
                    'networks': network.net_string,
                    'transports': [t.name for t in network.transports.all()],
                }

            tree[counter('CONNECTIVITY')] = {
                'transports': transports,
                'tunnels': tunnels,
                'networks': networks,
            }

            # os managers
            osmanagers: dict[str, typing.Any] = {}
            for osmanager in models.OSManager.objects.all():
                osmanagers[osmanager.name] = get_serialized_from_managed_object(osmanager)

            tree[counter('OSMANAGERS')] = osmanagers

            # calendars
            calendars: dict[str, typing.Any] = {}
            for calendar in models.Calendar.objects.all():
                # calendar rules
                rules = {}
                for rule in models.CalendarRule.objects.filter(calendar=calendar):
                    rules[rule.name] = get_serialized_from_model(rule, ['calendar_id', 'name'])

                calendars[calendar.name] = {
                    '_': get_serialized_from_model(calendar),
                    'rules': rules,
                }

            tree[counter('CALENDARS')] = calendars

            tree[counter('METAPOOLS')] = {
                metapool.name: {
                    '_': get_serialized_from_model(metapool, removable_fields=['servicesPoolGroup_id']),
                    'service_pools': [
                        get_serialized_from_model(servicepool) for servicepool in metapool.members.all()
                    ],
                }
                for metapool in models.MetaPool.objects.all()
            }

            # accounts
            accounts: dict[str, typing.Any] = {}
            for account in models.Account.objects.all():
                accounts[account.name] = {
                    '_': get_serialized_from_model(account),
                    'usages': list(account.usages.all().values('user_name', 'pool_name', 'start', 'end')),
                }

            tree[counter('ACCOUNTS')] = accounts

            # Service pool groups
            servicepool_groups: dict[str, typing.Any] = {}
            for servicepool_group in models.ServicePoolGroup.objects.all():
                servicepool_groups[servicepool_group.name] = {
                    'comments': servicepool_group.comments,
                    'service_pools': [sp.name for sp in servicepool_group.servicesPools.all()],
                }

            tree[counter('SERVICEPOOLGROUPS')] = servicepool_groups

            # Gallery
            gallery: dict[str, typing.Any] = {}
            for gallery_item in models.Image.objects.all():
                gallery[gallery_item.name] = {
                    'size': f'{gallery_item.width}x{gallery_item.height}',
                    'stamp': gallery_item.stamp,
                    'length': gallery_item.length,
                }

            tree[counter('GALLERY')] = gallery

            # Rest of registerd servers
            registered_servers: dict[str, typing.Any] = {}
            for i, registered_server in enumerate(models.Server.objects.all()):
                registered_servers[f'{i}'] = get_serialized_from_model(registered_server)

            tree[counter('REGISTEREDSERVERS')] = registered_servers

            cfg: dict[str, typing.Any] = {}
            # Now, config, but not passwords
            for section, data in config.Config.get_config_values().items():
                for key, value in data.items():
                    # value is a dict, get 'value' key
                    cfg[f'{section}.{key}'] = value['value']

            tree[counter('CONFIG')] = cfg

            # Last 7 days of logs
            logs = [
                get_serialized_from_model(log_entry)
                for log_entry in models.Log.objects.filter(
                    created__gt=now - datetime.timedelta(days=7)
                ).order_by('-created')
            ]
            # Cluster nodes
            cluster_nodes: list[dict[str, str]] = [node.as_dict() for node in cluster.enumerate_cluster_nodes()]
            # Scheduled jobs
            scheduled_jobs: list[dict[str, typing.Any]] = [
                {i.name: get_serialized_from_model(i)} for i in models.Scheduler.objects.all()
            ]
            delayed_tasks: list[dict[str, typing.Any]] = [
                {task.insert_date.strftime('%Y-%m-%d %H:%M:%S'): get_serialized_from_model(task)}
                for task in models.DelayedTask.objects.all()
            ]

            # system
            tree[counter('SYSTEM')] = {
                'logs': logs,
                'cluster_nodes': cluster_nodes,
                'scheduled_jobs': scheduled_jobs,
                'delayed_tasks': delayed_tasks,
            }

            self.stdout.write(yaml.safe_dump(tree, default_flow_style=False))

        except Exception as e:
            self.stdout.write(f'The command could not be processed: {e}')
            self.stdout.flush()
            logger.exception('Exception processing %s', args)
