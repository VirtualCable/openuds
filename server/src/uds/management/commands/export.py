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
from functools import reduce
import logging
import operator
import typing
import yaml

from django.core.management.base import BaseCommand
from django.db.models import Q

from uds import models

if typing.TYPE_CHECKING:
    import argparse
    from django.db.models import Model
    from uds.models.uuid_model import UUIDModel

logger = logging.getLogger(__name__)

ModelType = typing.TypeVar('ModelType', bound='UUIDModel')
T = typing.TypeVar('T')


def uuid_object_exporter(obj: 'UUIDModel') -> typing.Dict[str, typing.Any]:
    """
    Exports a uuid model to a dict
    """
    return {
        'uuid': obj.uuid,
    }


def managed_object_exporter(
    obj: models.ManagedObjectModel,
) -> typing.Dict[str, typing.Any]:
    """
    Exports a managed object to a dict
    """
    # Get uuid model
    m = uuid_object_exporter(obj)
    # Extend with managed object fields
    m.update(
        {
            'name': obj.name,
            'comments': obj.comments,
            'data': obj.data,
            'data_type': obj.data_type,
        }
    )
    return m


def provider_exporter(provider: models.Provider) -> typing.Dict[str, typing.Any]:
    """
    Exports a provider to a dict
    """
    p = managed_object_exporter(provider)
    p['maintenance_mode'] = provider.maintenance_mode
    return p


def service_exporter(service: models.Service) -> typing.Dict[str, typing.Any]:
    """
    Exports a service to a dict
    """
    s = managed_object_exporter(service)
    s['provider'] = service.provider.uuid
    s['token'] = service.token
    return s


def mfa_exporter(mfa: models.MFA) -> typing.Dict[str, typing.Any]:
    """
    Exports a mfa to a dict
    """
    m = managed_object_exporter(mfa)
    return m


def authenticator_exporter(
    authenticator: models.Authenticator,
) -> typing.Dict[str, typing.Any]:
    """
    Exports an authenticator to a dict
    """
    a = managed_object_exporter(authenticator)
    a['priority'] = authenticator.priority
    a['provider'] = authenticator.small_name
    a['visible'] = authenticator.state == models.Authenticator.VISIBLE
    a['enabled'] = authenticator.state != models.Authenticator.DISABLED
    return a


def user_exporter(user: models.User) -> typing.Dict[str, typing.Any]:
    """
    Exports a user to a dict
    """
    u = uuid_object_exporter(user)
    u.update(
        {
            'manager': user.manager.uuid,
            'name': user.name,
            'comments': user.comments,
            'real_name': user.real_name,
            'state': user.state,
            'password': user.password,
            'mfa_data': user.mfa_data,
            'staff_member': user.staff_member,
            'is_admin': user.is_admin,
            'last_access': user.last_access,
            'parent': user.parent,
            'created': user.created,
            'groups': [g.uuid for g in user.groups.all()],
        }
    )
    return u


def group_export(group: models.Group) -> typing.Dict[str, typing.Any]:
    """
    Exports a group to a dict
    """
    g = uuid_object_exporter(group)
    g.update(
        {
            'manager': group.manager.uuid,
            'name': group.name,
            'comments': group.comments,
            'state': group.state,
            'is_meta': group.is_meta,
            'meta_if_any': group.meta_if_any,
            'created': group.created,
        }
    )
    return g


def transport_exporter(transport: models.Transport) -> typing.Dict[str, typing.Any]:
    """
    Exports a transport to a dict
    """
    t = managed_object_exporter(transport)
    t.update(
        {
            'priority': transport.priority,
            'net_filtering': transport.net_filtering,
            'allowed_oss': transport.allowed_oss,
            'label': transport.label,
            'networks': [n.uuid for n in transport.networks.all()],
        }
    )
    return t


def network_exporter(network: models.Network) -> typing.Dict[str, typing.Any]:
    """
    Exports a network to a dict
    """
    n = uuid_object_exporter(network)
    n.update(
        {
            'name': network.name,
            'net_start': network.net_start,
            'net_end': network.net_end,
            'net_string': network.net_string,
        }
    )
    return n


def osmanager_exporter(osmanager: models.OSManager) -> typing.Dict[str, typing.Any]:
    """
    Exports an osmanager to a dict
    """
    o = managed_object_exporter(osmanager)
    return o


def calendar_exporter(calendar: models.Calendar) -> typing.Dict[str, typing.Any]:
    """
    Exports a calendar to a dict
    """
    c = uuid_object_exporter(calendar)
    c.update(
        {
            'name': calendar.name,
            'comments': calendar.comments,
            'modified': calendar.modified,
        }
    )
    return c


