//
// Copyright (c) 2012 Virtual Cable S.L.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without modification, 
// are permitted provided that the following conditions are met:
//
//    * Redistributions of source code must retain the above copyright notice, 
//      this list of conditions and the following disclaimer.
//    * Redistributions in binary form must reproduce the above copyright notice, 
//      this list of conditions and the following disclaimer in the documentation 
//      and/or other materials provided with the distribution.
//    * Neither the name of Virtual Cable S.L. nor the names of its contributors 
//      may be used to endorse or promote products derived from this software 
//      without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE 
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER 
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, 
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

// author: Adolfo Gómez, dkmaster at dkmon dot com

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using CookComputing.XmlRpc;

namespace UdsAdmin.xmlrpc
{
    public interface IUDSAdmin : IXmlRpcProxy
    {
        // Login, return credentials if logged in or empty if can't log in
        [XmlRpcMethod("login")]
        LoginData Login(string username, string password, string idAuth, string locale);

        [XmlRpcMethod("getAdminAuths")]
        SimpleInfo[] GetAdminAuths(string locale);

        [XmlRpcMethod("logout")]
        string Logout(string credentials);

        // Service provider related methods
        [XmlRpcMethod("getServiceProvidersTypes")]
        ServiceProviderType[] GetServiceProvidersTypes(string credentials);

        [XmlRpcMethod("getServiceProviders")]
        ServiceProvider[] GetServiceProviders(string credentials);

        [XmlRpcMethod("getServiceProviderGui")]
        GuiField[] GetServiceProviderGui(string credentials, string type);

        [XmlRpcMethod("getServiceProvider")]
        GuiFieldValue[] GetServiceProvider(string credentials, string id);

        [XmlRpcMethod("createServiceProvider")]
        bool CreateServiceProvider(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("modifyServiceProvider")]
        bool ModifyServiceProvider(string credentials, string id, GuiFieldValue[] data);

        [XmlRpcMethod("removeServiceProvider")]
        bool RemoveServiceProvider(string credentials, string id);

        [XmlRpcMethod("getOffersFromServiceProvider")]
        ServiceType[] GetOffersFromServiceProvider(string credentials, string type);

        [XmlRpcMethod("testServiceProvider")]
        ResultTest TestServiceProvider(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("checkServiceProvider")]
        string CheckServiceProvider(string credentials, string id);

        // Services related methods
        [XmlRpcMethod("getServices")]
        Service[] GetServices(string credentials, string idParent);

        [XmlRpcMethod("getAllServices")]
        Service[] GetAllServices(string credentials);

        [XmlRpcMethod("getServiceGui")]
        GuiField[] GetServiceGui(string credentials, string idParent, string type);

        [XmlRpcMethod("getService")]
        GuiFieldValue[] GetService(string credentials, string id);

        [XmlRpcMethod("createService")]
        bool CreateService(string credentials, string idParent, string type, GuiFieldValue[] data);

        [XmlRpcMethod("modifyService")]
        bool ModifyService(string credentials, string id, GuiFieldValue[] data);

        [XmlRpcMethod("removeService")]
        bool RemoveService(string credentials, string id);

        // Authenticators
        [XmlRpcMethod("getAuthenticatorsTypes")]
        AuthenticatorType[] GetAuthenticatorsTypes(string credentials);

        [XmlRpcMethod("getAuthenticatorType")]
        AuthenticatorType GetAuthenticatorType(string credentials, string id);

        [XmlRpcMethod("getAuthenticators")]
        Authenticator[] GetAuthenticators(string credentials);

        [XmlRpcMethod("getAuthenticatorGui")]
        GuiField[] GetAuthenticatorGui(string credentials, string type);

        [XmlRpcMethod("getAuthenticator")]
        GuiFieldValue[] GetAuthenticator(string credentials, string id);

        [XmlRpcMethod("getAuthenticatorGroups")]
        Group[] GetAuthenticatorGroups(string credentials, string id);

        [XmlRpcMethod("createAuthenticator")]
        bool CreateAuthenticator(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("modifyAuthenticator")]
        bool ModifyAuthenticator(string credentials, string id, GuiFieldValue[] data);

