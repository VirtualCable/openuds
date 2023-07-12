import typing

from django.db import migrations, models

ACTOR_TYPE = 2  # Hardcoded value from uds/models/registered_servers.py

def migrate_old_actor_tokens(apps, schema_editor):
    try:
        RegisteredServers = apps.get_model('uds', 'RegisteredServers')
        ActorToken = apps.get_model('uds', 'ActorToken')
        for token in ActorToken.objects.all():
            RegisteredServers.objects.create(
                username=token.username,
                ip_from=token.ip_from,
                ip=token.ip,
                ip_version=token.ip_version,
                hostname=token.hostname,
                token=token.token,
                stamp=token.stamp,
                kind=ACTOR_TYPE,
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

def revert_migration_to_old_actor_tokens(apps, schema_editor):
    RegisteredServers = apps.get_model('uds', 'RegisteredServers')
    ActorToken = apps.get_model('uds', 'ActorToken')
    for server in RegisteredServers.objects.filter(kind=ACTOR_TYPE):
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
            'RegisteredServers',
        ),
        migrations.RemoveConstraint(
            model_name="registeredservers",
            name="tt_ip_hostname",
        ),
        migrations.AddField(
            model_name="registeredservers",
            name="kind",
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name="registeredservers",
            name="ip_version",
            field=models.IntegerField(default=4),
        ),
        migrations.AddField(
            model_name="registeredservers",
            name="data",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(
            migrate_old_actor_tokens,
            revert_migration_to_old_actor_tokens,
            atomic=True,
        ),
        migrations.DeleteModel(
            name="ActorToken",
        ),
    ]
