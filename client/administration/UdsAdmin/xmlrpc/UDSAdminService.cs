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

using System.Windows.Forms;
using System.Reflection;

using CookComputing.XmlRpc;

namespace UdsAdmin.xmlrpc
{
    public class UdsAdminService
    {
        //public enum RemoteType { ServiceProvider = 0, Service = 1, Authenticator = 2 };
        private static IUDSAdmin s = null;
        private static string server = "";
        private static string credentials = "";
        public static bool isAdmin = false;

        private static void insertNameCommentsPriorityNet(string name, string comments, int priority, bool positiveNet, ref GuiFieldValue[] data)
        {
            int len = data.Length;
            Array.Resize(ref data, len + 4);
            data[len] = new GuiFieldValue("name", name);
            data[len + 1] = new GuiFieldValue("comments", comments);
            data[len + 2] = new GuiFieldValue("priority", priority.ToString());
            data[len + 3] = new GuiFieldValue("positiveNet", positiveNet ? xmlrpc.Constants.TRUE : xmlrpc.Constants.FALSE);
        }

        private static void insertNameCommentsPriority(string name, string comments, int priority, ref GuiFieldValue[] data)
        {
            int len = data.Length;
            Array.Resize(ref data, len + 3);
            data[len] = new GuiFieldValue("name", name);
            data[len + 1] = new GuiFieldValue("comments", comments);
            data[len + 2] = new GuiFieldValue("priority", priority.ToString());
        }

        private static void insertNameComments(string name, string comments, ref GuiFieldValue[] data)
        {
            int len = data.Length;
            Array.Resize(ref data, len + 2);
            data[len] = new GuiFieldValue("name", name);
            data[len + 1] = new GuiFieldValue("comments", comments);
        }

        public static void Initialize(string url)
        {
            System.Net.ServicePointManager.ServerCertificateValidationCallback = delegate { return true; };
            s = XmlRpcProxyGen.Create<IUDSAdmin>();
            s.Timeout = UdsAdmin.Properties.Settings.Default.TimeOut;
            s.Url = url;
            s.KeepAlive = false;
            s.EnableCompression = true; // Accepts gzip and compress data
        }

        // Service provider related methods
        public static ServiceProviderType[] GetServiceProvidersTypes()
        {
            try
            {
                return s.GetServiceProvidersTypes(credentials);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message);
            }
            return null;
        }

        public static ServiceProvider[] GetServiceProviders()
        {
            return s.GetServiceProviders(credentials);
        }

