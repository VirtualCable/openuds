# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import base64
import logging
import re
import struct
import typing

from django.urls import reverse
from django.utils.translation import gettext as _

from cryptography import x509 as crypto_x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization.pkcs7 import PKCS7Options, PKCS7SignatureBuilder

from uds import models
from uds.core import consts, exceptions, types
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.exceptions.services import ServiceNotReadyError
from uds.core.types.log import LogLevel, LogSource
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_stamp_seconds
from uds.core.util.rest.tools import match
from uds.models import TicketStore, User
from uds.REST import Handler

logger = logging.getLogger(__name__)

CLIENT_VERSION: typing.Final[str] = consts.system.VERSION
LOG_ENABLED_DURATION: typing.Final[int] = 2 * 60 * 60 * 24  # 2 days

# Settings that Microsoft's RDP client includes in signature verification.
# Order matters: it matches the order expected by mstsc.exe.
_RDP_SECURE_SETTINGS: typing.Final[list[tuple[str, str]]] = [
    ('full address:s:', 'Full Address'),
    ('alternate full address:s:', 'Alternate Full Address'),
    ('pcb:s:', 'PCB'),
    ('use redirection server name:i:', 'Use Redirection Server Name'),
    ('server port:i:', 'Server Port'),
    ('negotiate security layer:i:', 'Negotiate Security Layer'),
    ('enablecredsspsupport:i:', 'EnableCredSspSupport'),
    ('disableconnectionsharing:i:', 'DisableConnectionSharing'),
    ('autoreconnection enabled:i:', 'AutoReconnection Enabled'),
    ('gatewayhostname:s:', 'GatewayHostname'),
    ('gatewayusagemethod:i:', 'GatewayUsageMethod'),
    ('gatewayprofileusagemethod:i:', 'GatewayProfileUsageMethod'),
    ('gatewaycredentialssource:i:', 'GatewayCredentialsSource'),
    ('support url:s:', 'Support URL'),
    ('promptcredentialonce:i:', 'PromptCredentialOnce'),
    ('require pre-authentication:i:', 'Require pre-authentication'),
    ('pre-authentication server address:s:', 'Pre-authentication server address'),
    ('alternate shell:s:', 'Alternate Shell'),
    ('shell working directory:s:', 'Shell Working Directory'),
    ('remoteapplicationprogram:s:', 'RemoteApplicationProgram'),
    ('remoteapplicationexpandworkingdir:s:', 'RemoteApplicationExpandWorkingdir'),
    ('remoteapplicationmode:i:', 'RemoteApplicationMode'),
    ('remoteapplicationguid:s:', 'RemoteApplicationGuid'),
    ('remoteapplicationname:s:', 'RemoteApplicationName'),
    ('remoteapplicationicon:s:', 'RemoteApplicationIcon'),
    ('remoteapplicationfile:s:', 'RemoteApplicationFile'),
    ('remoteapplicationfileextensions:s:', 'RemoteApplicationFileExtensions'),
    ('remoteapplicationcmdline:s:', 'RemoteApplicationCmdLine'),
    ('remoteapplicationexpandcmdline:s:', 'RemoteApplicationExpandCmdLine'),
    ('prompt for credentials:i:', 'Prompt For Credentials'),
    ('authentication level:i:', 'Authentication Level'),
    ('audiomode:i:', 'AudioMode'),
    ('redirectdrives:i:', 'RedirectDrives'),
    ('redirectprinters:i:', 'RedirectPrinters'),
    ('redirectcomports:i:', 'RedirectCOMPorts'),
    ('redirectsmartcards:i:', 'RedirectSmartCards'),
    ('redirectposdevices:i:', 'RedirectPOSDevices'),
    ('redirectclipboard:i:', 'RedirectClipboard'),
    ('devicestoredirect:s:', 'DevicesToRedirect'),
    ('drivestoredirect:s:', 'DrivesToRedirect'),
    ('loadbalanceinfo:s:', 'LoadBalanceInfo'),
    ('redirectdirectx:i:', 'RedirectDirectX'),
    ('rdgiskdcproxy:i:', 'RDGIsKDCProxy'),
    ('kdcproxyname:s:', 'KDCProxyName'),
    ('eventloguploadaddress:s:', 'EventLogUploadAddress'),
]


