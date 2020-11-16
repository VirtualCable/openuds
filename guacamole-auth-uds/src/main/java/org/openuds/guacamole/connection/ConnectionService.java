/*
 * Copyright (c) 2015 Virtual Cable S.L.
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

package org.openuds.guacamole.connection;

import com.google.inject.Inject;
import com.google.inject.Singleton;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.URLConnection;
import java.util.HashMap;
import java.util.Map;
import javax.ws.rs.core.UriBuilder;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.GuacamoleServerException;
import org.apache.guacamole.protocol.GuacamoleConfiguration;
import org.openuds.guacamole.config.ConfigurationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Service which communicates with the remote OpenUDS connection service,
 * providing access to the underlying connection configuration.
 */
@Singleton
public class ConnectionService {

    /**
     * Logger for this class.
     */
    private final Logger logger = LoggerFactory.getLogger(ConnectionService.class);

    /**
     * The name of the parameter returned by the OpenUDS connection
     * configuration service which will contain the protocol that Guacamole
     * should use to initiate the remote desktop connection.
     */
    private static final String PROTOCOL_PARAMETER = "protocol";

    /**
     * Service for retrieving configuration information.
     */
    @Inject
    private ConfigurationService configService;

    /**
     * Makes an HTTP GET request to the OpenUDS service running at the given
     * URI, parsing the response into connection configuration data. The
     * response MUST be simple text, one line per connection parameter, with the
     * name of the connection parameter separated from the corresponding value
     * by a tab character. If the OpenUDS service encounters an error, it is
     * expected to return the single word "ERROR" on one line. Lines which do
     * not match these expectations will be skipped.
     *
     * @param uri
     *     The URI of the OpenUDS service to which the HTTP GET request should
     *     be made.
     *
     * @return
     *     A map of all parameter name/value pairs returned by the OpenUDS
     *     service.
     *
     * @throws GuacamoleException
     *     If the OpenUDS service returns an error, or the response from the
     *     service cannot be read.
     */
    private Map<String, String> readConnectionConfiguration(URI uri)
            throws GuacamoleException {

        BufferedReader response;

        // Connect to OpenUDS
        try {
            URLConnection connection = uri.toURL().openConnection();
            response = new BufferedReader(new InputStreamReader(connection.getInputStream()));
        }
        catch (IOException e) {
            throw new GuacamoleServerException("Unable to open connection to OpenUDS service.", e);
        }

        Map<String, String> parameters = new HashMap<String, String>();

        // Read and parse each line of the response
        try {

            String inputLine;
            while ((inputLine = response.readLine()) != null) {

                // Abort upon error
                if (inputLine.equals("ERROR"))
                    throw new GuacamoleServerException("OpenUDS service returned an error.");

                // Determine separation between each line's key and value
                int tab = inputLine.indexOf('\t');
                if (tab == -1)
                    continue;

                // Add key/value pair from either side of the tab
                parameters.put(
                    inputLine.substring(0, tab),
                    inputLine.substring(tab + 1)
                );

            }

        }

        // Rethrow any error which occurs during reading
        catch (IOException e) {
            throw new GuacamoleServerException("Failed to read response from OpenUDS service.", e);
        }

        // Always close the stream
        finally {

            try {
                response.close();
            }
            catch (IOException e) {
                logger.warn("Closure of connection to OpenUDS failed. Resource may leak.", e);
            }

        }

        // Parameters have been successfully parsed
        return parameters;

    }

    /**
     * Queries OpenUDS for the connection configuration for the connection
     * associated with the given data. This data is an opaque value provided
     * via the "data" parameter to the Guacamole tunnel.
     *
     * @param data
     *     The OpenUDS-specific data which defines the connection whose
     *     configuration should be retrieved.
     *
     * @return
     *     The configuration of the connection associated with the provided
     *     OpenUDS-specific data.
     *
     * @throws GuacamoleException
     *     If the connection configuration could not be retrieved from OpenUDS,
     *     of the response from OpenUDS was missing required information.
     */
    public GuacamoleConfiguration getConnectionConfiguration(String data)
            throws GuacamoleException {

        // Build URI of remote service from the base URI and given data
        URI serviceURI = UriBuilder.fromUri(configService.getUDSBaseURI())
                .path(configService.getUDSConnectionPath())
                .path(data)
                .build();

        // Pull connection configuration from remote service
        Map<String, String> params = readConnectionConfiguration(serviceURI);

        // Pull the protocol from the parameters
        String protocol = params.remove(PROTOCOL_PARAMETER);
        if (protocol == null)
            throw new GuacamoleServerException("Protocol missing from OpenUDS response.");

        // Create our configuration
        GuacamoleConfiguration config = new GuacamoleConfiguration();
        config.setProtocol(protocol);
        config.setParameters(params);

        return config;

    }

}