def calendar_rule_exporter(
    calendar_rule: models.CalendarRule,
) -> typing.Dict[str, typing.Any]:
    """
    Exports a calendar rule to a dict
    """
    c = uuid_object_exporter(calendar_rule)
    c.update(
        {
            'calendar': calendar_rule.calendar.uuid,
            'name': calendar_rule.name,
            'comments': calendar_rule.comments,
            'start': calendar_rule.start,
            'end': calendar_rule.end,
            'frequency': calendar_rule.frequency,
            'interval': calendar_rule.interval,
            'duration': calendar_rule.duration,
            'duration_unit': calendar_rule.duration_unit,
        }
    )
    return c


class Command(BaseCommand):
    help = 'Export entities from UDS to be imported in another UDS instance'

    VALID_ENTITIES: typing.Mapping[str, typing.Callable[[], str]]
    verbose: bool = True
    filter_args: typing.List[typing.Tuple[str, str]] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.VALID_ENTITIES = {
            'providers': self.export_providers,
            'services': self.export_services,
            'authenticators': self.export_authenticators,
            'users': self.export_users,
            'groups': self.export_groups,
            'mfa': self.export_mfa,
            'networks': self.export_networks,
            'transports': self.export_transports,
            'osmanagers': self.export_osmanagers,
        }

    def add_arguments(self, parser: 'argparse.ArgumentParser') -> None:
        # Accepts a list of valid entities to export
        parser.add_argument(
            'entities',
            nargs='+',
            choices=self.VALID_ENTITIES.keys(),
            default=self.VALID_ENTITIES.keys(),
            help='Entities to export',
        )

        # Output file name (will be appended .csv or .yaml)
        parser.add_argument(
            '--output',
            action='store',
            dest='output',
            default='/tmp/export.yaml',
            help='Output file name. Defaults to /tmp/export.yaml',
        )

        # Filter ALL entities by name, multiple names can be specified
        parser.add_argument(
            '--filter-name',
            action='append',
            dest='filter_name',
            default=[],
            help='Filter ALL entities by name',
        )

        # Filter ALL entities by uuid, multiple uuids can be specified
        parser.add_argument(
            '--filter-uuid',
            action='append',
            dest='filter_uuid',
            default=[],
            help='Filter ALL entities by uuid',
        )

        # quiet mode
        parser.add_argument(
            '--quiet',
            action='store_false',
            dest='verbose',
            default=True,
            help='Quiet mode',
        )

    def handle(self, *args, **options) -> None:
        self.verbose = options['verbose']

        if self.verbose:
            self.stderr.write(f'Exporting entities: {",".join(options["entities"])}')

        # Compose filter name for kwargs
        for i in options['filter_name']:
            self.filter_args.append(('name__icontains', i))

        for i in options['filter_uuid']:
            self.filter_args.append(('uuid', i))

        # some entities are redundant, so remove them from the list
        entities = self.remove_reduntant_entities(options['entities'])

        # For each entity, export it as yaml to output file
        with open(options['output'], 'w', encoding='utf8') as f:
            for entity in entities:
                self.stderr.write(f'Exporting {entity}')
                f.write(self.VALID_ENTITIES[entity]())
                f.write('')

        if self.verbose:
            self.stderr.write(f'Exported to {options["output"]}')

    def apply_filter(self, model: typing.Type[ModelType]) -> typing.Iterator[ModelType]:
        """
        Applies a filter to a model
        """
        if self.verbose:
            # Filter is a filter name, and an array of values
            values = [f'{k.split("__")[0]}={v}' for k, v in self.filter_args]
            self.stderr.write(f'Filtering {model.__name__}: \n  ', ending='')
            self.stderr.write("\n  ".join(values))
        # Generate "OR" filter with all kwargs
        if self.filter_args:
            return typing.cast(
                'typing.Iterator[ModelType]',
                model.objects.filter(reduce(operator.or_, (Q(**{k: v}) for k, v in self.filter_args))),
            )
        return typing.cast('typing.Iterator[ModelType]', model.objects.all().iterator())

    def output_count(self, message: str, iterable: typing.Iterable[T]) -> typing.Iterable[T]:
        """
        Outputs the count of an iterable
        """
        count = 0
        for v in iterable:
            count += 1
            if self.verbose:
                self.stderr.write(f'{message} {count}', ending='\r')
            yield v

        if self.verbose:
            self.stderr.write('\n')  # New line after count

    def export_providers(self) -> str:
        """
        Exports all providers to a list of dicts
        """
        return '# Providers\n' + yaml.safe_dump(
            [provider_exporter(p) for p in self.apply_filter(models.Provider)]
        )

    def export_services(self) -> str:
        # First, locate providers for services with the filter
        services_list = list(
            self.output_count('Filtering services', self.apply_filter(models.Service))
        )
        providers_list = {
            s.provider for s in self.output_count('Filtering providers', services_list)
        }
        # Now, export those providers
        providers = [
            provider_exporter(p)
            for p in self.output_count('Saving providers', providers_list)
        ]

        # Then, export services with the filter
        services = [
            service_exporter(s)
            for s in self.output_count('Saving services', services_list)
        ]

        return (
            '# Providers\n'
            + yaml.safe_dump(providers)
            + '# Services\n'
            + yaml.safe_dump(services)
    
    def export_mfa(self) -> str:
        """
        Exports all mfa to a list of dicts
        """
        return '# MFA\n' + yaml.safe_dump(
            [
                mfa_exporter(m)
                for m in self.output_count(
                    'Saving mfa',
                    self.apply_filter(models.MFA),
                )
            ]
        )

    def export_authenticators(self) -> str:
        """
        Exports all authenticators to a list of dicts
        """
        return '# Authenticators\n' + yaml.safe_dump(
            [
                authenticator_exporter(a)
                for a in self.output_count(
                    'Saving authenticators',
                    self.apply_filter(models.Authenticator),
                )
            ]
        )

    def export_users(self) -> str:
        """
        Exports all users to a list of dicts
        """
        # first, locate authenticators for users with the filter
        users_list = list(
            self.output_count('Filtering users', self.apply_filter(models.User))
        )
        authenticators_list = {
            u.manager for u in self.output_count('Filtering authenticators', users_list)
        }
        # Now, groups that contains those users
        groups_list = set()
        for u in self.output_count('Filtering groups', users_list):
            groups_list.update(u.groups.all())

        # now, export those authenticators
        authenticators = [
            authenticator_exporter(a)
            for a in self.output_count('Saving authenticators', authenticators_list)
        ]

        # then, export those groups
        groups = [
            group_export(g) for g in self.output_count('Saving groups', groups_list)
        ]

        # finally, export users with the filter
        users = [
            user_exporter(u) for u in self.output_count('Saving users', users_list)
        ]
        return (
            '# Authenticators\n'
            + yaml.safe_dump(authenticators)
            + '# Groups\n'
            + yaml.safe_dump(groups)
            + '# Users\n'
            + yaml.safe_dump(users)
        )

    def export_groups(self) -> str:
        """
        Exports all groups to a list of dicts
        """
        # First export authenticators for groups with the filter
        groups_list = list(
            self.output_count('Filtering groups', self.apply_filter(models.Group))
        )
        authenticators_list = {
            g.manager
            for g in self.output_count('Filtering authenticators', groups_list)
        }
        authenticators = [
            authenticator_exporter(a)
            for a in self.output_count('Saving authenticators', authenticators_list)
        ]

        # then, export groups with the filter
        groups = [
            group_export(g) for g in self.output_count('Saving groups', groups_list)
        ]

        return (
            '# Authenticators\n'
            + yaml.safe_dump(authenticators)
            + '# Groups\n'
            + yaml.safe_dump(groups)
        )

    def export_networks(self) -> str:
        """
        Exports all networks to a list of dicts
        """
        return '# Networks\n' + yaml.safe_dump(
            [
                network_exporter(n)
                for n in self.output_count(
                    'Saving networks', self.apply_filter(models.Network)
                )
            ]
        )

    def export_transports(self) -> str:
        """
        Exports all transports to a list of dicts
        """
        # First, export networks for transports with the filter
        transports_list = list(
            self.output_count(
                'Filtering transports', self.apply_filter(models.Transport)
            )
        )
        networks_list = set()
        for t in self.output_count('Filtering networks', transports_list):
            networks_list.update(t.networks.all())
        networks = [
            network_exporter(n)
            for n in self.output_count('Saving networks', networks_list)
        ]

        # then, export transports with the filter
        transports = [
            transport_exporter(t)
            for t in self.output_count('Saving transports', transports_list)
        ]

        return (
            '# Networks\n'
            + yaml.safe_dump(networks)
            + '# Transports\n'
            + yaml.safe_dump(transports)
        )

    def export_osmanagers(self) -> str:
        """
        Exports all osmanagers to a list of dicts
        """
        return '# OSManagers\n' + yaml.safe_dump(
            [
                osmanager_exporter(o)
                for o in self.output_count(
                    'Saving osmanagers', self.apply_filter(models.OSManager)
                )
            ]
        )

    def remove_reduntant_entities(self, entities: typing.List[str]) -> typing.List[str]:
        """
        Removes redundant entities from the list
        """
        REPLACES: typing.Mapping[str, typing.List[str]] = {
            'users': ['authenticators', 'groups'],
            'groups': ['authenticators'],
            'authenticators': [],
            'transports': ['networks'],
            'networks': [],
            'osmanagers': [],
            'services': ['providers'],
            'providers': [],
        }
        entities = list(set(entities))  # remove duplicates
        # Remove entities that are replaced by other entities
        for entity in entities:
            for replace in REPLACES.get(entity, []):
                if replace in entities:
                    entities.remove(replace)

        return entities
