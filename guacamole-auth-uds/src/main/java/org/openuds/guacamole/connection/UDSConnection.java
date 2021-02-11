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

package org.openuds.guacamole.connection;

import java.util.Map;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.net.GuacamoleTunnel;
import org.apache.guacamole.net.auth.simple.SimpleConnection;
import org.apache.guacamole.protocol.GuacamoleClientInformation;
import org.openuds.guacamole.UDSUserContext;

/**
 * Connection implementation which uses provided data to communicate with a 
 * remote UDS service to dynamically authorize access to a remote desktop. The
 * provided data is validated when the UDSConnection is created and upon each
 * connection attempt.
 */
public class UDSConnection extends SimpleConnection {

    /**
     * The name of the single connection that should be exposed to any user
     * that authenticates via UDS.
     */
    public static final String NAME = "UDS";

    /**
     * The unique identifier of the single connection that should be exposed to
     * any user that authenticates via UDS.
     */
    public static final String IDENTIFIER = NAME;

    /**
     * Service for retrieving configuration information.
     */
    private final ConnectionService connectionService;

    /**
     * The UDS-specific data that should be provided to the remote UDS service
     * to re-authenticate the user and determine the details of the connection
     * they are authorized to access.
     */
    private final String data;

    /**
     * Creates a new UDSConnection which exposes access to a remote desktop
     * that is dynamically authorized by exchanging arbitrary UDS-specific data
     * with a remote service. If the data is accepted by the UDS service, the
     * data will also be re-validated upon each connection attempt.
     *
     * @param connectionService
     *     The service that should be used to validate the provided UDS data
     *     and retrieve corresponding connection configuration information.
     *
     * @param data
     *     The UDS-specific data that should be provided to the remote UDS
     *     service.
     *
     * @throws GuacamoleException
     *     If the provided data is no longer valid or the UDS service does not
     *     respond successfully.
     */
    public UDSConnection(ConnectionService connectionService, String data)
            throws GuacamoleException {

        // Validate provided data
        super.setConfiguration(connectionService.getConnectionConfiguration(data));

        this.connectionService = connectionService;
        this.data = data;

    }

    @Override
    public String getParentIdentifier() {
        return UDSUserContext.ROOT_CONNECTION_GROUP;
    }

    @Override
    public void setParentIdentifier(String parentIdentifier) {
        throw new UnsupportedOperationException("UDSConnection is read-only.");
    }

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public void setName(String name) {
        throw new UnsupportedOperationException("UDSConnection is read-only.");
    }

    @Override
    public String getIdentifier() {
        return IDENTIFIER;
    }

    @Override
    public void setIdentifier(String identifier) {
        throw new UnsupportedOperationException("UDSConnection is read-only.");
    }

    @Override
    public GuacamoleTunnel connect(GuacamoleClientInformation info,
            Map<String, String> tokens) throws GuacamoleException {

        // Re-validate provided data (do not allow connections if data is no
        // longer valid)
        super.setConfiguration(connectionService.getConnectionConfiguration(data));

        // Connect with configuration produced from data
        return super.connect(info, tokens);

    }

}
