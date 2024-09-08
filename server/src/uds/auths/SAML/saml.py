# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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

from uds.core import auths, exceptions, types
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.ui import gui
from uds.core.util import security, decorators, auth as auth_utils, validators
from uds.core.util.model import sql_now

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from urllib.parse import ParseResult

    from uds.core.types.requests import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)


def CACHING_KEY_FNC(auth: 'SAMLAuthenticator') -> str:
    return auth.entity_id.as_str()


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

    private_key = gui.TextField(
        length=4096,
        lines=10,
        label=_('Private key'),
        order=1,
        tooltip=_('Private key used for sign and encription, as generated in base 64 from openssl'),
        required=True,
        tab=_('Certificates'),
        old_field_name='privateKey',
    )
    server_certificate = gui.TextField(
        length=4096,
        lines=10,
        label=_('Certificate'),
        order=2,
        tooltip=_('Server certificate used in SAML, as generated in base 64 from openssl'),
        required=True,
        tab=_('Certificates'),
        old_field_name='serverCertificate',
    )
    idp_metadata = gui.TextField(
        length=8192,
        lines=4,
        label=_('IDP Metadata'),
        order=3,
        tooltip=_('You can enter here the URL or the IDP metadata or the metadata itself (xml)'),
        required=True,
        tab=_('Metadata'),
        old_field_name='idpMetadata',
    )
    entity_id = gui.TextField(
        length=256,
        label=_('Entity ID'),
        order=4,
        tooltip=_('ID of the SP. If left blank, this will be autogenerated from server URL'),
        tab=_('Metadata'),
        old_field_name='entityID',
    )

    attrs_username = gui.TextField(
        length=2048,
        lines=2,
        label=_('User name attrs'),
        order=5,
        tooltip=_('Fields from where to extract user name'),
        required=True,
        tab=_('Attributes'),
        old_field_name='userNameAttr',
    )

    attrs_groupname = gui.TextField(
        length=2048,
        lines=2,
        label=_('Group name attrs'),
        order=6,
        tooltip=_('Fields from where to extract the groups'),
        required=True,
        tab=_('Attributes'),
        old_field_name='groupNameAttr',
    )

    attrs_realname = gui.TextField(
        length=2048,
        lines=2,
        label=_('Real name attrs'),
        order=7,
        tooltip=_('Fields from where to extract the real name'),
        required=True,
        tab=_('Attributes'),
        old_field_name='realNameAttr',
    )

    use_global_logout = gui.CheckBoxField(
        label=_('Global logout'),
        default=False,
        order=10,
        tooltip=_('If set, logout from UDS will trigger SAML logout'),
        tab=types.ui.Tab.ADVANCED,
        old_field_name='globalLogout',
    )

    adfs = gui.CheckBoxField(
        label=_('ADFS compatibility'),
        default=False,
        order=11,
        tooltip=_('If set, enable lowercase url encoding so ADFS can work correctly'),
        tab=types.ui.Tab.ADVANCED,
        old_field_name='adFS',
    )
    mfa_attr = gui.TextField(
        length=2048,
        lines=2,
        label=_('MFA attribute'),
        order=12,
        tooltip=_('Attribute from where to extract the MFA code'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='mfaAttr',
    )

    check_https_certificate = gui.CheckBoxField(
        label=_('Check SSL certificate'),
        default=False,  # For compatibility with previous versions
        order=23,
        tooltip=_('If set, check SSL certificate on requests for IDP Metadata'),
        tab=_('Security'),
        old_field_name='checkSSLCertificate',
    )

    use_name_id_encrypted = gui.CheckBoxField(
        label=_('Encripted nameID'),
        default=False,
        order=12,
        tooltip=_('If set, nameID will be encripted'),
        tab=_('Security'),
        old_field_name='nameIdEncrypted',
    )

    use_authn_requests_signed = gui.CheckBoxField(
        label=_('Authn requests signed'),
        default=False,
        order=13,
        tooltip=_('If set, authn requests will be signed'),
        tab=_('Security'),
        old_field_name='authnRequestsSigned',
    )

    logout_request_signed = gui.CheckBoxField(
        label=_('Logout requests signed'),
        default=False,
        order=14,
        tooltip=_('If set, logout requests will be signed'),
        tab=_('Security'),
        old_field_name='logoutRequestSigned',
    )

    use_signed_logout_response = gui.CheckBoxField(
        label=_('Logout responses signed'),
        default=False,
        order=15,
        tooltip=_('If set, logout responses will be signed'),
        tab=_('Security'),
        old_field_name='logoutResponseSigned',
    )

    use_signed_metadata = gui.CheckBoxField(
        label=_('Sign metadata'),
        default=False,
        order=16,
        tooltip=_('If set, metadata will be signed'),
        tab=_('Security'),
        old_field_name='signMetadata',
    )

    want_messages_signed = gui.CheckBoxField(
        label=_('Want messages signed'),
        default=False,
        order=17,
        tooltip=_('If set, messages will be signed'),
        tab=_('Security'),
        old_field_name='wantMessagesSigned',
    )

    want_assertions_signed = gui.CheckBoxField(
        label=_('Want assertions signed'),
        default=False,
        order=18,
        tooltip=_('If set, assertions will be signed'),
        tab=_('Security'),
        old_field_name='wantAssertionsSigned',
    )

    want_assertions_encrypted = gui.CheckBoxField(
        label=_('Want assertions encrypted'),
        default=False,
        order=19,
        tooltip=_('If set, assertions will be encrypted'),
        tab=_('Security'),
        old_field_name='wantAssertionsEncrypted',
    )

    want_name_id_encrypted = gui.CheckBoxField(
        label=_('Want nameID encrypted'),
        default=False,
        order=20,
        tooltip=_('If set, nameID will be encrypted'),
        tab=_('Security'),
        old_field_name='wantNameIdEncrypted',
    )

    use_requested_authn_context = gui.CheckBoxField(
        label=_('Requested authn context'),
        default=False,
        order=21,
        tooltip=_('If set, requested authn context will be sent'),
        tab=_('Security'),
        old_field_name='requestedAuthnContext',
    )

    allow_deprecated_signature_algorithms = gui.CheckBoxField(
        label=_('Allow deprecated signature algorithms'),
        default=True,
        order=23,
        tooltip=_('If set, deprecated signature algorithms will be allowed (as SHA1, MD5, etc...)'),
        tab=_('Security'),
        old_field_name='allowDeprecatedSignatureAlgorithms',
    )

    metadata_cache_duration = gui.NumericField(
        label=_('Metadata cache duration'),
        default=0,
        order=22,
        tooltip=_('Duration of metadata cache in days. 0 means default (ten years)'),
        tab=_('Metadata'),
        old_field_name='metadataCacheDuration',
    )

    metadata_validity_duration = gui.NumericField(
        label=_('Metadata validity duration'),
        default=0,
        order=22,
        tooltip=_('Duration of metadata validity in days. 0 means default (ten years)'),
        tab=_('Metadata'),
        old_field_name='metadataValidityDuration',
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

    manage_url = gui.HiddenField(serializable=True, old_field_name='manageUrl')

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
            raise exceptions.ui.ValidationError(
                gettext('This kind of Authenticator does not support white spaces on field NAME')
            )

        # Ensure ipdMetadata cache is empty, to regenerate it
        self.cache.remove('idpMetadata')

        # First, validate certificates
        validators.validate_private_key(self.private_key.value)
        validators.validate_certificate(self.server_certificate.value)

        if not security.check_certificate_matches_private_key(
            cert=self.server_certificate.value, key=self.private_key.value
        ):
            raise exceptions.ui.ValidationError(gettext('Certificate and private key do not match'))

        request: 'ExtendedHttpRequest' = values['_request']

        if self.entity_id.value == '':
            self.entity_id.value = request.build_absolute_uri(self.info_url())

        self.manage_url.value = request.build_absolute_uri(self.callback_url())

        idp_metadata: str = self.idp_metadata.value
        from_url: bool = False
        if idp_metadata.startswith('http://') or idp_metadata.startswith('https://'):
            logger.debug('idp Metadata is an URL: %s', idp_metadata)
            try:
                resp = requests.get(
                    idp_metadata.split('\n')[0],
                    verify=self.check_https_certificate.as_bool(),
                    timeout=10,
                )
                idp_metadata = resp.content.decode()
            except Exception as e:
                raise exceptions.ui.ValidationError(
                    gettext('Can\'t fetch url {url}: {error}').format(url=self.idp_metadata.value, error=str(e))
                )
            from_url = True

        # Try to parse it so we can check it is valid. Right now, it checks just that this is XML, will
        # correct it to check that is is valid idp metadata
        try:
            xml.sax.parseString(idp_metadata, xml.sax.ContentHandler())
        except Exception as e:
            msg = (gettext(' (obtained from URL)') if from_url else '') + str(e)
            raise exceptions.ui.ValidationError(gettext('XML does not seem valid for IDP Metadata ') + msg)

        # Now validate regular expressions, if they exists
        auth_utils.validate_regex_field(self.attrs_username)
        auth_utils.validate_regex_field(self.attrs_groupname)
        auth_utils.validate_regex_field(self.attrs_realname)

    def build_req_from_request(
        self,
        request: 'ExtendedHttpRequest',
        params: typing.Optional['types.auth.AuthCallbackParams'] = None,
    ) -> dict[str, typing.Any]:
        manage_url_obj = typing.cast('ParseResult', urlparse(self.manage_url.value))
        script_path: str = manage_url_obj.path
        host: str = manage_url_obj.netloc
        if ':' in host:
            host, port = host.split(':')
        else:
            if manage_url_obj.scheme == 'http':
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
                'lowercase_urlencoding': self.adfs.as_bool(),
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
            'lowercase_urlencoding': self.adfs.as_bool(),
            'query_string': request.META['QUERY_STRING'],
        }

    def get_idp_metadata_dict(self) -> dict[str, typing.Any]:
        if self.idp_metadata.value.startswith('http'):
            resp = self.cache.get('idpMetadata')
            if resp:
                return resp
            try:
                resp = requests.get(
                    self.idp_metadata.value.split('\n')[0],
                    verify=self.check_https_certificate.as_bool(),
                    timeout=10,
                )
                val = resp.content.decode()
                # 10 years, unless edited the metadata will be kept
                self.cache.put('idpMetadata', val, 86400 * 365 * 10)
            except Exception as e:
                logger.error('Error fetching idp metadata: %s', e)
                raise exceptions.auth.AuthenticatorException(gettext('Can\'t access idp metadata'))
        else:
            val = self.idp_metadata.value

        return OneLogin_Saml2_IdPMetadataParser.parse(val)  # pyright: ignore reportUnknownVariableType

    def build_onelogin_settings(self) -> dict[str, typing.Any]:
        return {
            'strict': True,
            'debug': True,
            'sp': {
                'entityId': self.entity_id.value,
                'assertionConsumerService': {
                    'url': self.manage_url.value,
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
                },
                'singleLogoutService': {
                    'url': self.manage_url.value + '?logout=true',
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
                },
                'x509cert': self.server_certificate.value,
                'privateKey': self.private_key.value,
                'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified',
            },
            'idp': self.get_idp_metadata_dict()['idp'],
            'security': {
                # in days, converted to seconds, this is a duration
                'metadataCacheDuration': (
                    self.metadata_cache_duration.as_int() * 86400
                    if self.metadata_cache_duration.value > 0
                    else 86400 * 365 * 10
                ),
                # This is a date of end of validity
                'metadataValidUntil': (
                    sql_now() + datetime.timedelta(days=self.metadata_validity_duration.as_int())
                    if self.metadata_cache_duration.value > 0
                    else sql_now() + datetime.timedelta(days=365 * 10)
                ),
                'nameIdEncrypted': self.use_name_id_encrypted.as_bool(),
                'authnRequestsSigned': self.use_authn_requests_signed.as_bool(),
                'logoutRequestSigned': self.logout_request_signed.as_bool(),
                'logoutResponseSigned': self.use_signed_logout_response.as_bool(),
                'signMetadata': self.use_signed_metadata.as_bool(),
                'wantMessagesSigned': self.want_messages_signed.as_bool(),
                'wantAssertionsSigned': self.want_assertions_signed.as_bool(),
                'wantAssertionsEncrypted': self.want_assertions_encrypted.as_bool(),
                'wantNameIdEncrypted': self.want_name_id_encrypted.as_bool(),
                'requestedAuthnContext': self.use_requested_authn_context.as_bool(),
                "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
                "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
                "rejectDeprecatedAlgorithm": not self.allow_deprecated_signature_algorithms.as_bool(),
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
        key_helper=CACHING_KEY_FNC,
        timeout=3600,  # 1 hour
    )
    def get_sp_metadata(self) -> str:
        saml_settings = OneLogin_Saml2_Settings(settings=self.build_onelogin_settings())
        metadata: typing.Any = saml_settings.get_sp_metadata()
        errors: list[typing.Any] = saml_settings.validate_metadata(  # pyright: ignore reportUnknownVariableType
            metadata
        )
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
        info = self.get_sp_metadata()
        wantsHtml = parameters.get('format') == 'html'

        content_type = 'text/html' if wantsHtml else 'application/samlmetadata+xml'
        info = (
            '<br/>'.join(info.replace('<', '&lt;').splitlines()) if parameters.get('format') == 'html' else info
        )
        return info, content_type  # 'application/samlmetadata+xml')

    def mfa_storage_key(self, username: str) -> str:
        return 'mfa_' + self.db_obj().uuid + username  # type: ignore

    def mfa_clean(self, username: str) -> None:
        self.storage.remove(self.mfa_storage_key(username))

    def mfa_identifier(self, username: str) -> str:
        return self.storage.read_pickled(self.mfa_storage_key(username)) or ''

    def logout_callback(
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

        logout_req_id = request.session.get('samlLogoutRequestId', None)

        # Cleanup session & session cookie
        request.session.flush()

        settings = OneLogin_Saml2_Settings(settings=self.build_onelogin_settings())
        auth = OneLogin_Saml2_Auth(req, settings)

        url: str = auth.process_slo(request_id=logout_req_id)  # pyright: ignore reportUnknownVariableType

        errors: list[str] = auth.get_errors()

        if errors:
            logger.debug(
                'Error on SLO: %s', auth.get_last_response_xml()  # pyright: ignore reportUnknownVariableType
            )
            logger.debug('post_data: %s', req['post_data'])
            logger.info('Errors processing logout request: %s', errors)
            raise exceptions.auth.AuthenticatorException(gettext('Error processing SLO: ') + str(errors))

        # Remove MFA related data
        if request.user:
            self.mfa_clean(request.user.name)

        return types.auth.AuthenticationResult(
            success=types.auth.AuthenticationState.REDIRECT,
            url=url or types.auth.AuthenticationInternalUrl.LOGIN.get_url(),
        )

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def auth_callback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        groups_manager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        req = self.build_req_from_request(request, params=parameters)

        if 'logout' in parameters.get_params:
            return self.logout_callback(req, typing.cast('ExtendedHttpRequestWithUser', request))

        try:
            settings = OneLogin_Saml2_Settings(settings=self.build_onelogin_settings())
            auth = OneLogin_Saml2_Auth(req, settings)
            auth.process_response()  # pyright: ignore reportUnknownVariableType
        except Exception as e:
            raise exceptions.auth.AuthenticatorException(gettext('Error processing SAML response: ') + str(e))
        errors: list[str] = auth.get_errors()
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

        attributes: dict[str, typing.Any] = (  # pyright: ignore reportUnknownVariableType
            auth.get_attributes().copy()  # pyright: ignore reportUnknownVariableType
        )
        # Append attributes by its friendly name
        attributes.update(auth.get_friendlyname_attributes())  # pyright: ignore reportUnknownVariableType

        if not attributes:
            raise exceptions.auth.AuthenticatorException(gettext('No attributes returned from IdP'))
        logger.debug("Attributes: %s", attributes)  # pyright: ignore reportUnknownVariableType

        # Now that we have attributes, we can extract values from this, map groups, etc...
        username = ''.join(
            auth_utils.process_regex_field(
                self.attrs_username.value, attributes  # pyright: ignore reportUnknownVariableType
            )
        )  # in case of multiple values is returned, join them
        logger.debug('Username: %s', username)

        groups = auth_utils.process_regex_field(
            self.attrs_groupname.value, attributes  # pyright: ignore reportUnknownVariableType
        )
        logger.debug('Groups: %s', groups)

        realName = ' '.join(
            auth_utils.process_regex_field(
                self.attrs_realname.value, attributes  # pyright: ignore reportUnknownVariableType
            )
        )
        logger.debug('Real name: %s', realName)

        # store groups for this username at storage, so we can check it at a later stage
        self.storage.save_pickled(username, [realName, groups])

        # store also the mfa identifier field value, in case we have provided it
        if self.mfa_attr.value.strip():
            self.storage.save_pickled(
                self.mfa_storage_key(username),
                ''.join(
                    auth_utils.process_regex_field(
                        self.mfa_attr.value, attributes  # pyright: ignore reportUnknownVariableType
                    )
                ),
            )  # in case multipel values is returned, join them
        else:
            self.storage.remove(self.mfa_storage_key(username))

        # Now we check validity of user

        groups_manager.validate(groups)

        return types.auth.AuthenticationResult(
            success=types.auth.AuthenticationState.SUCCESS, username=username
        )

    def logout(self, request: 'ExtendedHttpRequest', username: str) -> types.auth.AuthenticationResult:
        if not self.use_global_logout.as_bool():
            return types.auth.SUCCESS_AUTH

        req = self.build_req_from_request(request)

        settings = OneLogin_Saml2_Settings(settings=self.build_onelogin_settings())

        auth = OneLogin_Saml2_Auth(req, settings)

        saml = request.session.get('SAML', {})

        # Clear user data from session
        request.session.clear()

        # Remove MFA related data
        self.mfa_clean(username)

        if not saml:
            return types.auth.SUCCESS_AUTH

        return types.auth.AuthenticationResult(
            success=types.auth.AuthenticationState.REDIRECT,
            url=auth.logout(  # pyright: ignore reportUnknownVariableType
                name_id=saml.get('nameid'),
                session_index=saml.get('session_index'),
                nq=saml.get('nameid_namequalifier'),
                name_id_format=saml.get('nameid_format'),
                spnq=saml.get('nameid_spnamequalifier'),
            ),
        )

    def get_groups(self, username: str, groups_manager: 'auths.GroupsManager') -> None:
        data = self.storage.read_pickled(username)
        if not data:
            return
        groups_manager.validate(data[1])

    def get_real_name(self, username: str) -> str:
        data = self.storage.read_pickled(username)
        if not data:
            return username
        return data[0]

    def get_javascript(self, request: 'ExtendedHttpRequest') -> typing.Optional[str]:
        """
        We will here compose the saml request and send it via http-redirect
        """
        req = self.build_req_from_request(request)
        auth = OneLogin_Saml2_Auth(req, self.build_onelogin_settings())

        return f'window.location="{auth.login()}";'  # pyright: ignore reportUnknownVariableType

    def remove_user(self, username: str) -> None:
        """
        Clean ups storage data
        """
        self.storage.remove(username)
        self.mfa_clean(username)
