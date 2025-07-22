import datetime
import logging
import socket
import typing

from django.db import transaction, OperationalError

from uds import models
from uds.core.util.iface import get_first_iface
from uds.core.util.model import sql_now, get_my_ip_from_db

logger = logging.getLogger(__name__)


class UDSClusterNode(typing.NamedTuple):
    """
    Represents a node in the cluster with its hostname and last seen date.
    """

    hostname: str
    ip: str
    last_seen: datetime.datetime
    mac: str = '00:00:00:00:00:00'

    def as_dict(self) -> dict[str, str]:
        """
        Returns a dictionary representation of the UDSClusterNode.
        """
        return {
            'hostname': self.hostname,
            'ip': self.ip,
            'last_seen': self.last_seen.isoformat(),
            'mac': self.mac,
        }

    def __str__(self) -> str:
        return f'{self.hostname} ({self.ip}) - Last seen: {self.last_seen.isoformat()} - MAC: {self.mac}'


def store_cluster_info() -> None:
    """
    Stores the current hostname in the database, ensuring that it is unique.
    This is used to identify the current node in a cluster.
    """
    iface = get_first_iface()
    ip = iface.ip if iface else get_my_ip_from_db()
    mac = iface.mac if iface else '00:00:00:00:00:00'

    try:
        hostname = socket.getfqdn() + '|' + ip
        date = sql_now().isoformat()
        with transaction.atomic():
            current_host_property = (
                models.Properties.objects.select_for_update()
                .filter(owner_id='cluster', owner_type='cluster', key=hostname)
                .first()
            )
            if current_host_property:
                # Update existing property
                current_host_property.value = {'last_seen': date, 'mac': mac}
                current_host_property.save()
            else:
                # Create new property
                models.Properties.objects.create(
                    owner_id='cluster', owner_type='cluster', key=hostname, value={'last_seen': date}
                )

    except OperationalError as e:
        # If we cannot connect to the database, we log the error
        logger.error("Could not store cluster hostname: %s", e)


def enumerate_cluster_nodes() -> list[UDSClusterNode]:
    """
    Enumerates all nodes in the cluster by fetching properties with owner_type 'cluster'.
    Returns a list of hostnames.
    """
    try:
        properties = models.Properties.objects.filter(owner_type='cluster')
        return [
            UDSClusterNode(
                hostname=prop.key.split('|')[0],
                ip=prop.key.split('|')[1],
                last_seen=datetime.datetime.fromisoformat(prop.value['last_seen']),
                mac=prop.value.get('mac', '00:00:00:00:00:00'),
            )
            for prop in properties
            if 'last_seen' in prop.value and '|' in prop.key
        ]
    except OperationalError as e:
        # If we cannot connect to the database, we log the error and return an empty list
        logger.error("Could not enumerate cluster nodes: %s", e)
        return []
