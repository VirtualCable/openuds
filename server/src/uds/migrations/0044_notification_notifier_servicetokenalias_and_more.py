# Generated by Django 4.1.3 on 2022-11-29 02:37
# type: ignore

import typing
from django.db import migrations, models
import django.db.models.deletion
import uds.core.util.model
import uds.models.notifications
import uds.models.user_service_session


# Remove ServicePools with null service field
def remove_null_service_pools(apps: typing.Any, schema_editor: typing.Any):  # pylint: disable=unused-argument
    ServicePool = apps.get_model('uds', 'ServicePool')
    ServicePool.objects.filter(service__isnull=True).delete()


# No-Op backwards migration
def nop(apps: typing.Any, schema_editor: typing.Any):  # pylint: disable=unused-argument
    pass


# Python update network fields to allow ipv6
# We will
def update_network_model(apps: typing.Any, schema_editor: typing.Any):  # pylint: disable=unused-argument
    import uds.models.network  # pylint: disable=import-outside-toplevel,redefined-outer-name

    Network = apps.get_model('uds', 'Network')
    try:
        for net in Network.objects.all():
            # Store the net_start and net_end on new fields "start" and "end", that are strings
            # to allow us to store ipv6 addresses
            # pylint: disable=protected-access
            net.start = uds.models.network.Network.hexlify(net.net_start)
            # pylint: disable=protected-access
            net.end = uds.models.network.Network.hexlify(net.net_end)
            net.version = 4  # Previous versions only supported ipv4
            net.save(update_fields=['start', 'end', 'version'])
    except Exception as e:
        print(f'Error updating network model: {e}')  # Will fail on pytest, but it's ok


