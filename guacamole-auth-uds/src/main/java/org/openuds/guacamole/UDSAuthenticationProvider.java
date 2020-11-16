/*
 * Copyright (c) 2020 Virtual Cable S.L.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 *    * Redistributions of source code must retain the above copyright notice,
 *      this list of conditions and the following disclaimer.
 *    * Redistributions in binary form must reproduce the above copyright notice,
 *      this list of conditions and the following disclaimer in the documentation
 *      and/or other materials provided with the distribution.
 *    * Neither the name of Virtual Cable S.L. nor the names of its contributors
 *      may be used to endorse or promote products derived from this software
 *      without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

package org.openuds.guacamole;

import com.google.inject.Guice;
import com.google.inject.Injector;
import java.util.Collections;
import javax.servlet.http.HttpServletRequest;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.GuacamoleServerException;
import org.apache.guacamole.form.Field;
import org.apache.guacamole.net.auth.AbstractAuthenticationProvider;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.Credentials;
import org.apache.guacamole.net.auth.UserContext;
import org.apache.guacamole.net.auth.credentials.CredentialsInfo;
import org.apache.guacamole.net.auth.credentials.GuacamoleInvalidCredentialsException;
import org.apache.guacamole.net.auth.simple.SimpleUserContext;
import org.apache.guacamole.protocol.GuacamoleConfiguration;
import org.openuds.guacamole.connection.ConnectionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * AuthenticationProvider implementation which authenticates users that are
 * confirmed as authorized by an external UDS service.
 */
public class UDSAuthenticationProvider extends AbstractAuthenticationProvider {

    /**
     * The name of the single connection that should be exposed to any user
     * that authenticates via UDS.
     */
    private static final String CONNECTION_NAME = "UDS";

    /**
     * The name of the query parameter that should contain the data sent to
     * the UDS service for authentication.
     */
    private static final String DATA_PARAMETER_NAME = "data";

    /**
     * Logger for this class.
     */
    private final Logger logger = LoggerFactory.getLogger(UDSAuthenticationProvider.class);

    /**
     * Service for retrieving connection configuration information from the
     * UDS service.
     */
    private final ConnectionService connectionService;

    /**
     * Creates a new UDSAuthenticationProvider which authenticates users
     * against an external UDS service.
     *
     * @throws GuacamoleException
     *     If an error prevents guacamole.properties from being read.
     */
    public UDSAuthenticationProvider() throws GuacamoleException {

        // Create an injector with OpenUDS- and Guacamole-specific services
        // properly bound
        Injector injector = Guice.createInjector(
            new UDSModule()
        );

        // Pull instance of connection service from injector
        connectionService = injector.getInstance(ConnectionService.class);

    }

    @Override
    public String getIdentifier() {
        return "uds";
    }

    @Override
    public AuthenticatedUser authenticateUser(Credentials credentials)
            throws GuacamoleException {

        HttpServletRequest request = credentials.getRequest();

        // Pull OpenUDS-specific "data" parameter
        String data = request.getParameter(DATA_PARAMETER_NAME);
        if (data != null && !data.isEmpty()) {

            logger.debug("Retrieving connection configuration using data from \"{}\"...", data);

            // Retrieve connection information using provided data
            GuacamoleConfiguration config = connectionService.getConnectionConfiguration(data);
            if (config != null) {

                // Report successful authentication as a temporary, anonymous user,
                // storing the retrieved connection configuration data for future use
                return new UDSAuthenticatedUser(this, credentials, config);

            }

        }

        // Required parameter was missing or was invalid
        throw new GuacamoleInvalidCredentialsException(
            "Connection data was not provided or was rejected by UDS.",
            new CredentialsInfo(Collections.<Field>singletonList(
                new Field(DATA_PARAMETER_NAME, Field.Type.QUERY_PARAMETER)
            ))
        );

    }

    @Override
    public UserContext getUserContext(AuthenticatedUser authenticatedUser)
            throws GuacamoleException {

        // Provide data only for users authenticated by this extension
        if (!(authenticatedUser instanceof UDSAuthenticatedUser))
            return null;

        // Expose a single connection (derived from the "data" parameter
        // provided during authentication)
        return new SimpleUserContext(this, Collections.singletonMap(
            CONNECTION_NAME,
            ((UDSAuthenticatedUser) authenticatedUser).getGuacamoleConfiguration()
        ));

    }

}
