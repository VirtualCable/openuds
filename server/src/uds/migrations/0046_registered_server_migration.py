import typing

import django.db.models.deletion
from django.db import migrations, models

import uds.core.types.servers
import uds.core.util.model
from uds.core.util.os_detector import KnownOS

from .fixers import transports_v4

ACTOR_TYPE: typing.Final[int] = uds.core.types.servers.ServerType.ACTOR.value

if typing.TYPE_CHECKING:
    import uds.models


def migrate_old_data(apps, schema_editor) -> None:
    try:
        RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
        # Not typed, disappeared on this migration
        ActorToken = apps.get_model('uds', 'ActorToken')

        # First, add uuid to existing registered servers
        for server in RegisteredServer.objects.all():
            server.uuid = uds.core.util.model.generateUuid()
            server.save(update_fields=['uuid'])

        # Current Registered servers are tunnel servers, and all tunnel servers are linux os, so update ip
        RegisteredServer.objects.all().update(os_type=KnownOS.LINUX.os_name())

        # Now append actors to registered servers, with "unknown" os type (legacy)
        for token in ActorToken.objects.all():
            RegisteredServer.objects.create(
                username=token.username,
                ip_from=token.ip_from,
                ip=token.ip,
                hostname=token.hostname,
                token=token.token,
                stamp=token.stamp,
                kind=ACTOR_TYPE,
                os_type=KnownOS.UNKNOWN.os_name(),
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
    except Exception as e:
        if 'no such table' not in str(e):
            # Pytest is running this method twice??
            raise e


def rollback_old_data(apps, schema_editor) -> None:
    RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
    ActorToken = apps.get_model('uds', 'ActorToken')
    for server in RegisteredServer.objects.filter(kind=ACTOR_TYPE):
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


class Migration(migrations.Migration):
    dependencies = [
        ("uds", "0045_actortoken_custom_log_name"),
    ]

    operations = [
        migrations.RenameModel(
            'TunnelToken',
            'RegisteredServer',
        ),
        migrations.CreateModel(
            name="RegisteredServerGroup",
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
                ("kind", models.IntegerField(default=uds.core.types.servers.ServerType["LEGACY"], db_index=True)),
                ("sub_kind", models.CharField(db_index=True, default="", max_length=32)),
                ("host", models.CharField(default="", max_length=255)),
                ("port", models.IntegerField(default=0)),
                ("tags", models.ManyToManyField(to="uds.tag")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="registeredservergroup",
            constraint=models.UniqueConstraint(
                fields=("host", "port"), name="unique_host_port_group"
            ),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="tags",
            field=models.ManyToManyField(to="uds.tag"),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="uuid",
            field=models.CharField(default=uds.core.util.model.generateUuid, max_length=50, unique=False),
        ),
        migrations.RemoveConstraint(
            model_name="registeredserver",
            name="tt_ip_hostname",
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="kind",
            field=models.IntegerField(db_index=True, default=1),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="sub_kind",
            field=models.CharField(db_index=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="maintenance_mode",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="version",
            field=models.CharField(default="4.0.0", max_length=32),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="data",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="os_type",
            field=models.CharField(default="unknown", max_length=32),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="mac",
            field=models.CharField(db_index=True, default="00:00:00:00:00:00", max_length=32),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="certificate",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="listen_port",
            field=models.IntegerField(default=43910),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="log_level",
            field=models.IntegerField(default=50000),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="groups",
            field=models.ManyToManyField(
                related_name="servers",
                to="uds.registeredservergroup",
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
        # After generating all the uuid's, set it as unique
        migrations.AlterField(
            model_name="registeredserver",
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
                to="uds.registeredservergroup",
            ),
        ),
    ]
