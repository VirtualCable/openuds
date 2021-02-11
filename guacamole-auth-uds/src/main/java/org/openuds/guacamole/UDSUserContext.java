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

import java.util.Collections;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.net.auth.AbstractUserContext;
import org.apache.guacamole.net.auth.AuthenticationProvider;
import org.apache.guacamole.net.auth.Connection;
import org.apache.guacamole.net.auth.Directory;
import org.apache.guacamole.net.auth.User;
import org.apache.guacamole.net.auth.permission.ObjectPermissionSet;
import org.apache.guacamole.net.auth.simple.SimpleDirectory;
import org.apache.guacamole.net.auth.simple.SimpleObjectPermissionSet;
import org.apache.guacamole.net.auth.simple.SimpleUser;
import org.openuds.guacamole.connection.UDSConnection;

/**
 * UserContext implementation which exposes access only to a single
 * UDSConnection. The details of the connection exposed are determined by the
 * UDS-specific data associated with the user.
 */
public class UDSUserContext extends AbstractUserContext {

    /**
     * The unique identifier of the root connection group.
     */
    public static final String ROOT_CONNECTION_GROUP = DEFAULT_ROOT_CONNECTION_GROUP;

    /**
     * The AuthenticationProvider that produced this UserContext.
     */
    private final AuthenticationProvider authProvider;

    /**
     * The AuthenticatedUser for whom this UserContext was created.
     */
    private final UDSAuthenticatedUser authenticatedUser;

    /**
     * Creates a new UDSUserContext that is associated with the given
     * AuthenticationProvider and uses the UDS-specific data of the given
     * UDSAuthenticatedUser to determine the connection that user can access.
     *
     * @param authProvider
     *     The AuthenticationProvider that is producing the UserContext.
     *
     * @param authenticatedUser
     *     The AuthenticatedUser for whom this UserContext is being created.
     */
    public UDSUserContext(AuthenticationProvider authProvider,
            UDSAuthenticatedUser authenticatedUser) {
        this.authProvider = authProvider;
        this.authenticatedUser = authenticatedUser;
    }

    @Override
    public User self() {
        return new SimpleUser() {

            @Override
            public ObjectPermissionSet getConnectionGroupPermissions() throws GuacamoleException {
                return new SimpleObjectPermissionSet(Collections.singleton(DEFAULT_ROOT_CONNECTION_GROUP));
            }

            @Override
            public ObjectPermissionSet getConnectionPermissions() throws GuacamoleException {
                return new SimpleObjectPermissionSet(Collections.singleton(UDSConnection.IDENTIFIER));
            }

        };
    }

    @Override
    public AuthenticationProvider getAuthenticationProvider() {
        return authProvider;
    }

    @Override
    public Directory<Connection> getConnectionDirectory() throws GuacamoleException {
        return new SimpleDirectory<>(authenticatedUser.getConnection());
    }

}