def _sign_rdp_content(rdp_content: str) -> str:
    """Sign an RDP file content using the configured server certificate.

    Replicates exactly what Microsoft's rdpsign.exe does:
      1. Extract the subset of settings covered by the signature.
      2. Build a UTF-16LE message blob (identical to what mstsc.exe verifies).
      3. Sign with CMS/PKCS#7 detached signature (DER, no attributes, no SMIME caps).
      4. Prepend the 12-byte Microsoft header and base64-encode the result.
      5. Append signscope and signature lines to the RDP content.

    Args:
        rdp_content: The RDP file content as a Python string (any line-ending style).

    Returns:
        Signed RDP content as a string with \\r\\n line endings.

    Raises:
        Exception: If signing is not configured or no signable settings are found.
    """
    sign_cert_pem = GlobalConfig.RDP_SIGN_CERT.as_str().strip()
    sign_key_pem = GlobalConfig.RDP_SIGN_KEY.as_str().strip()

    if not sign_cert_pem or not sign_key_pem:
        raise Exception('RDP signing certificate/key not configured in Security settings')

    cert = crypto_x509.load_pem_x509_certificate(sign_cert_pem.encode(), default_backend())
    private_key = serialization.load_pem_private_key(sign_key_pem.encode(), password=None, backend=default_backend())

    # Optional intermediate chain
    chain_certs: list[crypto_x509.Certificate] = []
    chain_pem = GlobalConfig.RDP_SIGN_CHAIN.as_str().strip()
    if chain_pem:
        for block in re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', chain_pem, re.DOTALL):
            chain_certs.append(crypto_x509.load_pem_x509_certificate(block.encode(), default_backend()))

    # Normalise line endings and strip each line
    lines = [line.strip() for line in rdp_content.replace('\r\n', '\n').replace('\r', '\n').split('\n')]

    settings: list[str] = []
    fulladdress: typing.Optional[str] = None
    alternatefulladdress: typing.Optional[str] = None

    for v in lines:
        if not v:
            continue
        if v.startswith('full address:s:'):
            fulladdress = v[15:]
        elif v.startswith('alternate full address:s:'):
            alternatefulladdress = v[25:]
        elif v.startswith('signature:s:') or v.startswith('signscope:s:'):
            continue  # Strip any pre-existing signature/signscope
        settings.append(v)

    # Prevent address-spoofing via alternate full address
    if fulladdress and not alternatefulladdress:
        settings.append('alternate full address:s:' + fulladdress)

    # Collect only the settings covered by the signature, preserving order
    signnames: list[str] = []
    signlines: list[str] = []
    for prefix, name in _RDP_SECURE_SETTINGS:
        for v in settings:
            if v.startswith(prefix):
                signnames.append(name)
                signlines.append(v)
                break  # Only first match per setting key

    if not signnames:
        raise Exception('No signable settings found in RDP content')

    # Build the message blob exactly as mstsc.exe expects: UTF-16LE, CRLF, NUL-terminated
    msgtext = '\r\n'.join(signlines) + '\r\n' + 'signscope:s:' + ','.join(signnames) + '\r\n' + '\x00'
    msgblob = msgtext.encode('UTF-16LE')

    # Sign: equivalent to: openssl smime -sign -binary -noattr -nosmimecap -outform DER
    # Note: NoAttributes is a superset of NoCapabilities in the Python API.
    builder = PKCS7SignatureBuilder().set_data(msgblob).add_signer(cert, private_key, hashes.SHA256())
    for chain_cert in chain_certs:
        builder = builder.add_certificate(chain_cert)
    sig_der = builder.sign(
        serialization.Encoding.DER,
        [PKCS7Options.Binary, PKCS7Options.NoAttributes],
    )

    # Prepend the 12-byte Microsoft header (two unknown DWORDs + length DWORD)
    msgsig = struct.pack('<III', 0x00010001, 0x00000001, len(sig_der)) + sig_der
    sigval = base64.b64encode(msgsig).decode('ascii')

    # Reassemble: original settings + signscope + signature, CRLF line endings
    result = '\r\n'.join(settings)
    result += '\r\nsignscope:s:' + ','.join(signnames)
    result += '\r\nsignature:s:' + sigval
    result += '\r\n'
    return result