        [XmlRpcMethod("removeAuthenticator")]
        bool RemoveAuthenticator(string credentials, string id);

        [XmlRpcMethod("testAuthenticator")]
        ResultTest TestAuthenticator(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("checkAuthenticator")]
        string CheckAuthenticator(string credentials, string id);

        [XmlRpcMethod("searchAuthenticator")]
        SimpleInfo[] SearchAuthenticator(string credentials, string id, bool srchUser, string srchString);

        // Authenticators, groups part
        [XmlRpcMethod("getGroups")]
        Group[] GetGroups(string credentials, string idParent);

        [XmlRpcMethod("getGroup")]
        Group GetGroup(string credentials, string id);

        [XmlRpcMethod("createGroup")]
        bool CreateGroup(string credentials, Group group);

        [XmlRpcMethod("changeGroupsState")]
        bool ChangeGroupsState(string credentials, string[] ids, bool newState);

        [XmlRpcMethod("removeGroups")]
        bool RemoveGroups(string credentials, string[] ids);

        // Authenticators, users part
        [XmlRpcMethod("getUsers")]
        User[] GetUsers(string credentials, string idParent);

        [XmlRpcMethod("getUser")]
        User GetUser(string credentials, string id);

        [XmlRpcMethod("getUserGroups")]
        Group[] GetUserGroups(string credentials, string id);

        [XmlRpcMethod("changeUsersState")]
        bool ChangeUsersState(string credentials, string[] ids, string newState);

        [XmlRpcMethod("removeUsers")]
        bool RemoveUsers(string credentials, string[] ids);

        [XmlRpcMethod("createUser")]
        bool CreateUser(string credentials, User user);

        [XmlRpcMethod("modifyUser")]
        bool ModifyUser(string credentials, User user);

        [XmlRpcMethod("getPrefsForUser")]
        PrefGroup[] GetPrefsForUser(string credentials, string id);

        [XmlRpcMethod("setPrefsForUser")]
        bool SetPrefsForUser(string credentials, string id, GuiFieldValue[] data);

        // OS Managers related methods
        [XmlRpcMethod("getOSManagersTypes")]
        OSManagerType[] GetOSManagersTypes(string credentials);

        [XmlRpcMethod("getOSManagers")]
        OSManager[] GetOSManagers(string credentials);

        [XmlRpcMethod("getOSManagerGui")]
        GuiField[] GetOSManagerGui(string credentials, string type);

        [XmlRpcMethod("getOSManager")]
        GuiFieldValue[] GetOSManager(string credentials, string id);

        [XmlRpcMethod("createOSManager")]
        bool CreateOSManager(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("modifyOSManager")]
        bool ModifyOSManager(string credentials, string id, GuiFieldValue[] data);

        [XmlRpcMethod("removeOSManager")]
        bool RemoveOSManager(string credentials, string id);

        [XmlRpcMethod("testOsManager")]
        ResultTest TestOsManager(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("checkOSManager")]
        string CheckOSManager(string credentials, string id);

        // Transports related methods
        [XmlRpcMethod("getTransportsTypes")]
        TransportType[] GetTransportsTypes(string credentials);

        [XmlRpcMethod("getTransports")]
        Transport[] GetTransports(string credentials);

        [XmlRpcMethod("getTransportGui")]
        GuiField[] GetTransportGui(string credentials, string type);

        [XmlRpcMethod("getTransport")]
        GuiFieldValue[] GetTransport(string credentials, string id);

        [XmlRpcMethod("createTransport")]
        string CreateTransport(string credentials, string type, GuiFieldValue[] data);

        [XmlRpcMethod("modifyTransport")]
        bool ModifyTransport(string credentials, string id, GuiFieldValue[] data);

        [XmlRpcMethod("removeTransport")]
        bool RemoveTransport(string credentials, string id);

        [XmlRpcMethod("checkTransport")]
        string CheckTransport(string credentials, string id);
        
        // Networks related (transports networks)
        [XmlRpcMethod("getNetworks")]
        Network[] GetNetworks(string credentials);

