import typing

from django.db import migrations, models
import django.db.models.deletion
from uds.core.util.os_detector import KnownOS

ACTOR_TYPE = 2  # Hardcoded value from uds/models/registered_servers.py

def migrate_old_data(apps, schema_editor):
    try:
        RegisteredServer = apps.get_model('uds', 'RegisteredServer')
        ActorToken = apps.get_model('uds', 'ActorToken')

        # Current Registered servers are tunnel servers, and all tunnel servers are linux os, so update ip
        RegisteredServer.objects.all().update(os_type=KnownOS.LINUX.os_name())

        # Now append actors to registered servers, with "unknown" os type (legacy)
        for token in ActorToken.objects.all():
            RegisteredServer.objects.create(
                username=token.username,
                ip_from=token.ip_from,
                ip=token.ip,
                ip_version=token.ip_version,
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
                }
            )
    except Exception as e:
        if 'no such table' not in str(e):
            # Pytest is running this method twice??
            raise e

def revert_old_data(apps, schema_editor):
    RegisteredServer = apps.get_model('uds', 'RegisteredServer')
    ActorToken = apps.get_model('uds', 'ActorToken')
    for server in RegisteredServer.objects.filter(kind=ACTOR_TYPE):
        ActorToken.objects.create(
            username=server.username,
            ip_from=server.ip_from,
            ip=server.ip,
            ip_version=server.ip_version,
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

class Migration(migrations.Migration):
    dependencies = [
        ("uds", "0045_actortoken_custom_log_name"),
    ]

    operations = [
        migrations.RenameModel(
            'TunnelToken',
            'RegisteredServer',
        ),
        migrations.RemoveConstraint(
            model_name="registeredserver",
            name="tt_ip_hostname",
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="kind",
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="sub_kind",
            field=models.CharField(default="", max_length=32),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="version",
            field=models.CharField(default="4.0.0", max_length=32),
        ),
        migrations.AddField(
            model_name="registeredserver",
            name="ip_version",
            field=models.IntegerField(default=4),
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
            field=models.CharField(
                db_index=True, default="00:00:00:00:00:00", max_length=32
            ),
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
            name="attached_to",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attached_servers",
                to="uds.provider",
            ),
        ),
        migrations.RunPython(
            migrate_old_data,
            revert_old_data,
            atomic=True,
        ),
        migrations.DeleteModel(
            name="ActorToken",
        ),
    ]
