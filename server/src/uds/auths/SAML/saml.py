# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import datetime
import logging
import re
import typing
import collections.abc
import xml.sax  # nosec: used to parse trusted xml provided only by administrators
from urllib.parse import urlparse

import requests
from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from uds.core import auths, exceptions, types, consts
from uds.core.managers.crypto import CryptoManager
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.ui import gui
from uds.core.util import security, decorators, ensure, auth as auth_utils
from uds.core.util.model import sql_datetime

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import HttpRequest

    from uds.core.types.requests import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)


def CACHING_KEY_FNC(auth: 'SAMLAuthenticator') -> str:
    return str(hash(auth.idpMetadata.value))


class SAMLAuthenticator(auths.Authenticator):
    """
    This class represents the SAML Authenticator
    """

    # : Name of type, used at administration interface to identify this
    # : authenticator (i.e. LDAP, SAML, ...)
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_name = _('SAML Authenticator')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    type_type = 'SAML20Authenticator'

    # : Description shown at administration level for this authenticator.
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_description = _('SAML (v2.0) Authenticator')

    # : Icon file, used to represent this authenticator at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    icon_file = 'auth.png'

    # : Mark this authenticator as that the users comes from outside the UDS
    # : database, that are most authenticator (except Internal DB)
    # : True is the default value, so we do not need it in fact

    # : If we need to enter the password for this user when creating a new
    # : user at administration interface. Used basically by internal authenticator.
    # : False is the default value, so this is not needed in fact
    # : needs_password = False

    # : Label for username field, shown at administration interface user form.
    label_username = _('User')

    # Label for group field, shown at administration interface user form.
    label_groupname = _('Group')

    # : Definition of this type of authenticator form
    # : We will define a simple form where we will use a simple
    # : list editor to allow entering a few group names

    privateKey = gui.TextField(
        length=4096,
        lines=10,
        label=_('Private key'),
        order=1,
        tooltip=_('Private key used for sign and encription, as generated in base 64 from openssl'),
        required=True,
        tab=_('Certificates'),
    )
    serverCertificate = gui.TextField(
        length=4096,
        lines=10,
        label=_('Certificate'),
        order=2,
        tooltip=_(
            'Public key used for sign and encription (public part of previous private key), as generated in base 64 from openssl'
        ),
        required=True,
        tab=_('Certificates'),
    )
    idpMetadata = gui.TextField(
        length=8192,
        lines=4,
        label=_('IDP Metadata'),
        order=3,
        tooltip=_('You can enter here the URL or the IDP metadata or the metadata itself (xml)'),
        required=True,
        tab=_('Metadata'),
    )
    entityID = gui.TextField(
        length=256,
        label=_('Entity ID'),
        order=4,
        tooltip=_('ID of the SP. If left blank, this will be autogenerated from server URL'),
        tab=_('Metadata'),
    )

    userNameAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('User name attrs'),
        order=5,
        tooltip=_('Fields from where to extract user name'),
        required=True,
        tab=_('Attributes'),
    )

    groupNameAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('Group name attrs'),
        order=6,
        tooltip=_('Fields from where to extract the groups'),
        required=True,
        tab=_('Attributes'),
    )

    realNameAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('Real name attrs'),
        order=7,
        tooltip=_('Fields from where to extract the real name'),
        required=True,
        tab=_('Attributes'),
    )

    globalLogout = gui.CheckBoxField(
        label=_('Global logout'),
        default=False,
        order=10,
        tooltip=_('If set, logout from UDS will trigger SAML logout'),
        tab=types.ui.Tab.ADVANCED,
    )

    adFS = gui.CheckBoxField(
        label=_('ADFS compatibility'),
        default=False,
        order=11,
        tooltip=_('If set, enable lowercase url encoding so ADFS can work correctly'),
        tab=types.ui.Tab.ADVANCED,
    )
    mfaAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('MFA attribute'),
        order=12,
        tooltip=_('Attribute from where to extract the MFA code'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )

    checkSSLCertificate = gui.CheckBoxField(
        label=_('Check SSL certificate'),
        default=False,  # For compatibility with previous versions
        order=23,
        tooltip=_('If set, check SSL certificate on requests for IDP Metadata'),
        tab=_('Security'),
    )

    nameIdEncrypted = gui.CheckBoxField(
        label=_('Encripted nameID'),
        default=False,
        order=12,
        tooltip=_('If set, nameID will be encripted'),
        tab=_('Security'),
    )

    authnRequestsSigned = gui.CheckBoxField(
        label=_('Authn requests signed'),
        default=False,
        order=13,
        tooltip=_('If set, authn requests will be signed'),
        tab=_('Security'),
    )

    logoutRequestSigned = gui.CheckBoxField(
        label=_('Logout requests signed'),
        default=False,
        order=14,
        tooltip=_('If set, logout requests will be signed'),
        tab=_('Security'),
    )

    logoutResponseSigned = gui.CheckBoxField(
        label=_('Logout responses signed'),
        default=False,
        order=15,
        tooltip=_('If set, logout responses will be signed'),
        tab=_('Security'),
    )

    signMetadata = gui.CheckBoxField(
        label=_('Sign metadata'),
        default=False,
        order=16,
        tooltip=_('If set, metadata will be signed'),
        tab=_('Security'),
    )

    wantMessagesSigned = gui.CheckBoxField(
        label=_('Want messages signed'),
        default=False,
        order=17,
        tooltip=_('If set, messages will be signed'),
        tab=_('Security'),
    )

    wantAssertionsSigned = gui.CheckBoxField(
        label=_('Want assertions signed'),
        default=False,
        order=18,
        tooltip=_('If set, assertions will be signed'),
        tab=_('Security'),
    )

    wantAssertionsEncrypted = gui.CheckBoxField(
        label=_('Want assertions encrypted'),
        default=False,
        order=19,
        tooltip=_('If set, assertions will be encrypted'),
        tab=_('Security'),
    )

    wantNameIdEncrypted = gui.CheckBoxField(
        label=_('Want nameID encrypted'),
        default=False,
        order=20,
        tooltip=_('If set, nameID will be encrypted'),
        tab=_('Security'),
    )

    requestedAuthnContext = gui.CheckBoxField(
        label=_('Requested authn context'),
        default=False,
        order=21,
        tooltip=_('If set, requested authn context will be sent'),
        tab=_('Security'),
    )

    allowDeprecatedSignatureAlgorithms = gui.CheckBoxField(
        label=_('Allow deprecated signature algorithms'),
        default=True,
        order=23,
        tooltip=_('If set, deprecated signature algorithms will be allowed (as SHA1, MD5, etc...)'),
        tab=_('Security'),
    )

    metadataCacheDuration = gui.NumericField(
        label=_('Metadata cache duration'),
        default=0,
        order=22,
        tooltip=_('Duration of metadata cache in days. 0 means default (ten years)'),
        tab=_('Metadata'),
    )

    metadataValidityDuration = gui.NumericField(
        label=_('Metadata validity duration'),
        default=0,
        order=22,
        tooltip=_('Duration of metadata validity in days. 0 means default (ten years)'),
        tab=_('Metadata'),
    )
    
    organization_name = gui.TextField(
        length=256,
        label=_('Organization Name'),
        default='UDS',
        order=40,
        tooltip=_('Organization name to use on SAML SP Metadata'),
        tab=_('Organization'),
    )
    
    organization_display_name = gui.TextField(
        length=256,
        label=_('Organization Display Name'),
        default='UDS Organization',
        order=41,
        tooltip=_('Organization Display name to use on SAML SP Metadata'),
        tab=_('Organization'),
    )
    
    organization_url = gui.TextField(
        length=256,
        label=_('Organization URL'),
        default='https://www.udsenterprise.com',
        order=42,
        tooltip=_('Organization url to use on SAML SP Metadata'),
        tab=_('Organization'),
    )
    
    manageUrl = gui.HiddenField(serializable=True)

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        """
        Simply check if we have
        at least one group in the list
        """
        # To avoid problems, we only check data if values are passed
        # If values are not passed in, form data will only be available after
        # unserialization, and at this point all will be default values
        # so self.groups.value will be []
        if values is None:
            return

        if ' ' in values['name']:
            raise exceptions.validation.ValidationError(
                gettext('This kind of Authenticator does not support white spaces on field NAME')
            )

        # First, validate certificates
        self.cache.remove('idpMetadata')

        # This is in fact not needed, but we may say something useful to user if we check this
        if self.serverCertificate.value.startswith('-----BEGIN CERTIFICATE-----\n') is False:
            raise exceptions.validation.ValidationError(
                gettext(
                    'Server certificate should be a valid PEM (PEM certificates starts with -----BEGIN CERTIFICATE-----)'
                )
            )

        try:
            CryptoManager().load_certificate(self.serverCertificate.value)
        except Exception as e:
            raise exceptions.validation.ValidationError(gettext('Invalid server certificate. ') + str(e))

        if (
            self.privateKey.value.startswith('-----BEGIN RSA PRIVATE KEY-----\n') is False
            and self.privateKey.value.startswith('-----BEGIN PRIVATE KEY-----\n') is False
        ):
            raise exceptions.validation.ValidationError(
                gettext(
                    'Private key should be a valid PEM (PEM private keys starts with -----BEGIN RSA PRIVATE KEY-----'
                )
            )

        try:
            CryptoManager().load_private_key(self.privateKey.value)
        except Exception as e:
            raise exceptions.validation.ValidationError(gettext('Invalid private key. ') + str(e))

        if not security.check_certificate_matches_private_key(
            cert=self.serverCertificate.value, key=self.privateKey.value
        ):
            raise exceptions.validation.ValidationError(gettext('Certificate and private key do not match'))

        request: 'ExtendedHttpRequest' = values['_request']

        if self.entityID.value == '':
            self.entityID.value = request.build_absolute_uri(self.info_url())

        self.manageUrl.value = request.build_absolute_uri(self.callback_url())

        idpMetadata: str = self.idpMetadata.value
        fromUrl: bool = False
        if idpMetadata.startswith('http://') or idpMetadata.startswith('https://'):
            logger.debug('idp Metadata is an URL: %s', idpMetadata)
            try:
                resp = requests.get(
                    idpMetadata.split('\n')[0],
                    verify=self.checkSSLCertificate.as_bool(),
                    timeout=10,
                )
                idpMetadata = resp.content.decode()
            except Exception as e:
                raise exceptions.validation.ValidationError(
                    gettext('Can\'t fetch url {0}: {1}').format(self.idpMetadata.value, str(e))
                )
            fromUrl = True

        # Try to parse it so we can check it is valid. Right now, it checks just that this is XML, will
        # correct it to check that is is valid idp metadata
        try:
            xml.sax.parseString(idpMetadata, xml.sax.ContentHandler())  # type: ignore  # nosec: url provided by admin
        except Exception as e:
            msg = (gettext(' (obtained from URL)') if fromUrl else '') + str(e)
            raise exceptions.validation.ValidationError(gettext('XML does not seem valid for IDP Metadata ') + msg)

        # Now validate regular expressions, if they exists
        auth_utils.validateRegexField(self.userNameAttr)
        auth_utils.validateRegexField(self.groupNameAttr)
        auth_utils.validateRegexField(self.realNameAttr)

    def getReqFromRequest(
        self,
        request: 'ExtendedHttpRequest',
        params: typing.Optional['types.auth.AuthCallbackParams'] = None,
    ) -> dict[str, typing.Any]:
        manageUrlObj = urlparse(self.manageUrl.value)
        script_path = manageUrlObj.path
        host = manageUrlObj.netloc
        if ':' in host:
            host, port = host.split(':')
        else:
            if manageUrlObj.scheme == 'http':
                port = '80'
            else:
                port = '443'

        # If callback parameters are passed, we use them
        if params:
            # Remove next 3 lines, just for testing and debugging
            return {
                'https': ['off', 'on'][params.https],
                'http_host': host,  # params['http_host'],
                'script_name': script_path,  # params['path_info'],
                'server_port': port,  # params['server_port'],
                'get_data': params.get_params.copy(),
                'post_data': params.post_params.copy(),
                'lowercase_urlencoding': self.adFS.as_bool(),
                'query_string': params.query_string,
            }
        # No callback parameters, we use the request
        return {
            'https': 'on' if request.is_secure() else 'off',
            'http_host': host,  # request.META['HTTP_HOST'],
            'script_name': script_path,  # request.META['PATH_INFO'],
            'server_port': port,  # request.META['SERVER_PORT'],
            'get_data': request.GET.copy(),
            'post_data': request.POST.copy(),
            'lowercase_urlencoding': self.adFS.as_bool(),
            'query_string': request.META['QUERY_STRING'],
        }

    @decorators.cached(
        prefix='idpm',
        key_fnc=CACHING_KEY_FNC,
        timeout=3600 * 24 * 365,  # 1 year
    )
    def getIdpMetadataDict(self) -> dict[str, typing.Any]:
        if self.idpMetadata.value.startswith('http'):
            try:
                resp = requests.get(
                    self.idpMetadata.value.split('\n')[0],
                    verify=self.checkSSLCertificate.as_bool(),
                    timeout=10,
                )
                val = resp.content.decode()
            except Exception as e:
                logger.error('Error fetching idp metadata: %s', e)
                raise exceptions.auth.AuthenticatorException(gettext('Can\'t access idp metadata'))
        else:
            val = self.idpMetadata.value

        return OneLogin_Saml2_IdPMetadataParser.parse(val)

    def oneLoginSettings(self) -> dict[str, typing.Any]:
        return {
            'strict': True,
            'debug': True,
            'sp': {
                'entityId': self.entityID.value,
                'assertionConsumerService': {
                    'url': self.manageUrl.value,
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
                },
                'singleLogoutService': {
                    'url': self.manageUrl.value + '?logout=true',
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
                },
                'x509cert': self.serverCertificate.value,
                'privateKey': self.privateKey.value,
                'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified',
            },
            'idp': self.getIdpMetadataDict()['idp'],
            'security': {
                'metadataCacheDuration': self.metadataCacheDuration.int_value
                if self.metadataCacheDuration.int_value > 0
                else 86400 * 365 * 10,
                'metadataValidUntil': sql_datetime()
                + datetime.timedelta(seconds=self.metadataValidityDuration.int_value)
                if self.metadataCacheDuration.int_value > 0
                else sql_datetime() + datetime.timedelta(days=365 * 10),
                'nameIdEncrypted': self.nameIdEncrypted.as_bool(),
                'authnRequestsSigned': self.authnRequestsSigned.as_bool(),
                'logoutRequestSigned': self.logoutRequestSigned.as_bool(),
                'logoutResponseSigned': self.logoutResponseSigned.as_bool(),
                'signMetadata': self.signMetadata.as_bool(),
                'wantMessagesSigned': self.wantMessagesSigned.as_bool(),
                'wantAssertionsSigned': self.wantAssertionsSigned.as_bool(),
                'wantAssertionsEncrypted': self.wantAssertionsEncrypted.as_bool(),
                'wantNameIdEncrypted': self.wantNameIdEncrypted.as_bool(),
                'requestedAuthnContext': self.requestedAuthnContext.as_bool(),
                "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
                "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
                "rejectDeprecatedAlgorithm": not self.allowDeprecatedSignatureAlgorithms.as_bool(),
            },
            'organization': {
                'en-US': {
                    'name': self.organization_name.as_str(),
                    'displayname': self.organization_display_name.as_str(),
                    'url': self.organization_url.as_str(),
                },
            },
        }

    @decorators.cached(
        prefix='spm',
        key_fnc=CACHING_KEY_FNC,
        timeout=3600,  # 1 hour
    )
    def getSpMetadata(self) -> str:
        saml_settings = OneLogin_Saml2_Settings(settings=self.oneLoginSettings())
        metadata = saml_settings.get_sp_metadata()
        errors = saml_settings.validate_metadata(metadata)
        if len(errors) > 0:
            raise exceptions.auth.AuthenticatorException(
                gettext('Error validating SP metadata: ') + str(errors)
            )
        if isinstance(metadata, str):
            return metadata
        return typing.cast(bytes, metadata).decode()


    def get_info(
        self, parameters: collections.abc.Mapping[str, str]
    ) -> typing.Optional[tuple[str, typing.Optional[str]]]:
        """
        Althought this is mainly a get info callback, this can be used for any other purpuse we like.
        In this case, we use it to provide logout callback also
        """
        info = self.getSpMetadata()
        wantsHtml = parameters.get('format') == 'html'

        content_type = 'text/html' if wantsHtml else 'application/samlmetadata+xml'
        info = (
            '<br/>'.join(info.replace('<', '&lt;').splitlines()) if parameters.get('format') == 'html' else info
        )
        return info, content_type  # 'application/samlmetadata+xml')

    def mfaStorageKey(self, username: str) -> str:
        return 'mfa_' + self.db_obj().uuid + username  # type: ignore

    def mfaClean(self, username: str):
        self.storage.remove(self.mfaStorageKey(username))

    def mfa_identifier(self, username: str) -> str:
        return self.storage.get_unpickle(self.mfaStorageKey(username)) or ''

    def logoutFromCallback(
        self,
        req: dict[str, typing.Any],
        request: 'ExtendedHttpRequestWithUser',
    ) -> types.auth.AuthenticationResult:
        # Convert HTTP-POST to HTTP-REDIRECT on SAMLResponse, for just in case...
        if 'SAMLResponse' in req['post_data']:
            if isinstance(req['post_data']['SAMLResponse'], list):
                req['get_data']['SAMLResponse'] = req['post_data']['SAMLResponse'][0]
            else:
                req['get_data']['SAMLResponse'] = req['post_data']['SAMLResponse']

        logoutRequestId = request.session.get('samlLogoutRequestId', None)

        # Cleanup session & session cookie
        request.session.flush()

        settings = OneLogin_Saml2_Settings(settings=self.oneLoginSettings())
        auth = OneLogin_Saml2_Auth(req, settings)

        url = auth.process_slo(request_id=logoutRequestId)

        errors = auth.get_errors()

        if errors:
            logger.debug('Error on SLO: %s', auth.get_last_response_xml())
            logger.debug('post_data: %s', req['post_data'])
            logger.info('Errors processing logout request: %s', errors)
            raise exceptions.auth.AuthenticatorException(gettext('Error processing SLO: ') + str(errors))

        # Remove MFA related data
        if request.user:
            self.mfaClean(request.user.name)

        return types.auth.AuthenticationResult(
            success=types.auth.AuthenticationState.REDIRECT,
            url=url or types.auth.AuthenticationInternalUrl.LOGIN.get_url(),
        )

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def auth_callback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'ExtendedHttpRequestWithUser',
    ) -> types.auth.AuthenticationResult:
        req = self.getReqFromRequest(request, params=parameters)

        if 'logout' in parameters.get_params:
            return self.logoutFromCallback(req, request)

        try:
            settings = OneLogin_Saml2_Settings(settings=self.oneLoginSettings())
            auth = OneLogin_Saml2_Auth(req, settings)
            auth.process_response()
        except Exception as e:
            raise exceptions.auth.AuthenticatorException(gettext('Error processing SAML response: ') + str(e))
        errors = auth.get_errors()
        if errors:
            raise exceptions.auth.AuthenticatorException('SAML response error: ' + str(errors))

        if not auth.is_authenticated():
            raise exceptions.auth.AuthenticatorException(gettext('SAML response not authenticated'))

        # Store SAML attributes
        request.session['SAML'] = {
            'nameid': auth.get_nameid(),
            'nameid_format': auth.get_nameid_format(),
            'nameid_namequalifier': auth.get_nameid_nq(),
            'nameid_spnamequalifier': auth.get_nameid_spnq(),
            'session_index': auth.get_session_index(),
            'session_expiration': auth.get_session_expiration(),
        }

        # In our case, we ignore relay state, because we do not use it (we redirect ourselves).
        # It will contain the originating request to javascript
        # if (
        #     'RelayState' in req['post_data']
        #     and OneLogin_Saml2_Utils.get_self_url(req) != req['post_data']['RelayState']
        # ):
        #     return types.auth.AuthenticationResult(
        #         success=auths.AuthenticationSuccess.REDIRECT,
        #         url=auth.redirect_to(req['post_data']['RelayState'])
        #     )

        attributes = auth.get_attributes().copy()
        # Append attributes by its friendly name
        attributes.update(auth.get_friendlyname_attributes())

        if not attributes:
            raise exceptions.auth.AuthenticatorException(gettext('No attributes returned from IdP'))
        logger.debug("Attributes: %s", attributes)

        # Now that we have attributes, we can extract values from this, map groups, etc...
        username = ''.join(
            auth_utils.processRegexField(self.userNameAttr.value, attributes)
        )  # in case of multiple values is returned, join them
        logger.debug('Username: %s', username)

        groups = auth_utils.processRegexField(self.groupNameAttr.value, attributes)
        logger.debug('Groups: %s', groups)

        realName = ' '.join(auth_utils.processRegexField(self.realNameAttr.value, attributes))
        logger.debug('Real name: %s', realName)

        # store groups for this username at storage, so we can check it at a later stage
        self.storage.put_pickle(username, [realName, groups])

        # store also the mfa identifier field value, in case we have provided it
        if self.mfaAttr.value.strip():
            self.storage.put_pickle(
                self.mfaStorageKey(username),
                ''.join(auth_utils.processRegexField(self.mfaAttr.value, attributes)),
            )  # in case multipel values is returned, join them
        else:
            self.storage.remove(self.mfaStorageKey(username))

        # Now we check validity of user

        gm.validate(groups)

        return types.auth.AuthenticationResult(success=types.auth.AuthenticationState.SUCCESS, username=username)

    def logout(self, request: 'ExtendedHttpRequest', username: str) -> types.auth.AuthenticationResult:
        if not self.globalLogout.as_bool():
            return types.auth.SUCCESS_AUTH

        req = self.getReqFromRequest(request)

        settings = OneLogin_Saml2_Settings(settings=self.oneLoginSettings())

        auth = OneLogin_Saml2_Auth(req, settings)

        saml = request.session.get('SAML', {})

        # Clear user data from session
        request.session.clear()

        # Remove MFA related data
        self.mfaClean(username)

        if not saml:
            return types.auth.SUCCESS_AUTH

        return types.auth.AuthenticationResult(
            success=types.auth.AuthenticationState.REDIRECT,
            url=auth.logout(
                name_id=saml.get('nameid'),
                session_index=saml.get('session_index'),
                nq=saml.get('nameid_namequalifier'),
                name_id_format=saml.get('nameid_format'),
                spnq=saml.get('nameid_spnamequalifier'),
            ),
        )

    def get_groups(self, username: str, groupsManager: 'auths.GroupsManager'):
        data = self.storage.get_unpickle(username)
        if not data:
            return
        groupsManager.validate(data[1])

    def get_real_name(self, username: str) -> str:
        data = self.storage.get_unpickle(username)
        if not data:
            return username
        return data[0]

    def get_javascript(self, request: 'ExtendedHttpRequest') -> typing.Optional[str]:
        """
        We will here compose the saml request and send it via http-redirect
        """
        req = self.getReqFromRequest(request)
        auth = OneLogin_Saml2_Auth(req, self.oneLoginSettings())

        return f'window.location="{auth.login()}";'

    def remove_user(self, username):
        """
        Clean ups storage data
        """
        self.storage.remove(username)
        self.storage.remove('lasso-' + username)