class Migration(migrations.Migration):
    dependencies = [
        ("uds", "0043_auto_20220704_2120"),
    ]

    operations = [
        migrations.RunPython(remove_null_service_pools, nop),
        migrations.CreateModel(
            name="Notification",
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
                ("stamp", models.DateTimeField(auto_now_add=True)),
                ("group", models.CharField(db_index=True, max_length=128)),
                ("identificator", models.CharField(db_index=True, max_length=128)),
                ("level", models.PositiveIntegerField()),
                ("message", models.TextField()),
                ("processed", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "uds_notification",
            },
        ),
        migrations.CreateModel(
            name="Notifier",
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
                        default=uds.core.util.model.generate_uuid,
                        max_length=50,
                        unique=True,
                    ),
                ),
                ("data_type", models.CharField(max_length=128)),
                ("data", models.TextField(default="")),
                ("name", models.CharField(default="", max_length=128)),
                ("comments", models.CharField(default="", max_length=256)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "level",
                    models.PositiveIntegerField(
                        default=uds.models.notifications.LogLevel["ERROR"]
                    ),
                ),
            ],
            options={
                "db_table": "uds_notify_prov",
            },
        ),
        migrations.CreateModel(
            name="ServiceTokenAlias",
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
                ("alias", models.CharField(max_length=64, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="UserServiceSession",
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
                    "session_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default=uds.models.user_service_session._session_id_generator,  # pylint: disable=protected-access
                        max_length=128,
                    ),
                ),
                ("start", models.DateTimeField(default=uds.core.util.model.sql_now)),
                ("end", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "uds__user_service_session",
            },
        ),
        migrations.DeleteModel(
            name="DBFile",
        ),
        migrations.RemoveField(
            model_name="userpreference",
            name="user",
        ),
        migrations.RemoveField(
            model_name="authenticator",
            name="visible",
        ),
        migrations.RemoveField(
            model_name="service",
            name="proxy",
        ),
        migrations.RemoveField(
            model_name="transport",
            name="nets_positive",
        ),
        migrations.RemoveField(
            model_name="userservice",
            name="cluster_node",
        ),
        migrations.AddField(
            model_name="actortoken",
            name="ip_version",
            field=models.IntegerField(default=4),
        ),
        migrations.AddField(
            model_name="authenticator",
            name="net_filtering",
            field=models.CharField(db_index=True, default="n", max_length=1),
        ),
        migrations.AddField(
            model_name="authenticator",
            name="state",
            field=models.CharField(db_index=True, default="v", max_length=1),
        ),
        migrations.AddField(
            model_name="config",
            name="help",
            field=models.CharField(default="", max_length=256),
        ),
        migrations.AddField(
            model_name="metapool",
            name="ha_policy",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="network",
            name="authenticators",
            field=models.ManyToManyField(
                db_table="uds_net_auths",
                related_name="networks",
                to="uds.authenticator",
            ),
        ),
        migrations.AddField(
            model_name="network",
            name="end",
            field=models.CharField(db_index=True, default="0", max_length=32),
        ),
        migrations.AddField(
            model_name="network",
            name="start",
            field=models.CharField(db_index=True, default="0", max_length=32),
        ),
        migrations.AddField(
            model_name="network",
            name="version",
            field=models.IntegerField(default=4),
        ),
        # Run python code to update network model
        migrations.RunPython(update_network_model, nop),
        migrations.RemoveField(
            model_name="network",
            name="net_end",
        ),
        migrations.RemoveField(
            model_name="network",
            name="net_start",
        ),
        migrations.AddField(
            model_name="service",
            name="max_services_count_type",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="transport",
            name="net_filtering",
            field=models.CharField(db_index=True, default="n", max_length=1),
        ),
        migrations.AlterField(
            model_name="account",
            name="comments",
            field=models.CharField(default="", max_length=256),
        ),
        migrations.AlterField(
            model_name="account",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="accountusage",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="actortoken",
            name="hostname",
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name="actortoken",
            name="ip",
            field=models.CharField(max_length=45),
        ),
        migrations.AlterField(
            model_name="actortoken",
            name="ip_from",
            field=models.CharField(max_length=45),
        ),
        migrations.AlterField(
            model_name="authenticator",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="calendar",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="calendaraccess",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="calendaraccessmeta",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="calendaraction",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="calendarrule",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="group",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="image",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="metapool",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="metapoolmember",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="mfa",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="network",
            name="net_string",
            field=models.CharField(default="", max_length=240),
        ),
        migrations.AlterField(
            model_name="network",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="osmanager",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="permissions",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="provider",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="scheduler",
            name="owner_server",
            field=models.CharField(db_index=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="service",
            name="token",
            field=models.CharField(
                blank=True, default=None, max_length=64, null=True, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="service",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="servicepool",
            name="service",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="deployedServices",
                to="uds.service",
            ),
        ),
        migrations.AlterField(
            model_name="servicepool",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="servicepoolgroup",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="servicepoolpublication",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="tag",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="ticketstore",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="transport",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="tunneltoken",
            name="hostname",
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name="tunneltoken",
            name="ip",
            field=models.CharField(max_length=45),
        ),
        migrations.AlterField(
            model_name="tunneltoken",
            name="ip_from",
            field=models.CharField(max_length=45),
        ),
        migrations.AlterField(
            model_name="user",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="userservice",
            name="src_hostname",
            field=models.CharField(default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="userservice",
            name="src_ip",
            field=models.CharField(default="", max_length=45),
        ),
        migrations.AlterField(
            model_name="userservice",
            name="uuid",
            field=models.CharField(
                default=uds.core.util.model.generate_uuid, max_length=50, unique=True
            ),
        ),
        migrations.DeleteModel(
            name="Proxy",
        ),
        migrations.DeleteModel(
            name="UserPreference",
        ),
        migrations.AddField(
            model_name="userservicesession",
            name="user_service",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sessions",
                to="uds.userservice",
            ),
        ),
        migrations.AddField(
            model_name="servicetokenalias",
            name="service",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="aliases",
                to="uds.service",
            ),
        ),
        migrations.AddField(
            model_name="notifier",
            name="tags",
            field=models.ManyToManyField(to="uds.tag"),
        ),
        migrations.AddConstraint(
            model_name="userservicesession",
            constraint=models.UniqueConstraint(
                fields=("session_id", "user_service"), name="u_session_userservice"
            ),
        ),
        migrations.AlterField(
            model_name="log",
            name="data",
            field=models.CharField(default="", max_length=4096),
        ),
    ]
