# -*- coding: utf-8 -*-

#
# Copyright (c) 2026 Virtual Cable S.L.U.
# All rights reserved.
#
"""
Normalizes existing uds_user.name values and merges the duplicate rows that
invisible code points (BOM U+FEFF, ZWSP, ZWNJ, ZWJ, soft hyphen, ...) created.

Without this, the normalization added to Authenticator.get_or_create_user would
stop matching the polluted rows already stored, and the next login of an affected
user would create a brand new, empty account (losing groups, permissions and
assigned user services).
"""
import collections
import logging
import typing

from django.db import migrations

from uds.core.util.auth import normalize_username

logger = logging.getLogger(__name__)

# uds.core.types.log.LogObjectType.USER
LOG_OWNER_TYPE_USER = 5
# uds.models.User.get_owner_id_and_type
PROPERTIES_OWNER_TYPE_USER = 'user'


def _dedupe_user_names(apps: typing.Any, schema_editor: typing.Any) -> None:
    User = apps.get_model('uds', 'User')
    UserService = apps.get_model('uds', 'UserService')
    Permissions = apps.get_model('uds', 'Permissions')
    Log = apps.get_model('uds', 'Log')
    Properties = apps.get_model('uds', 'Properties')

    duplicates: dict[tuple[int, str], list[typing.Any]] = collections.defaultdict(list)
    for user in User.objects.all():
        duplicates[(user.manager_id, normalize_username(user.name))].append(user)

    for (_manager_id, clean_name), users in duplicates.items():
        # A name that is *only* invisible chars normalizes to empty: there is no safe
        # target to merge it into, so it is left untouched for an admin to look at.
        if not clean_name:
            continue

        # Keep the row that is already clean (its uuid is the one referenced elsewhere);
        # if none is, keep the most recently used one.
        keeper = sorted(
            users, key=lambda u: (u.name != clean_name, -u.last_access.timestamp(), u.id)
        )[0]
        losers = [u for u in users if u.id != keeper.id]

        if losers:
            loser_ids = [u.id for u in losers]
            loser_uuids = [u.uuid for u in losers]
            logger.info(
                'Merging %s duplicate user(s) of "%s" into user id %s', len(losers), clean_name, keeper.id
            )

            # Assigned services and permissions are FK-CASCADE: they must be moved before
            # the delete below, or they would be wiped along with the duplicate row.
            UserService.objects.filter(user_id__in=loser_ids).update(user=keeper)
            Permissions.objects.filter(user_id__in=loser_ids).update(user=keeper)
            Log.objects.filter(owner_type=LOG_OWNER_TYPE_USER, owner_id__in=loser_ids).update(
                owner_id=keeper.id
            )
            User.objects.filter(parent__in=loser_uuids).update(parent=keeper.uuid)

            for loser in losers:
                keeper.groups.add(*loser.groups.all())

            # Properties are unique on (owner_id, owner_type, key): move only the keys the
            # keeper does not already have, drop the rest.
            keeper_keys = set(
                Properties.objects.filter(
                    owner_id=keeper.uuid, owner_type=PROPERTIES_OWNER_TYPE_USER
                ).values_list('key', flat=True)
            )
            loser_properties = Properties.objects.filter(
                owner_id__in=loser_uuids, owner_type=PROPERTIES_OWNER_TYPE_USER
            )
            loser_properties.filter(key__in=keeper_keys).delete()
            loser_properties.update(owner_id=keeper.uuid)

            User.objects.filter(id__in=loser_ids).delete()

        if keeper.name != clean_name:
            keeper.name = clean_name
            keeper.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ("uds", "0047_servicepool_custom_message_and_more"),
    ]

    operations = [
        migrations.RunPython(_dedupe_user_names, migrations.RunPython.noop),
    ]
