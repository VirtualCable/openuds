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
import java.util.Properties;
import javax.servlet.ServletContext;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.GuacamoleServerException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Service that provides access to configuration information stored within
 * OpenUDS' tunnel.properties file.
 */
@Singleton
public class ConfigurationService {

    /**
     * Logger for this class.
     */
    private final Logger logger = LoggerFactory.getLogger(ConfigurationService.class);

    /**
     * The name of the property within tunnel.properties which defines the file
     * whose content dictates the base URL of the service providing connection
     * configuration information.
     */
    private static final String UDSFILE_PROPERTY = "udsfile";

    /**
     * The path beneath the OpenUDS service base URI (scheme + hostname) at
     * which the connection configuration service can be found. Currently, this
     * is hard-coded as "/guacamole/".
     */
    private static final String UDS_CONNECTION_PATH = "/guacamole/";

    /**
     * The base URI (scheme + hostname) where OpenUDS is being served.
     */
    private final URI udsBaseURI;

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
     * Given an arbitrary URI, returns a new URI which contains only the scheme
     * and host. The path, fragment, etc. of the given URI, if any, are
     * discarded.
     *
     * @param uri
     *     An arbitrary URI from which a base URI should be derived.
     *
     * @return
     *     A new URI containing only the scheme and host of the provided URI.
     *
     * @throws GuacamoleException
     *     If the new URI could not be generated because the result is not a
     *     valid URI.
     */
    private URI getBaseURI(URI uri) throws GuacamoleException {

        // Build base URI from only the scheme and host of the given URI
        try {
            return new URI(uri.getScheme(), null, uri.getHost(), uri.getPort(),
                    null, null, null);
        }
        catch (URISyntaxException e) {
            throw new GuacamoleServerException("Failed to derive base URI.", e);
        }

    }

    /**
     * Creates a new ConfigurationService which provides access to the
     * configuration information stored within the "/WEB-INF/tunnel.properties"
     * file in the classpath. This file will be parsed immediately, but any
     * resulting errors will simply be logged. If configuration information
     * cannot be read, attempts to retrieve this information later through calls
     * to the getters of this service will fail with appropriate exceptions.
     *
     * @param context
     *     The ServletContext associated with the servlet container which is
     *     serving this web application.
     */
    @Inject
    public ConfigurationService(ServletContext context) {

        // Read tunnel.properties
        Properties config = new Properties();
        try {
            config.load(context.getResourceAsStream("/WEB-INF/tunnel.properties"));
        }
        catch (IOException e) {
            logger.error("Unable to read tunnel.properties.", e);
        }

        // Parse URI from the UDS file (if defined)
        URI parsedURI = null;
        String udsFile = config.getProperty(UDSFILE_PROPERTY);
        if (udsFile != null) {

            // Attempt to parse base URI from the UDS file, logging any failures
            try {
                parsedURI = getBaseURI(readServiceURI(udsFile));
            }
            catch (GuacamoleException e) {
                logger.error("OpenUDS service URI could not be parsed. This "
                           + "web application WILL NOT FUNCTION.", e);
            }

        }

        // If no UDS file is defined, web application startup has failed
        else
            logger.error("Property \"{}\" not found within tunnel.properties. "
                       + "This web application WILL NOT FUNCTION.", UDSFILE_PROPERTY);

        // Assign the parsed URI, which may be null
        udsBaseURI = parsedURI;

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

        // Explicitly fail if the configuration was not successfully read
        if (udsBaseURI == null)
            throw new GuacamoleServerException("The UDS base URI is not defined.");

        return udsBaseURI;

    }

    /**
     * Returns the path beneath the OpenUDS base URI at which the connection
     * configuration service can be found. This service is expected to respond
     * to HTTP GET requests, returning the configuration of requested
     * connections.
     *
     * @return
     *     The path beneath the OpenUDS base URI at which the connection
     *     configuration service can be found.
     */
    public String getUDSConnectionPath() {
        return UDS_CONNECTION_PATH;
    }

}