# Enclosed methods under /client path
class Client(Handler):
    """
    Processes Client requests
    """

    authenticated = False  # Client requests are not authenticated

    @staticmethod
    def result(
        result: typing.Any = None,
        error: typing.Optional[typing.Union[str, int]] = None,
        error_code: int = 0,
        is_retrayable: bool = False,
    ) -> dict[str, typing.Any]:
        """
        Helper method to create a "result" set for actor response

        Args:
            result: Result value to return (can be None, in which case it is converted to empty string '')
            error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
            error_code: Code of the error to return, if error is not None
            retryable: If True, this operation can (and must) be retried

        Returns:
            A dictionary, suitable for REST response
        """
        result = result if result is not None else ''
        res = {'result': result}
        if error:
            if isinstance(error, int):
                error = types.errors.Error.from_int(error).message
            # error = str(error)  # Ensures error is an string
            if error_code != 0:
                # Reformat error so it is better understood by users
                # error += ' (code {0:04X})'.format(errorCode)
                error = (
                    _('Your service is being created. Please, wait while we complete it')
                    + f' ({int(error_code)*25}%)'
                )

            res['error'] = error
            # is_retrayable is new key, but we keep retryable for compatibility
            res['is_retryable'] = res['retryable'] = '1' if is_retrayable else '0'

        logger.debug('Client Result: %s', res)

        return res

    def test(self) -> dict[str, typing.Any]:
        """
        Executes and returns the test
        """
        return Client.result(_('Correct'))

    def process(self, ticket: str, scrambler: str) -> dict[str, typing.Any]:
        info: typing.Optional[types.services.UserServiceInfo] = None
        hostname = self._params.get('hostname', '')  # Or if hostname is not included...
        version = self._params.get('version', '0.0.0')
        src_ip = self._request.ip

        if version < consts.system.VERSION_REQUIRED_CLIENT:
            return Client.result(error='Client version not supported.\n Please, upgrade it.')

        # Ip is optional,
        if GlobalConfig.HONOR_CLIENT_IP_NOTIFY.as_bool() is True:
            src_ip = self._params.get('ip', src_ip)

        logger.debug(
            'Got Ticket: %s, scrambled: %s, Hostname: %s, Ip: %s',
            ticket,
            scrambler,
            hostname,
            src_ip,
        )

        try:
            data: dict[str, typing.Any] = TicketStore.get(ticket)
        except TicketStore.InvalidTicket:
            return Client.result(error=types.errors.Error.ACCESS_DENIED)
        
        if scrambler == "rdp_signature":
            # Return signing certificate info so the client can install it in the trust store.
            # The actual RDP signing is done via POST (see post() handler).
            sign_cert = GlobalConfig.RDP_SIGN_CERT.as_str().strip()
            chain = GlobalConfig.RDP_SIGN_CHAIN.as_str().strip()
            if not sign_cert:
                return Client.result(error='RDP signing not configured')
            return Client.result(result={'cert': sign_cert, 'chain': chain})

        self._request.user = User.objects.get(uuid=data['user'])

        try:
            logger.debug(data)
            info = UserServiceManager.manager().get_user_service_info(
                self._request.user,
                self._request.os,
                self._request.ip,
                data['service'],
                data['transport'],
                client_hostname=hostname,
            )
            logger.debug('Res: %s', info)
            password = CryptoManager.manager().symmetric_decrypt(data['password'], scrambler)

            # userService.setConnectionSource(srcIp, hostname)  # Store where we are accessing from so we can notify Service
            if not info.ip:
                raise ServiceNotReadyError()

            transport_script = info.transport.get_instance().encoded_transport_script(
                info.userservice,
                info.transport,
                info.ip,
                self._request.os,
                self._request.user,
                password,
                self._request,
            )

            logger.debug('Script: %s', transport_script)

            # Log is enabled if user has log_enabled property set to
            try:
                log_enabled_since_limit = sql_stamp_seconds() - LOG_ENABLED_DURATION
                log_enabled_since = self._request.user.properties.get('client_logging', log_enabled_since_limit)
                is_logging_enabled = False if log_enabled_since <= log_enabled_since_limit else True
            except Exception:
                is_logging_enabled = False
            log: dict[str, 'str|None'] = {
                'level': 'DEBUG',
                'ticket': None,
            }

            if is_logging_enabled:
                log['ticket'] = TicketStore.create(
                    {
                        'user': self._request.user.uuid,
                        'userservice': info.userservice.uuid,
                        'type': 'log',
                    },
                    # Long enough for a looong time, will be cleaned on first access
                    # Or 24 hours after creation, whatever happens first
                    validity=60 * 60 * 24,
                )

            # Always create a short-lived signing ticket so transport scripts can
            # request server-side RDP signing via POST /{sign_ticket}/rdp_signature.
            sign_ticket = TicketStore.create(
                {
                    'user': self._request.user.uuid,
                    'userservice': info.userservice.uuid,
                    'type': 'rdp_sign',
                },
                validity=60 * 60,  # 1 hour – enough for any reasonable session
            )
            # Inject into transport parameters so scripts can access sp['sign_ticket']
            params_with_sign = dict(transport_script.parameters)
            params_with_sign['sign_ticket'] = sign_ticket
            transport_script.parameters = params_with_sign

            return Client.result(
                result={
                    'script': transport_script.script,
                    'type': transport_script.script_type,
                    'signature': transport_script.signature_b64,  # It is already on base64
                    'params': transport_script.encoded_parameters,
                    'log': log,
                }
            )
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            TicketStore.revalidate(ticket, 20)  # Retry will be in at most 5 seconds, so 20 is fine :)
            return Client.result(
                error=types.errors.Error.SERVICE_IN_PREPARATION, error_code=e.code, is_retrayable=True
            )
        except Exception as e:
            logger.exception("Exception")
            return Client.result(error=str(e))

        finally:
            # ensures that we mark the service as accessed by client
            # so web interface can show can react to this
            if info and info.userservice:
                info.userservice.properties['accessed_by_client'] = True

    def post(self) -> dict[str, typing.Any]:
        """
        Processes put requests

        Currently, only "upload logs"
        """
        logger.debug('Client args for POST: %s', self._args)
        try:
            ticket, command = self._args[:2]
            try:
                data: dict[str, typing.Any] = TicketStore.get(ticket)
            except TicketStore.InvalidTicket:
                return Client.result(error=types.errors.Error.ACCESS_DENIED)

            self._request.user = User.objects.get(uuid=data['user'])

            # Handle rdp_signature before we require a userservice
            if command == 'rdp_signature':
                if data.get('type') != 'rdp_sign':
                    return Client.result(error='Invalid ticket type for RDP signing')
                rdp_content: str = self._params.get('rdp', '')
                if not rdp_content:
                    return Client.result(error='Missing RDP content')
                try:
                    signed = _sign_rdp_content(rdp_content)
                    return Client.result(result=signed)
                except Exception as e:
                    logger.exception('RDP signing failed')
                    return Client.result(error=str(e))

            try:
                userservice = models.UserService.objects.get(uuid=data['userservice'])
            except models.UserService.DoesNotExist:
                return Client.result(error='Service not found')

            match command:
                case 'log':
                    if data.get('type') != 'log':
                        return Client.result(error='Invalid command')

                    log: str = self._params.get('log', '')
                    # Right now, log to logger, but will be stored with user logs
                    logger.info('Client %s: %s', self._request.user.pretty_name, userservice.service_pool.name)
                    for line in log.split('\n'):
                        # Firt word is level
                        try:
                            level, message = line.split(' ', 1)
                            userservice.log(message, LogLevel.from_str(level), LogSource.CLIENT)
                            logger.info('Client %s: %s', self._request.user.pretty_name, message)
                        except Exception:
                            # If something goes wrong, log it as debug
                            pass
                case _:
                    return Client.result(error='Invalid command')

        except Exception as e:
            return Client.result(error=str(e))

        return Client.result(result='Ok')

    def get(self) -> dict[str, typing.Any]:
        """
        Processes get requests
        """
        logger.debug('Client args for GET: %s', self._args)

        def _error() -> None:
            raise exceptions.rest.RequestError('Invalid request')

        def _noargs() -> dict[str, typing.Any]:
            return Client.result(
                {
                    'availableVersion': CLIENT_VERSION,  # Compat with old clients, TB removed soon...
                    'available_version': CLIENT_VERSION,
                    'requiredVersion': consts.system.VERSION_REQUIRED_CLIENT,  # Compat with old clients, TB removed soon...
                    'required_version': consts.system.VERSION_REQUIRED_CLIENT,
                    'downloadUrl': self._request.build_absolute_uri(
                        reverse('page.client-download')
                    ),  # Compat with old clients, TB removed soon...
                    'client_link': self._request.build_absolute_uri(reverse('page.client-download')),
                }
            )

        return match(
            self._args,
            _error,  # In case of error, raises RequestError
            ((), _noargs),  # No args, return version
            (('test',), self.test),  # Test request, returns "Correct"
            (
                (
                    '<ticket>',
                    '<crambler>',
                ),
                self.process,
            ),  # Process request, needs ticket and scrambler
        )
