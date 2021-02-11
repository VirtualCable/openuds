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

package org.openuds.guacamole.config;

import com.google.inject.Inject;
import com.google.inject.Singleton;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.GuacamoleServerException;
import org.apache.guacamole.environment.Environment;
import org.apache.guacamole.properties.URIGuacamoleProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Service that provides access to OpenUDS-specific configuration information
 * stored within guacamole.properties.
 */
@Singleton
public class ConfigurationService {

    /**
     * Logger for this class.
     */
    private final Logger logger = LoggerFactory.getLogger(ConfigurationService.class);

    /**
     * The name of the property within guacamole.properties which defines the
     * base URL of the service providing connection configuration information.
     */
    private static final URIGuacamoleProperty UDS_BASE_URL_PROPERTY = new URIGuacamoleProperty() {

        @Override
        public String getName() {
            return "uds-base-url";
        }

    };

    /**
     * The Guacamole server environment.
     */
    @Inject
    private Environment environment;

    /**
     * Parses the contents of the given file, reading the URI of the OpenUDS
     * service contained therein. The file is expected to define this URI on
     * the first line, and only the first line is read.
     *
     * @param udsFile
     *     The file from which the URI of the OpenUDS service should be read.
     *
     * @return
     *     The URI of the OpenUDS service.
     *
     * @throws GuacamoleException
     *     If the file could not be opened or read for any reason, or if the
     *     line read from the file is not a valid URI.
     */
    private URI readServiceURI(String udsFile) throws GuacamoleException {

        // Open UDS file
        BufferedReader input;
        try {
            input = new BufferedReader(new FileReader(udsFile));
        }
        catch (IOException e) {
            throw new GuacamoleServerException("Failed to open UDS file.", e);
        }

        // Parse the first line (and only the first line) assuming it contains
        // the URL of the OpenUDS service
        try {
            return new URI(input.readLine());
        }

        // Rethrow general failure to read from the file
        catch (IOException e) {
            throw new GuacamoleServerException("Failed to read UDS service URI from file.", e);
        }

        // Rethrow failure to parse the URL
        catch (URISyntaxException e) {
            throw new GuacamoleServerException("Failed to parse UDS service URI from file.", e);
        }

        // Always close the file
        finally {

            try {
                input.close();
            }
            catch (IOException e) {
                logger.warn("Closure of OpenUDS file failed. Resource may leak.", e);
            }

        }

    }

    /**
     * Returns the base URI of the OpenUDS service. All services providing data
     * to this Guacamole integration are hosted beneath this base URI.
     *
     * @return
     *     The base URI of the OpenUDS service.
     *
     * @throws GuacamoleException
     *     If the base URI of the OpenUDS service is not defined because the
     *     tunnel.properties file could not be parsed when the web application
     *     started.
     */
    public URI getUDSBaseURI() throws GuacamoleException {
        return environment.getRequiredProperty(UDS_BASE_URL_PROPERTY);
    }

}
