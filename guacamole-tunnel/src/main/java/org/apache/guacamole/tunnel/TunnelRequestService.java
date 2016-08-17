/*
 * This file has been modified from the original, upstream version to facilitate
 * integration with OpenUDS.
 */

/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package org.apache.guacamole.tunnel;

import com.google.inject.Inject;
import com.google.inject.Singleton;
import java.util.List;
import org.apache.guacamole.GuacamoleClientException;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.net.GuacamoleSocket;
import org.apache.guacamole.net.GuacamoleTunnel;
import org.apache.guacamole.net.InetGuacamoleSocket;
import org.apache.guacamole.net.SimpleGuacamoleTunnel;
import org.apache.guacamole.protocol.ConfiguredGuacamoleSocket;
import org.apache.guacamole.protocol.GuacamoleClientInformation;
import org.apache.guacamole.protocol.GuacamoleConfiguration;
import org.openuds.guacamole.connection.ConnectionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Utility class that takes a standard request from the Guacamole JavaScript
 * client and produces the corresponding GuacamoleTunnel. The implementation
 * of this utility is specific to the form of request used by the upstream
 * Guacamole web application, and is not necessarily useful to applications
 * that use purely the Guacamole API.
 *
 * @author Michael Jumper
 * @author Vasily Loginov
 */
@Singleton
public class TunnelRequestService {

    /**
     * Logger for this class.
     */
    private final Logger logger = LoggerFactory.getLogger(TunnelRequestService.class);

    /**
     * Service for retrieving remotely-maintained connection information.
     */
    @Inject
    private ConnectionService connectionService;

    /**
     * The hostname of the server hosting guacd.
     */
    private static final String GUACD_HOSTNAME = "127.0.0.1";

    /**
     * The port that guacd will be listening on.
     */
    private static final int GUACD_PORT = 4822;

    /**
     * Creates a new tunnel using the parameters and credentials present in
     * the given request.
     * 
     * @param request
     *     The HttpServletRequest describing the tunnel to create.
     *
     * @return
     *     The created tunnel, or null if the tunnel could not be created.
     *
     * @throws GuacamoleException
     *     If an error occurs while creating the tunnel.
     */
    public GuacamoleTunnel createTunnel(TunnelRequest request) throws GuacamoleException {

        // Pull OpenUDS-specific "data" parameter
        String data = request.getParameter("data");
        if (data == null || data.isEmpty()) {
            logger.debug("No ID received in tunnel connect request.");
            throw new GuacamoleClientException("Connection data not provided.");
        }

        logger.debug("Establishing tunnel and connection with data from \"{}\"...", data);

        // Get connection from remote service
        GuacamoleConfiguration config = connectionService.getConnectionConfiguration(data);
        if (config == null)
            throw new GuacamoleClientException("Connection configuration could not be retrieved.");
        
        // Get client information
        GuacamoleClientInformation info = new GuacamoleClientInformation();

        // Set width if provided
        String width = request.getParameter("GUAC_WIDTH");
        if (width != null)
            info.setOptimalScreenWidth(Integer.parseInt(width));

        // Set height if provided
        String height = request.getParameter("GUAC_HEIGHT");
        if (height != null)
            info.setOptimalScreenHeight(Integer.parseInt(height));

        // Set resolution if provided
        String dpi = request.getParameter("GUAC_DPI");
        if (dpi != null)
            info.setOptimalResolution(Integer.parseInt(dpi));

        // Add audio mimetypes
        List<String> audio_mimetypes = request.getParameterValues("GUAC_AUDIO");
        if (audio_mimetypes != null)
            info.getAudioMimetypes().addAll(audio_mimetypes);

        // Add video mimetypes
        List<String> video_mimetypes = request.getParameterValues("GUAC_VIDEO");
        if (video_mimetypes != null)
            info.getVideoMimetypes().addAll(video_mimetypes);

        // Add image mimetypes
        List<String> image_mimetypes = request.getParameterValues("GUAC_IMAGE");
        if (image_mimetypes != null)
            info.getImageMimetypes().addAll(image_mimetypes);

        // Connect socket for connection
        GuacamoleSocket socket;
        try {
	        socket = new ConfiguredGuacamoleSocket(
                new InetGuacamoleSocket(GUACD_HOSTNAME, GUACD_PORT),
                config, info
	        );
        }

        // Log any errors during connection
        catch (GuacamoleException e) {
            logger.error("Unable to connect to guacd.", e);
            throw e;
        }

        // Return corresponding tunnel
        return new SimpleGuacamoleTunnel(socket);

    }

}
