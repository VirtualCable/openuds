# pylint: disable=unused-import

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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

# Imports all models so they are available for migrations, etc..
from .managed_object_model import ManagedObjectModel

# Permissions
from .permissions import Permissions

# Services
from .provider import Provider
from .service import Service, ServiceTokenAlias

# Os managers
from .os_manager import OSManager

# Transports
from .transport import Transport
from .network import Network

# Authenticators
from .authenticator import Authenticator
from .user import User
from .group import Group

# Provisioned services
from .service_pool import ServicePool  # New name
from .meta_pool import MetaPool, MetaPoolMember
from .service_pool_group import ServicePoolGroup
from .service_pool_publication import ServicePoolPublication, ServicePoolPublicationChangelog

from .user_service import UserService
from .user_service_property import UserServiceProperty
from .user_service_session import UserServiceSession

# Especific log information for an user service
from .log import Log

# Stats
from .stats_counters import StatsCounters
from .stats_counters_accum import StatsCountersAccum
from .stats_events import StatsEvents

# General utility models, such as a database cache (for caching remote content of slow connections to external services providers for example)
# We could use django cache (and maybe we do it in a near future), but we need to clean up things when objecs owning them are deleted
from .cache import Cache
from .config import Config
from .storage import Storage
from .unique_id import UniqueId

# Workers/Schedulers related
from .scheduler import Scheduler
from .delayed_task import DelayedTask

# Image galery related
from .image import Image

# Ticket storage
from .ticket_store import TicketStore

# Calendar related
from .calendar import Calendar
from .calendar_rule import CalendarRule

from .calendar_access import CalendarAccess, CalendarAccessMeta
from .calendar_action import CalendarAction

# Accounting
from .account import Account
from .account_usage import AccountUsage

# Tagging
from .tag import Tag, TaggingMixin

# Tokens
from .registered_servers import RegisteredServer

# Notifications & Alerts
from .notifications import Notification, Notifier, LogLevel
# Multi factor authentication
from .mfa import MFA
