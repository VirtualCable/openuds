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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import re
import time
import datetime
import xml.sax
import requests
import logging
import typing

import lasso

from django.utils.translation import gettext_noop as _, gettext
from uds.core.ui import gui
from uds.core import auths
from uds.core.util.config import Config
from uds.core.managers import cryptoManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import HttpRequest
    from uds.core.util.request import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)

SAML_REQUEST_ID = 'saml2RequestId'


def iso8601_to_datetime(date_string: str) -> datetime.datetime:
    """
    Convert a string formatted as an ISO8601 date into a time_t value.
       This function ignores the sub-second resolution
    """
    m = re.match(r'(\d+-\d+-\d+T\d+:\d+:\d+)(?:\.\d+)?Z$', date_string)

    if not m:
        raise ValueError('Invalid ISO8601 date')

    tm = time.strptime(m.group(1) + 'Z', "%Y-%m-%dT%H:%M:%SZ")

    return datetime.datetime.fromtimestamp(time.mktime(tm))


class SAMLAuthenticator(auths.Authenticator):
    """
    This class represents the SAML Authenticator
    """

    # : Name of type, used at administration interface to identify this
    # : authenticator (i.e. LDAP, SAML, ...)
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    typeName = _('SAML Authenticator')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    typeType = 'SAML20Authenticator'

    # : Description shown at administration level for this authenticator.
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    typeDescription = _('SAML (v2.0) Authenticator')

    # : Icon file, used to represent this authenticator at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    iconFile = 'auth.png'

    # : Mark this authenticator as that the users comes from outside the UDS
    # : database, that are most authenticator (except Internal DB)
    # : True is the default value, so we do not need it in fact
    # isExternalSource = True

    # : If we need to enter the password for this user when creating a new
    # : user at administration interface. Used basically by internal authenticator.
    # : False is the default value, so this is not needed in fact
    # : needsPassword = False

    # : Label for username field, shown at administration interface user form.
    userNameLabel = _('User')

    # Label for group field, shown at administration interface user form.
    groupNameLabel = _('Group')

    # : Definition of this type of authenticator form
    # : We will define a simple form where we will use a simple
    # : list editor to allow entering a few group names

    privateKey = gui.TextField(
        length=4096,
        multiline=10,
        label=_('Private key'),
        order=1,
        tooltip=_(
            'Private key used for sign and encription, as generated in base 64 from openssl'
        ),
        required=True,
        tab=_('Certificates'),
    )
    serverCertificate = gui.TextField(
        length=4096,
        multiline=10,
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
        multiline=4,
        label=_('IDP Metadata'),
        order=3,
        tooltip=_(
            'You can enter here the URL or the IDP metadata or the metadata itself (xml)'
        ),
        required=True,
        tab=_('Metadata'),
    )
    entityID = gui.TextField(
        length=256,
        label=_('Entity ID'),
        order=4,
        tooltip=_(
            'ID of the SP. If left blank, this will be autogenerated from server URL'
        ),
        tab=_('Metadata'),
    )

    userNameAttr = gui.TextField(
        length=2048,
        multiline=2,
        label=_('User name attrs'),
        order=5,
        tooltip=_('Fields from where to extract user name'),
        required=True,
        tab=_('Attributes'),
    )

    groupNameAttr = gui.TextField(
        length=2048,
        multiline=2,
        label=_('Group name attrs'),
        order=6,
        tooltip=_('Fields from where to extract the groups'),
        required=True,
        tab=_('Attributes'),
    )

    realNameAttr = gui.TextField(
        length=2048,
        multiline=2,
        label=_('Real name attrs'),
        order=7,
        tooltip=_('Fields from where to extract the real name'),
        required=True,
        tab=_('Attributes'),
    )

    manageUrl = gui.HiddenField(serializable=True)

    def initialize(self, values: typing.Optional[typing.Dict[str, typing.Any]]) -> None:
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
            raise auths.Authenticator.ValidationException(
                gettext(
                    'This kind of Authenticator does not support white spaces on field NAME'
                )
            )

        # First, validate certificates
        self.cache.remove('idpMetadata')

        # This is in fact not needed, but we may say something useful to user if we check this
        if (
            self.serverCertificate.value.startswith('-----BEGIN CERTIFICATE-----\n')
            is False
        ):
            raise auths.Authenticator.ValidationException(
                gettext(
                    'Server certificate should be a valid PEM (PEM certificates starts with -----BEGIN CERTIFICATE-----)'
                )
            )

        try:
            cryptoManager().loadCertificate(self.serverCertificate.value)
        except Exception as e:
            raise auths.Authenticator.ValidationException(
                gettext('Invalid server certificate. ') + str(e)
            )

        if (
            self.privateKey.value.startswith('-----BEGIN RSA PRIVATE KEY-----\n')
            is False
            and self.privateKey.value.startswith('-----BEGIN PRIVATE KEY-----\n')
            is False
        ):
            raise auths.Authenticator.ValidationException(
                gettext(
                    'Private key should be a valid PEM (PEM private keys starts with -----BEGIN RSA PRIVATE KEY-----'
                )
            )

        try:
            pk = cryptoManager().loadPrivateKey(self.privateKey.value)
        except Exception as e:
            raise auths.Authenticator.ValidationException(
                gettext('Invalid private key. ') + str(e)
            )

        request = values['_request']

        if self.entityID.value == '':
            self.entityID.value = request.build_absolute_uri(self.infoUrl())

        self.manageUrl.value = request.build_absolute_uri(self.callbackUrl())

        idpMetadata: str = self.idpMetadata.value
        fromUrl: bool = False
        if idpMetadata.startswith('http://') or idpMetadata.startswith('https://'):
            logger.debug('idp Metadata is an URL: %s', idpMetadata)
            try:
                resp = requests.get(idpMetadata.split('\n')[0], verify=False)
                idpMetadata = resp.content.decode()
            except Exception as e:
                raise auths.Authenticator.ValidationException(
                    gettext('Can\'t fetch url {0}: {1}').format(
                        self.idpMetadata.value, str(e)
                    )
                )
            fromUrl = True

        # Try to parse it so we can check it is valid. Right now, it checks just that this is XML, will
        # correct it to check that is is valid idp metadata
        try:
            xml.sax.parseString(idpMetadata, xml.sax.ContentHandler())  # type: ignore
        except Exception as e:
            msg = (gettext(' (obtained from URL)') if fromUrl else '') + str(e)
            raise auths.Authenticator.ValidationException(
                gettext('XML does not seem valid for IDP Metadata ') + msg
            )

        # Now validate regular expressions, if they exists
        self.__validateField(self.userNameAttr)
        self.__validateField(self.groupNameAttr)
        self.__validateField(self.realNameAttr)

    def __idpMetadata(self, force=False):
        if self.idpMetadata.value.startswith(
            'http://'
        ) or self.idpMetadata.value.startswith('https://'):
            val = self.cache.get('idpMetadata')
            if val is None or force:
                try:
                    resp = requests.get(
                        self.idpMetadata.value.split('\n')[0], verify=False
                    )
                    val = resp.content.decode()
                except Exception as e:
                    logger.error('Error fetching idp metadata: %s', e)
                    raise auths.exceptions.AuthenticatorException(
                        gettext('Can\'t access idp metadata')
                    )
                self.cache.put(
                    'idpMetadata',
                    val,
                    Config.section('SAML').value('IDP Metadata cache').getInt(True),
                )
        else:
            val = self.idpMetadata.value
        return val

    def __spMetadata(self):
        return '''<?xml version="1.0"?>
              <md:EntityDescriptor
                xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
                entityID="{0}">
                <md:SPSSODescriptor
                    AuthnRequestsSigned="true"
                    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
                  <md:KeyDescriptor use="signing">
                    <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                      <ds:X509Data>
                        <ds:X509Certificate>{1}</ds:X509Certificate>
                      </ds:X509Data>
                    </ds:KeyInfo>
                  </md:KeyDescriptor>
                  <md:KeyDescriptor use="encryption">
                    <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                      <ds:X509Data>
                        <ds:X509Certificate>{1}</ds:X509Certificate>
                      </ds:X509Data>
                    </ds:KeyInfo>
                  </md:KeyDescriptor>
                  <md:SingleLogoutService
                    Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                    Location="{2}?logout=true"/>
                  <md:AssertionConsumerService isDefault="true" index="0"
                    Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                    Location="{2}" />
                </md:SPSSODescriptor>
                <md:Organization>
                   <md:OrganizationName xml:lang="en">{3}</md:OrganizationName>
                   <md:OrganizationDisplayName xml:lang="en">{4}</md:OrganizationDisplayName>
                   <md:OrganizationURL xml:lang="en">{5}</md:OrganizationURL>
                </md:Organization>
              </md:EntityDescriptor>
              '''.format(
            self.entityID.value,
            cryptoManager().certificateString(self.serverCertificate.value),
            self.manageUrl.value,
            Config.section('SAML').value('Organization Name').get(True),
            Config.section('SAML').value('Org. Display Name').get(True),
            Config.section('SAML').value('Organization URL').get(True),
        )

    def __createServer(self) -> lasso.Server:
        # Create server for this SP
        server: typing.Optional[lasso.Server] = lasso.Server.newFromBuffers(
            self.__spMetadata(), self.privateKey.value
        )
        if not server:
            raise auths.exceptions.AuthenticatorException('Can\'t create lasso server')

        # Now add provider
        # logger.debug('Types: %s', self.__idpMetadata())
        server.addProviderFromBuffer(lasso.PROVIDER_ROLE_IDP, self.__idpMetadata())
        server.signatureMethod = lasso.SIGNATURE_METHOD_RSA_SHA256

        return server

    def __validateField(self, field: gui.TextField):
        """
        Validates the multi line fields refering to attributes
        """
        value: str = field.value
        for line in value.splitlines():
            if line.find('=') != -1:
                pattern = line.split('=')[0:2][1]
                if pattern.find('(') == -1:
                    pattern = '(' + pattern + ')'
                try:
                    re.search(pattern, '')
                except:
                    raise auths.Authenticator.ValidationException(
                        'Invalid pattern at {0}: {1}'.format(field.label, line)
                    )

    def __processField(
        self, field: str, attributes: typing.Dict[str, typing.List]
    ) -> typing.List[str]:
        res = []
        for line in field.splitlines():
            equalPos = line.find('=')
            if equalPos != -1:
                attr, pattern = (line[:equalPos], line[equalPos + 1 :])
                # if pattern do not have groups, define one with full re
                if pattern.find('(') == -1:
                    pattern = '(' + pattern + ')'
                val = attributes.get(attr, [])

                for v in val:
                    try:
                        logger.debug('Pattern: %s', pattern)
                        srch = re.search(pattern, v)
                        if srch is None:
                            continue
                        res.append(''.join(srch.groups()))
                    except Exception as e:
                        logger.warning('Invalid regular expression')
                        logger.debug(e)
                        break
            else:
                res += attributes.get(line, [])
        return res

    def getInfo(
        self, parameters: typing.Mapping[str, str]
    ) -> typing.Optional[typing.Tuple[str, typing.Optional[str]]]:
        """
        Althought this is mainly a get info callback, this can be used for any other purpuse we like.
        In this case, we use it to provide logout callback also
        """
        info = self.__spMetadata()

        content_type = (
            'text/html'
            if parameters.get('format', '') == 'html'
            else 'application/samlmetadata+xml'
        )
        return info, content_type  # 'application/samlmetadata+xml')

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def authCallback(
        self,
        parameters: typing.Dict[str, typing.Any],
        gm: 'auths.GroupsManager',
        request: 'ExtendedHttpRequestWithUser',
    ) -> typing.Optional[str]:
        samlResponseMsg: typing.Optional[str] = parameters.get(
            lasso.SAML2_FIELD_RESPONSE, None
        )

        logout: typing.Optional[lasso.Logout] = None

        if 'logout' in parameters:
            if (
                not request.user
            ):  # This is a SAML Response, we can ignore it, because the user was already logged out
                raise auths.exceptions.Logout(parameters.get('RelayState'))

            server: typing.Optional[lasso.Server] = None
            samlRequestMsg: typing.Optional[str] = parameters.get(
                lasso.SAML2_FIELD_REQUEST, None
            )
            session = self.storage.get('lasso-' + request.user.name)
            if session and samlRequestMsg:
                # Process logout
                try:
                    server = self.__createServer()
                    logout = lasso.Logout(server)
                    logout.setSessionFromDump(session)

                    query = parameters.get('_query', '')
                    logger.debug('Query: %s', query)
                    if samlRequestMsg is not None:
                        logout.processRequestMsg(query)

                    # Build logout request to idp
                    logout.buildResponseMsg()

                    logger.debug('Logout data: %s', logout.debug())

                    # Return to logout message url, but also logout user from this platform
                    raise auths.exceptions.Logout(logout.msgUrl)

                except lasso.DsSignatureNotFoundError:
                    logger.warning(
                        'Logout message request from %s is not signed',
                        server.providers.keys()[0] if server else None,
                    )
                except Exception:
                    logger.exception(
                        'SAML Logout %s', logout.debug() if logout else None
                    )
                    # Silently redirect to '/'
                    raise auths.exceptions.Redirect('/')

                raise auths.exceptions.Logout(parameters.get('RelayState'))

        logger.debug("samlResponseMSG: %s", samlResponseMsg)

        if not samlResponseMsg:
            raise auths.exceptions.AuthenticatorException('Can\'t locate saml response')

        server = self.__createServer()
        login: lasso.Login = lasso.Login(server)

        try:
            login.processAuthnResponseMsg(samlResponseMsg)
        except (lasso.DsError, lasso.ProfileCannotVerifySignatureError) as e:
            logger.exception('Got exception processing response')
            raise auths.exceptions.AuthenticatorException(
                'Invalid signature: {}'.format(e)
            )
        except lasso.Error as e:
            raise auths.exceptions.AuthenticatorException(
                'Misc error : {0}'.format(lasso.strError(e[0]))
            )

        assertion = login.assertion
        # Check that authentication is in response to an sent request
        # if request.session.get(SAML_REQUEST_ID, '') != assertion.subject.subjectConfirmation.subjectConfirmationData.inResponseTo:
        #     logger.debug('Session id: {0}, inResponseTo; {1}'.format(request.session.get(SAML_REQUEST_ID, ''), assertion.subject.subjectConfirmation.subjectConfirmationData.inResponseTo ))
        #     raise auths.exceptions.AuthenticatorException('Invalid response id')

        if (
            assertion.subject.subjectConfirmation.method
            != 'urn:oasis:names:tc:SAML:2.0:cm:bearer'
        ):
            raise auths.exceptions.AuthenticatorException(
                'Unknown subject confirmation method'
            )

        # Audience restriction
        try:
            audienceOk = False
            for audience_restriction in assertion.conditions.audienceRestriction:
                if audience_restriction.audience != login.server.providerId:
                    raise auths.exceptions.AuthenticatorException(
                        'Incorrect audience restriction'
                    )
                audienceOk = True
            if audienceOk is False:
                raise auths.exceptions.AuthenticatorException(
                    'Incorrect audience restriction'
                )
        except:
            raise auths.exceptions.AuthenticatorException(
                'Error checking AudienceResctriction'
            )

        # Check, not before, notOnAfter
        notBefore = (
            assertion.subject.subjectConfirmation.subjectConfirmationData.notBefore
        )
        notOnOrAfter = (
            assertion.subject.subjectConfirmation.subjectConfirmationData.notOnOrAfter
        )

        if notBefore:
            raise auths.exceptions.AuthenticatorException(
                'assertion in response to AuthnRequest, notBefore MUST not be in SubjectConfirmationData'
            )

        if not notOnOrAfter or not notOnOrAfter.endswith('Z'):
            raise auths.exceptions.AuthenticatorException('Invalid notOnOrAfter value')

        # if models.getSqlDatetime() > iso8601_to_datetime(notOnOrAfter):
        #     raise auths.exceptions.AuthenticatorException('Assertion has expired: {} > {}'.format(models.getSqlDatetime(), iso8601_to_datetime(notOnOrAfter)))

        try:
            login.acceptSso()
        except lasso.Error:
            raise auths.exceptions.AuthenticatorException('Invalid assertion')

        logger.debug('Accepted SSO: %s', login.debug())

        # Read attributes
        attributes: typing.Dict[str, typing.Any] = {}
        for attStatement in assertion.attributeStatement:
            for attr in attStatement.attribute:
                name = None
                nickName = None
                try:
                    name = attr.name
                except Exception:
                    logger.warning('error decoding name of attribute %s', attr.dump())
                    continue
                if attr.friendlyName:
                    nickName = attr.friendlyName

                try:
                    values = attr.attributeValue
                    if not values:
                        continue
                    if name not in attributes:
                        attributes[name] = []
                    if nickName:
                        if nickName not in attributes:
                            attributes[nickName] = attributes[name]
                    for value in values:
                        content = ''.join(
                            [anyValue.exportToXml() for anyValue in value.any]
                        )
                        logger.debug(content)
                        attributes[name].append(content)
                except Exception as e:
                    logger.warning(
                        "value of an attribute field failed to decode to ascii %s due to %s",
                        attr.dump(),
                        e,
                    )

        logger.debug("Attributes: %s", attributes)

        # Now that we have attributes, we can extract values from this, map groups, etc...
        username = ''.join(self.__processField(self.userNameAttr.value, attributes))
        logger.debug('Username: %s', username)

        groups = self.__processField(self.groupNameAttr.value, attributes)
        logger.debug('Groups: %s', groups)

        realName = ' '.join(self.__processField(self.realNameAttr.value, attributes))
        logger.debug('Real name: %s', realName)

        # store groups for this username at storage, so we can check it at a later stage
        self.storage.putPickle(username, [realName, groups])
        self.storage.put(
            'lasso-' + username, login.session.dump()
        )  # Also store session

        # Now we check validity of user
        gm.validate(groups)

        return username

    def logout(self, username: str) -> auths.AuthenticationResult:
        if Config.section('SAML').value('Global logout on exit').getInt(True) == 0:
            return auths.AuthenticationResult(success=True)

        logout = self.cache.get('lasso-' + username)

        if logout:
            return logout

        server = self.__createServer()
        logout = lasso.Logout(server)

        idpEntityId = list(server.providers.keys())[0]

        session = self.storage.get('lasso-' + username)

        url: typing.Optional[str] = None
        if session:
            try:
                logout.setSessionFromDump(session)
                logout.initRequest(idpEntityId, lasso.HTTP_METHOD_REDIRECT)

                logout.buildRequestMsg()

                url = logout.msgUrl

                # Cache for a while, just in case this repeats...
                self.cache.put('lasso-' + username, logout.msgUrl, 10)

                self.storage.remove(username)
                self.storage.remove('lasso-' + username)
            except Exception as e:
                logger.warning(
                    'SAML Global logout is enabled on configuration, but an error ocurred processing logout: %s',
                    e,
                )

        return auths.AuthenticationResult(success=True, url=url)

    def getGroups(self, username: str, groupsManager: 'auths.GroupsManager'):
        data = self.storage.getPickle(username)
        if not data:
            return
        groupsManager.validate(data[1])

    def getRealName(self, username: str) -> str:
        data = self.storage.getPickle(username)
        if not data:
            return username
        return data[0]

    def getJavascript(self, request: 'HttpRequest') -> typing.Optional[str]:
        """
        We will here compose the saml request and send it via http-redirect
        """
        server = self.__createServer()
        try:
            login = lasso.Login(server)
        except Exception:
            raise auths.exceptions.InvalidAuthenticatorException(
                'Can\'t create lasso login'
            )

        idpEntityId = list(server.providers.keys())[0]
        # logger.debug('IDP Entity ID: %s', idpEntityId)

        # httpMethod = server.getFirstHttpMethod(server.providers[idpEntityId], lasso.MD_PROTOCOL_TYPE_SINGLE_SIGN_ON)

        # logger.debug('Lasso httpMethod: {0}'.format(httpMethod))

        # if httpMethod == lasso.HTTP_METHOD_NONE:
        if (
            server.acceptHttpMethod(
                server.providers[idpEntityId],
                lasso.MD_PROTOCOL_TYPE_SINGLE_SIGN_ON,
                lasso.HTTP_METHOD_REDIRECT,
                True,
            )
            is False
        ):
            raise auths.exceptions.InvalidAuthenticatorException(
                'IDP do not have any supported SingleSignOn method'
            )

        try:
            login.initAuthnRequest(idpEntityId, lasso.HTTP_METHOD_REDIRECT)
        except lasso.Error as error:
            raise auths.exceptions.InvalidAuthenticatorException(
                'Error at initAuthnRequest: {0}'.format(lasso.strError(error[0]))
            )

        try:
            login.buildAuthnRequestMsg()
        except lasso.Error as error:
            raise auths.exceptions.InvalidAuthenticatorException(
                'Error at buildAuthnRequestMsg: {0}'.format(lasso.strError(error[0]))
            )

        request.session[SAML_REQUEST_ID] = login.request.iD
        logger.debug('Request session ID: %s', login.request.iD)

        # logger.debug(login.dump())

        return 'window.location="{0}";'.format(login.msgUrl)

    def removeUser(self, username):
        """
        Clean ups storage data
        """
        self.storage.remove(username)
        self.storage.remove('lasso-' + username)