        public static GuiField[] GetServiceProviderGui(string type)
        {
            try {
                return s.GetServiceProviderGui(credentials, type);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message, "Exception invoking getServiceProviderGui!!!");
                return null;
            }

        }

        public static GuiFieldValue[] GetServiceProvider(string id)
        {
            return s.GetServiceProvider(credentials, id);
        }


        public static bool CreateServiceProvider(string name, string comments, string type, GuiFieldValue[] data)
        {
            insertNameComments(name, comments, ref data);

            return s.CreateServiceProvider(credentials, type, data);
        }

        public static bool ModifyServiceProvider(string name, string comments, string id, GuiFieldValue[] data)
        {
            insertNameComments(name, comments, ref data);

            return s.ModifyServiceProvider(credentials, id, data);
        }

        public static bool RemoveServiceProvider(string id)
        {
            return s.RemoveServiceProvider(credentials, id);
        }

        public static ServiceType[] GetOffersFromServiceProvider(string type)
        {
            return s.GetOffersFromServiceProvider(credentials, type);
        }

        public static ResultTest testServiceProvider(string type, GuiFieldValue[] data)
        {
            return s.TestServiceProvider(credentials, type, data);
        }

        public static string CheckServiceProvider(string id)
        {
            return s.CheckServiceProvider(credentials, id);
        }

        // Services related methods
        public static Service[] GetServices(string idParent)
        {
            return s.GetServices(credentials,idParent);
        }

        public static Service[] GetAllServices()
        {
            return s.GetAllServices(credentials);
        }

        public static GuiField[] GetServiceGui(string idParent, string type)
        {
            try
            {
                return s.GetServiceGui(credentials, idParent, type);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message, "Exception invoking getServiceGui!!!");
                return null;
            }
        }

        public static GuiFieldValue[] GetService(string id)
        {
            return s.GetService(credentials, id);
        }

        public static bool CreateService(string idParent, string name, string comments, string type, GuiFieldValue[] data)
        {
            insertNameComments(name, comments, ref data);

            return s.CreateService(credentials, idParent, type, data);
        }

        public static bool ModifyService(string name, string comments, string id, GuiFieldValue[] data)
        {
            insertNameComments(name, comments, ref data);

            return s.ModifyService(credentials, id, data);
        }

        public static bool RemoveService(string id)
        {
            return s.RemoveService(credentials, id);
        }


        // Login related

        public static SimpleInfo[] GetAdminAuths(string host, bool https)
        {
            server = https ? "https" : "http";
            server += "://" + host;
            string url = server + "/xmlrpc";
            try
            {
                Initialize(url);
                return s.GetAdminAuths(UdsAdmin.Properties.Settings.Default.Locale);
            }
            catch (Exception e)
            {
                throw new exceptions.CommunicationException("Can't connect to server " + e.Message);
            }
        }

        public static void Login(string username, string password, string idAuth)
        {
            LoginData login = s.Login(username, password, idAuth, UdsAdmin.Properties.Settings.Default.Locale);
            credentials = login.credentials;
            if (credentials == "")
                throw new exceptions.AuthenticationException("Invalid username os password");
            Version v = Assembly.GetExecutingAssembly().GetName().Version;
            string executingVersion = v.Major.ToString() + "." +
                v.Minor.ToString() + "." + v.Build.ToString();
            if( executingVersion != login.versionRequired )
                throw new exceptions.NewVersionRequiredException("New version required", login.url);
            isAdmin = login.isAdmin;
            return;

        }

        public static string Logout()
        {
            string ret = "";
            if (s != null)
                try
                {
                    ret = s.Logout(credentials);
                    credentials = "";
                    s = null;
                }
                catch (Exception)
                {
                    // If credentials are not valid, or we can't reach server, we are exiting so we don't care :-)
                }
            return ret;
        }

        // Authenticators
        public static AuthenticatorType[] GetAuthenticatorsTypes()
        {
            try
            {
                return s.GetAuthenticatorsTypes(credentials);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message);
            }
            return null;
        }

        public static AuthenticatorType GetAuthenticatorType(string id)
        {
            return s.GetAuthenticatorType(credentials, id);
        }

        public static Authenticator[] GetAuthenticators()
        {
            return s.GetAuthenticators(credentials);
        }

        public static GuiField[] GetAuthenticatorGui(string type)
        {
            try
            {
                return s.GetAuthenticatorGui(credentials, type);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message, "Exception invoking getAuthenticatorGui!!!");
                return null;
            }

        }

        public static GuiFieldValue[] GetAuthenticator(string id)
        {
            return s.GetAuthenticator(credentials, id);
        }

        public static Group[] GetAuthenticatorGroups(string id)
        {
            return s.GetAuthenticatorGroups(credentials, id);
        }

        public static bool CreateAuthenticator(string name, string comments, string type, int priority, GuiFieldValue[] data)
        {
            insertNameCommentsPriority(name, comments, priority, ref data);

            return s.CreateAuthenticator(credentials, type, data);
        }

        public static bool ModifyAuthenticator(string name, string comments, int priority, string id, GuiFieldValue[] data)
        {
            insertNameCommentsPriority(name, comments, priority, ref data);

            return s.ModifyAuthenticator(credentials, id, data);
        }

        public static bool RemoveAuthenticator(string id)
        {
            return s.RemoveAuthenticator(credentials, id);
        }

        public static ResultTest TestAuthenticator(string type, GuiFieldValue[] data)
        {
            return s.TestAuthenticator(credentials, type, data);
        }

        public static string CheckAuthenticator(string id)
        {
            return s.CheckAuthenticator(credentials, id);
        }

        public static SimpleInfo[] SearchAuthenticator(string id, bool searchUser, string srchString)
        {
            return s.SearchAuthenticator(credentials, id, searchUser, srchString);
        }

        // Authenticators, groups related methods
        public static Group[] GetGroups(string idParent)
        {
            return s.GetGroups(credentials, idParent);
        }


        public static Group GetGroup(string id)
        {
            return s.GetGroup(credentials, id);
        }

        public static bool CreateGroup(Group grp)
        {
             return s.CreateGroup(credentials, grp);
        }

        public static bool ChangeGroupsState(string[] ids, bool newState)
        {
            return s.ChangeGroupsState(credentials, ids, newState);
        }

        public static bool RemoveGroups(string[] ids)
        {
            return s.RemoveGroups(credentials, ids);
        }

        // Authenticators, users related methods
        public static User[] GetUsers(string idParent)
        {
            return s.GetUsers(credentials, idParent);
        }

        public static User GetUser(string id)
        {
            return s.GetUser(credentials, id);
        }

        public static Group[] GetUserGroups(string id)
        {
            try
            {
                return s.GetUserGroups(credentials, id);
            }
            catch (System.Net.WebException e)
            {
                MessageBox.Show(e.Message, "Exception invoking getUserGroups!!!");
                return null;
            }

        }

        public static bool ChangeUsersState(string[] ids, string newState)
        {
            return s.ChangeUsersState(credentials, ids, newState);
        }

        public static bool RemoveUsers(string[] ids)
        {
            return s.RemoveUsers(credentials, ids);
        }

        public static bool CreateUser(User usr)
        {
            return s.CreateUser(credentials, usr);
        }


        public static bool ModifyUser(User user)
        {
            return s.ModifyUser(credentials, user);
        }

        public static PrefGroup[] GetPrefsForUser(string id)
        {
            return s.GetPrefsForUser(credentials, id);
        }


        public static bool SetPrefsForUser(string id, GuiFieldValue[] data)
        {
            return s.SetPrefsForUser(credentials, id, data);
        }

        // OS Manager Related methods
        public static OSManagerType[] GetOSManagersTypes()
        {
            try
            {
                return s.GetOSManagersTypes(credentials);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message);
            }
            return null;
        }

        public static OSManager[] GetOSManagers()
        {
            return s.GetOSManagers(credentials);
        }

        public static GuiField[] GetOSManagerGui(string type)
        {
            try
            {
                return s.GetOSManagerGui(credentials, type);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message, "Exception invoking GetOSManagerGui!!!");
                return null;
            }

        }

        public static GuiFieldValue[] GetOSManager(string id)
        {
            return s.GetOSManager(credentials, id);
        }


        public static bool CreateOSManager(string name, string comments, string type, GuiFieldValue[] data)
        {
            insertNameComments(name, comments, ref data);

            return s.CreateOSManager(credentials, type, data);
        }

        public static bool ModifyOSManager(string name, string comments, string id, GuiFieldValue[] data)
        {
            insertNameComments(name, comments, ref data);

            return s.ModifyOSManager(credentials, id, data);
        }

        public static bool RemoveOSManager(string id)
        {
            return s.RemoveOSManager(credentials, id);
        }

        public static ResultTest TestOsManager(string type, GuiFieldValue[] data)
        {
            return s.TestOsManager(credentials, type, data);
        }

        public static string CheckOSManager(string id)
        {
            return s.CheckOSManager(credentials, id);
        }

        // Transports Related methods
        public static TransportType[] GetTransportsTypes()
        {
            try
            {
                return s.GetTransportsTypes(credentials);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message);
            }
            return null;
        }

        public static Transport[] GetTransports()
        {
            return s.GetTransports(credentials);
        }

        public static GuiField[] GetTransportGui(string type)
        {
            try
            {
                return s.GetTransportGui(credentials, type);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message, "Exception invoking GetTransportGui!!!");
                return null;
            }

        }

        public static GuiFieldValue[] GetTransport(string id)
        {
            return s.GetTransport(credentials, id);
        }


        public static string CreateTransport(string name, string comments, int priority, bool positiveNets, string type, GuiFieldValue[] data)
        {
            insertNameCommentsPriorityNet(name, comments, priority, positiveNets, ref data);

            return s.CreateTransport(credentials, type, data);
        }

        public static bool ModifyTransport(string name, string comments, int priority, bool positiveNets, string id, GuiFieldValue[] data)
        {
            insertNameCommentsPriorityNet(name, comments, priority, positiveNets, ref data);

            return s.ModifyTransport(credentials, id, data);
        }

        public static bool RemoveTransport(string id)
        {
            return s.RemoveTransport(credentials, id);
        }

        public static string CheckTransport(string id)
        {
            return s.CheckTransport(credentials, id);
        }

        // Networks (for transports) Related methods
        public static Network[] GetNetworks()
        {
            return s.GetNetworks(credentials);
        }

        public static string[] GetNetworksForTransport(string id)
        {
            return s.getNetworksForTransport(credentials, id);
        }

        public static bool SetNetworksForTransport(string id, string[] networks)
        {
            return s.setNetworksForTransport(credentials, id, networks);
        }

        public static Network GetNetwork(string id)
        {
            return s.GetNetwork(credentials, id);
        }

        public static bool CreateNetwork(Network net)
        {
            return s.CreateNetwork(credentials, net);
        }

        public static bool ModifyNetwork(Network net)
        {
            return s.ModifyNetwork(credentials, net);
        }

        public static bool RemoveNetworks(string[] ids)
        {
            return s.RemoveNetworks(credentials, ids);
        }


        // Deployed service related
        public static DeployedService[] GetDeployedServices(bool all = false)
        {
            return s.GetDeployedServices(credentials, all);
        }

        public static DeployedService GetDeployedService(string id)
        {
            return s.GetDeployedService(credentials, id);
        }

        public static bool RemoveDeployedService(string id)
        {
            return s.RemoveDeployedService(credentials, id);
        }

        public static string CreateDeployedService(DeployedService deployedService)
        {
            return s.CreateDeployedService(credentials, deployedService); 
        }

        public static bool ModifyDeployedService(DeployedService deployedService)
        {
            return s.ModifyDeployedService(credentials, deployedService);
        }

        public static Group[] GetGroupsAssignedToDeployedService(string deployedServiceId)
        {
            return s.GetGroupsAssignedToDeployedService(credentials, deployedServiceId);
        }

        public static bool AssignGroupToDeployedService(string deployedServiceId, string groupId)
        {
            return s.AssignGroupToDeployedService(credentials, deployedServiceId, groupId);
        }

        public static bool RemoveGroupsFromDeployedService(string deployedServiceId, string[] groupIds)
        {
            return s.RemoveGroupsFromDeployedService(credentials, deployedServiceId, groupIds);
        }

        public static Transport[] GetTransportsAssignedToDeployedService(string idDeployedService)
        {
            return s.GetTransportsAssignedToDeployedService(credentials, idDeployedService);
        }

        public static bool AssignTransportToDeployedService(string deployedServiceId, string groupId)
        {
            return s.AssignTransportToDeployedService(credentials, deployedServiceId, groupId);
        }

        public static bool RemoveTransportFromDeployedService(string deployedServiceId, string[] groupIds)
        {
            return s.RemoveTransportFromDeployedService(credentials, deployedServiceId, groupIds);
        }

        public static DeployedServicePublication[] getPublications(DeployedService deployedService)
        {
            return s.GetPublications(credentials, deployedService.id);
        }

        public static bool PublishDeployedService(DeployedService deployedService)
        {
            return s.PublishDeployedService(credentials, deployedService.id);
        }

        public static bool CancelPublication(string id)
        {
            return s.CancelPublication(credentials, id);
        }


        public static CachedDeployedService[] GetCachedDeployedServices(DeployedService deployedService)
        {
            return s.GetCachedDeployedServices(credentials, deployedService.id);
        }

        public static AssignedDeployedService[] GetAssignedDeployedServices(DeployedService deployedService)
        {
            return s.GetAssignedDeployedServices(credentials, deployedService.id);
        }

        public static AssignableDeployedService[] GetAssignableDeployedServices(string idParent)
        {
            return s.GetAssignableDeployedServices(credentials, idParent);
        }

        public static bool AssignDeployedService(string idParent, string idDeployedUserService, string idUser)
        {
            return s.AssignDeployedService(credentials, idParent, idDeployedUserService, idUser);
        }

        public static bool RemoveUserService(string[] ids)
        {
            return s.RemoveUserService(credentials, ids);
        }

        public static string GetUserDeployedServiceError(string id)
        {
            return s.GetUserDeployedServiceError(credentials, id);
        }


        // Utility methods
        public static bool FlushCache()
        {
            return s.FlushCache(credentials);
        }

        public static Configuration[] GetConfiguration()
        {
            return s.GetConfiguration(credentials);
        }

        public static bool UpdateConfiguration(Configuration[] configuration)
        {
            return s.UpdateConfiguration(credentials, configuration);
        }

        // Calbacks

        public static GuiFieldValue[] InvokeChooseCallback(string name, GuiFieldValue[] parameters)
        {
            try
            {
                return s.InvokeChooseCallback(credentials, name, parameters);
            }
            catch (Exception e)
            {
                MessageBox.Show(e.Message, "Exception invoking getServiceGui!!!");
                return null;
            }

        }

    }
}
