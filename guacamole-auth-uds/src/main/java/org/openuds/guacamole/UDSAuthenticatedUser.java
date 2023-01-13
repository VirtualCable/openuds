/*
 * Copyright (c) 2020 Virtual Cable S.L.U.
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
 *    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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

import org.apache.guacamole.net.auth.AbstractAuthenticatedUser;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.AuthenticationProvider;
import org.apache.guacamole.net.auth.Credentials;
import org.openuds.guacamole.connection.UDSConnection;

/**
 * A Guacamole user that was authenticated by an external UDS service.
 */
public class UDSAuthenticatedUser extends AbstractAuthenticatedUser {

    /**
     * The AuthenticationProvider that authenticated this user.
     */
    private final AuthenticationProvider authProvider;

    /**
     * The credentials provided by this user when they authenticated.
     */
    private final Credentials credentials;

    /**
     * The single connection that this user should be authorized to access.
     */
    private final UDSConnection connection;

    /**
     * Creates a new UDSAuthenticatedUser representing a Guacamole user that
     * was authenticated by an external UDS service.
     *
     * @param authProvider
     *     The AuthenticationProvider that authenticated the user.
     *
     * @param credentials
     *     The credentials provided by the user when they authenticated.
     *
     * @param connection
     *     The single connection that the user should be authorized to access.
     */
    public UDSAuthenticatedUser(AuthenticationProvider authProvider,
            Credentials credentials, UDSConnection connection) {
        this.authProvider = authProvider;
        this.credentials = credentials;
        this.connection = connection;
    }

    @Override
    public String getIdentifier() {
        return AuthenticatedUser.ANONYMOUS_IDENTIFIER;
    }

    @Override
    public AuthenticationProvider getAuthenticationProvider() {
        return authProvider;
    }

    @Override
    public Credentials getCredentials() {
        return credentials;
    }

    /**
     * Returns the single connection that this user should be authorized to
     * access.
     *
     * @return
     *     The single connection that this user should be authorized to access.
     */
    public UDSConnection getConnection() {
        return connection;
    }

}