        [XmlRpcMethod("getNetworksForTransport")]
        string[] getNetworksForTransport(string credentials, string id);

        [XmlRpcMethod("setNetworksForTransport")]
        bool setNetworksForTransport(string credentials, string id, string[] networks);

        [XmlRpcMethod("getNetwork")]
        Network GetNetwork(string credentials, string id);

        [XmlRpcMethod("createNetwork")]
        bool CreateNetwork(string credentials, Network network);

        [XmlRpcMethod("modifyNetwork")]
        bool ModifyNetwork(string credentials, Network network);

        [XmlRpcMethod("removeNetworks")]
        bool RemoveNetworks(string credentials, string[] ids);


        // Deployed Services related
        [XmlRpcMethod("getDeployedServices")]
        DeployedService[] GetDeployedServices(string credentials, bool all);

        [XmlRpcMethod("getDeployedService")]
        DeployedService GetDeployedService(string credentials, string id);

        [XmlRpcMethod("removeDeployedService")]
        bool RemoveDeployedService(string credentials, string id);

        [XmlRpcMethod("createDeployedService")]
        string CreateDeployedService(string credentials, DeployedService deployedService);

        [XmlRpcMethod("modifyDeployedService")]
        bool ModifyDeployedService(string credentials, DeployedService deployedService);

        [XmlRpcMethod("getGroupsAssignedToDeployedService")]
        Group[] GetGroupsAssignedToDeployedService(string credentials, string deployedServiceId);

        [XmlRpcMethod("assignGroupToDeployedService")]
        bool AssignGroupToDeployedService(string credentials, string deployedServiceId, string groupId);

        [XmlRpcMethod("removeGroupsFromDeployedService")]
        bool RemoveGroupsFromDeployedService(string credentials, string deployedService, string[] groupIds);

        [XmlRpcMethod("getTransportsAssignedToDeployedService")]
        Transport[] GetTransportsAssignedToDeployedService(string credentials, string idDeployedService);

        [XmlRpcMethod("assignTransportToDeployedService")]
        bool AssignTransportToDeployedService(string credentials, string deployedServiceId, string transportId);

        [XmlRpcMethod("removeTransportFromDeployedService")]
        bool RemoveTransportFromDeployedService(string credentials, string deployedService, string[] transportIds);

        [XmlRpcMethod("getPublications")]
        DeployedServicePublication[] GetPublications(string credentials, string idParent);

        [XmlRpcMethod("publishDeployedService")]
        bool PublishDeployedService(string credentials, string idParent);

        [XmlRpcMethod("cancelPublication")]
        bool CancelPublication(string credentials, string id);

        [XmlRpcMethod("getCachedDeployedServices")]
        CachedDeployedService[] GetCachedDeployedServices(string credentials, string idParent);

        [XmlRpcMethod("getAssignedDeployedServices")]
        AssignedDeployedService[] GetAssignedDeployedServices(string credentials, string idParent);

        [XmlRpcMethod("getAssignableDeployedServices")]
        AssignableDeployedService[] GetAssignableDeployedServices(string credentials, string idParent);

        [XmlRpcMethod("removeUserService")]
        bool RemoveUserService(string credentials, string[] ids);

        [XmlRpcMethod("assignDeployedService")]
        bool AssignDeployedService(string credentials, string idParent, string idDeployedUserService, string idUser);

        [XmlRpcMethod("getUserDeployedServiceError")]
        string GetUserDeployedServiceError(string credentials, string id);

        // Utilities and related stuff
        [XmlRpcMethod("flushCache")]
        bool FlushCache(string credentials);

        [XmlRpcMethod("getConfiguration")]
        Configuration[] GetConfiguration(string credentials);

        [XmlRpcMethod("updateConfiguration")]
        bool UpdateConfiguration(string credentials, Configuration[] configuration);

        // Callbacks invoker
        [XmlRpcMethod("chooseCallback")]
        GuiFieldValue[] InvokeChooseCallback(string credentials, string name, GuiFieldValue[] parameters);


    }

}
