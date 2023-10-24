import typing

import django.db.models.deletion
from django.db import migrations, models

import uds.core.types.servers
import uds.core.types.os
import uds.core.util.model

from .fixers import properties_v4, transports_v4, providers_v4

ACTOR_TYPE: typing.Final[int] = uds.core.types.servers.ServerType.ACTOR.value

if typing.TYPE_CHECKING:
    import uds.models


def migrate_old_data(apps, schema_editor) -> None:
    try:
        Server: 'typing.Type[uds.models.Server]' = apps.get_model('uds', 'Server')
        # Not typed, disappeared on this migration
        ActorToken = apps.get_model('uds', 'ActorToken')

        # First, add uuid to existing registered servers
        for server in Server.objects.all():
            server.uuid = uds.core.util.model.generateUuid()
            server.save(update_fields=['uuid'])

        # Current Registered servers are tunnel servers, and all tunnel servers are linux os, so update ip
        Server.objects.all().update(os_type=uds.core.types.os.KnownOS.LINUX.os_name())

        # Now append actors to registered servers, with "unknown" os type (legacy)
        for token in ActorToken.objects.all():
            Server.objects.create(
                username=token.username,
                ip_from=token.ip_from,
                ip=token.ip,
                hostname=token.hostname,
                token=token.token,
                stamp=token.stamp,
                type=ACTOR_TYPE,
                os_type=uds.core.types.os.KnownOS.UNKNOWN.os_name(),
                data={
                    'mac': token.mac,
                    'pre_command': token.pre_command,
                    'post_command': token.post_command,
                    'runonce_command': token.runonce_command,
                    'log_level': token.log_level,
                    'custom': token.custom,
                },
            )
        # Migrate old transports
        transports_v4.migrate(apps, schema_editor)
        # Old providers and services
        providers_v4.migrate(apps, schema_editor)
        # Old properties to new model
        properties_v4.migrate(apps, schema_editor)
    except Exception as e:
        if 'no such table' not in str(e) and " doesn't exist" not in str(e):
            # Pytest is running this method twice??
            raise e


def rollback_old_data(apps, schema_editor) -> None:
    Server: 'typing.Type[uds.models.Server]' = apps.get_model('uds', 'Server')
    ActorToken = apps.get_model('uds', 'ActorToken')
    for server in Server.objects.filter(type=ACTOR_TYPE):
        if not server.data:
            continue  # Skip servers without data, they are not actors!!
        ActorToken.objects.create(
            username=server.username,
            ip_from=server.ip_from,
            ip=server.ip,
            hostname=server.hostname,
            token=server.token,
            stamp=server.stamp,
            mac=server.data['mac'],
            pre_command=server.data['pre_command'],
            post_command=server.data['post_command'],
            runonce_command=server.data['runonce_command'],
            log_level=server.data['log_level'],
            custom=server.data['custom'],
        )
        # Delete the server
        server.delete()

    transports_v4.rollback(apps, schema_editor)
    providers_v4.rollback(apps, schema_editor)
    properties_v4.rollback(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("uds", "0045_actortoken_custom_log_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Properties",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("owner_id", models.CharField(db_index=True, max_length=128)),
                ("owner_type", models.CharField(db_index=True, max_length=64)),
                (
                    "key",
                    models.CharField(max_length=64, db_index=True),
                ),
                ("value", models.JSONField(default=dict)),
            ],
        ),
        migrations.AddConstraint(
            model_name="properties",
            constraint=models.UniqueConstraint(
                fields=("owner_id", "owner_type", "key"), name="unique_property"
            ),
        ),
        migrations.RenameModel(
            'TunnelToken',
            'Server',
        ),
        migrations.CreateModel(
            name="ServerGroup",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "uuid",
                    models.CharField(
                        default=uds.core.util.model.generateUuid,
                        max_length=50,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=64, unique=True)),
                ("comments", models.CharField(default="", max_length=255)),
                (
                    "type",
                    models.IntegerField(default=uds.core.types.servers.ServerType["UNMANAGED"], db_index=True),
                ),
                ("subtype", models.CharField(db_index=True, default="", max_length=32)),
                ("host", models.CharField(default="", max_length=255)),
                ("port", models.IntegerField(default=0)),
                ("tags", models.ManyToManyField(to="uds.tag")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AlterField(
            model_name="server",
            name="token",
            field=models.CharField(
                db_index=True,
                default=uds.models.servers.create_token,
                max_length=48,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="server",
            name="tags",
            field=models.ManyToManyField(to="uds.tag"),
        ),
        migrations.AddField(
            model_name="server",
            name="uuid",
            field=models.CharField(default=uds.core.util.model.generateUuid, max_length=50, unique=False),
        ),
        migrations.RemoveConstraint(
            model_name="server",
            name="tt_ip_hostname",
        ),
        migrations.AddField(
            model_name="server",
            name="type",
            field=models.IntegerField(db_index=True, default=1),
        ),
        migrations.AddField(
            model_name="server",
            name="subtype",
            field=models.CharField(db_index=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="server",
            name="maintenance_mode",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="server",
            name="version",
            field=models.CharField(default="", max_length=32),
        ),
        migrations.AddField(
            model_name="server",
            name="data",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="server",
            name="os_type",
            field=models.CharField(default="unknown", max_length=32),
        ),
        migrations.AddField(
            model_name="server",
            name="mac",
            field=models.CharField(db_index=True, default="00:00:00:00:00:00", max_length=32),
        ),
        migrations.AddField(
            model_name="server",
            name="certificate",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="server",
            name="listen_port",
            field=models.IntegerField(default=43910),
        ),
        migrations.AddField(
            model_name="server",
            name="log_level",
            field=models.IntegerField(default=50000),
        ),
        migrations.AddField(
            model_name="server",
            name="locked_until",
            field=models.DateTimeField(blank=True, db_index=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="server",
            name="groups",
            field=models.ManyToManyField(
                related_name="servers",
                to="uds.servergroup",
            ),
        ),
        migrations.RunPython(
            migrate_old_data,
            rollback_old_data,
            atomic=True,
        ),
        migrations.DeleteModel(
            name="ActorToken",
        ),
        migrations.DeleteModel(
            name="UserServiceProperty",
        ),
        # After generating all the uuid's, set it as unique
        migrations.AlterField(
            model_name="server",
            name="uuid",
            field=models.CharField(default=uds.core.util.model.generateUuid, max_length=50, unique=True),
        ),
        # Add server group to transports
        migrations.AddField(
            model_name="transport",
            name="serverGroup",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transports",
                to="uds.servergroup",
            ),
        ),
        # Remove old UnsavedForeignKey
        migrations.AlterField(
            model_name="group",
            name="manager",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="groups",
                to="uds.authenticator",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="manager",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="users",
                to="uds.authenticator",
            ),
        ),
        # Remove unused validator field from ticket store
        migrations.RemoveField(
            model_name="ticketstore",
            name="validator",
        ),
        migrations.AlterField(
            model_name="servicepool",
            name="name",
            field=models.CharField(default="", max_length=192),
        ),
        migrations.AlterField(
            model_name="servicepool",
            name="short_name",
            field=models.CharField(default="", max_length=96),
        ),        
        migrations.AlterField(
            model_name="metapool",
            name="name",
            field=models.CharField(default="", max_length=192),
        ),
        migrations.AlterField(
            model_name="metapool",
            name="short_name",
            field=models.CharField(default="", max_length=96),
        ),        
        migrations.AlterField(
            model_name="authenticator",
            name="small_name",
            field=models.CharField(db_index=True, default="", max_length=128),
        ),
    ]
