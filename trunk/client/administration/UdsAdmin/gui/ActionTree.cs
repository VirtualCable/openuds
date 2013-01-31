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
using System.Drawing;

namespace UdsAdmin.gui
{
    class ActionTree
    {
        // Plurar forms must be same literals as designated in actionTree in MainForm
        public const string SERVICES_PROVIDERS = "ServicesProviders";
        public const string SERVICE_PROVIDER = "ServiceProvider";
        public const string DEPLOYED_SERVICES = "DeployedServices";
        public const string DEPLOYED_SERVICE = "DeployedService";
        public const string AUTHENTICATORS = "Authenticators";
        public const string AUTHENTICATOR = "Authenticator";
        public const string OS_MANAGERS = "OSManagers";
        public const string OS_MANAGER = "OSManager";
        public const string CONNECTIVITY = "Connectivity";
        public const string TRANSPORTS = "Transports";
        public const string TRANSPORT = "Transport";
        public const string NETWORKS = "Networks";
        public const string SERVICES = "Services";
        public const string SERVICE = "Service";
        public const string USERS = "Users";
        public const string GROUPS = "Groups";
        public const string ALLOWED_GROUPS = "AllowGroups";
        public const string ASSIGNED_SERVICES = "AssignService";
        public const string ASSIGNED_TRANSPORTS = "AssignedTransports";
        public const string PUBLICATIONS = "Deployments";
        public const string CACHE = "Cache";


        public const string DIMMED_OUT = "_2";

        public const float UNSELECTED_OPACITY = 0.8f;

        public const string NEW_ACTION = "new";
        public const string MODIFY_ACTION = "modify";
        public const string DELETE_ACTION = "delete";
        public const string CHECK_ACTION = "test";
        public const string PUBLISH_ACTION = "publish";

        private static Dictionary<string, xmlrpc.ServiceType[]> stCache = new Dictionary<string, xmlrpc.ServiceType[]>();

        static public void FillServicesProviders(TreeNode node, EventHandler action)
        {
            ImageList lst = node.TreeView.ImageList;
            node.Nodes.Clear();
            xmlrpc.ServiceProvider[] providers = xmlrpc.UdsAdminService.GetServiceProviders();
            foreach (xmlrpc.ServiceProvider prov in providers)
            {
                // We check if already knows about this type
                if (!stCache.ContainsKey(prov.type))
                    stCache.Add(prov.type, xmlrpc.UdsAdminService.GetOffersFromServiceProvider(prov.type));

                xmlrpc.ServiceType[] offers = stCache[prov.type];

                // Add Icons of service types to image list if they don't already exists
                foreach (xmlrpc.ServiceType st in offers)
                {
                    if (!lst.Images.ContainsKey(st.type))
                    {
                        lst.Images.Add(st.type + DIMMED_OUT, Helpers.SetImageOpacity(Helpers.ImageFromBase64(st.icon), UNSELECTED_OPACITY));
                        lst.Images.Add(st.type, Helpers.ImageFromBase64(st.icon));
                    }
                }

                // Menu for right-click on service provider
                ContextMenuStrip menu = MenusManager.ServicesMenu(action, offers, true);

                TreeNode sp = new TreeNode(prov.name);
                sp.Name = SERVICE_PROVIDER;
                sp.Tag = prov;   // We keep provider at tag, so we can easyly modify/delete or add new services for that provider
                sp.ToolTipText = prov.typeName + ".\n" + prov.comments;
                sp.ImageKey = prov.type + DIMMED_OUT;
                sp.SelectedImageKey = prov.type;
                sp.ContextMenuStrip = menu;

                // Meno for right-click on "Services" inside service provider
                ContextMenuStrip menu2 = MenusManager.ServicesMenu(action, offers, false);

                TreeNode spChild = new TreeNode(Strings.services);
                spChild.Name = SERVICES;
                spChild.ToolTipText = "";
                spChild.ImageKey = SERVICES + DIMMED_OUT;
                spChild.SelectedImageKey = SERVICES;
                spChild.ContextMenuStrip = menu2;
                sp.Nodes.Add(spChild);

                // Add to tree
                node.Nodes.Add(sp);
            }
        }

        static public void FillServices(TreeNode node, EventHandler action)
        {
            TreeNode servicesTree = node.Nodes[SERVICES];
            xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)node.Tag;
            xmlrpc.Service[] services = xmlrpc.UdsAdminService.GetServices(sp.id);

            servicesTree.Nodes.Clear();
            foreach (xmlrpc.Service s in services)
            {
                TreeNode se = new TreeNode(s.name);
                se.Name = SERVICE;
                se.Tag = s;
                se.ToolTipText = s.typeName + ".\n" + s.comments;
                se.ImageKey = s.type + DIMMED_OUT;
                se.SelectedImageKey = s.type;
                xmlrpc.ServiceType[] offers = stCache[sp.type];
                xmlrpc.ServiceType type = new xmlrpc.ServiceType();
                foreach( xmlrpc.ServiceType st in offers )
                {
                    if( st.type == s.type )
                    {
                        type = st;
                        break;
                    }
                }
                se.ContextMenuStrip = MenusManager.ServiceMenu(action, s, type);

                servicesTree.Nodes.Add(se);
            }
        }

        static public void FillAuthenticators(TreeNode node, xmlrpc.AuthenticatorType[] authsTypes, EventHandler actionOnAuthClick, EventHandler actionOnUsersGroupsClick)
        {
            ImageList lst = node.TreeView.ImageList;
            node.Nodes.Clear();
            xmlrpc.Authenticator[] auths = xmlrpc.UdsAdminService.GetAuthenticators();

            ContextMenuStrip newMenu = MenusManager.TreeUsersGroupsMenu(actionOnUsersGroupsClick);

            foreach (xmlrpc.Authenticator auth in auths)
            {
                // Menu for right-click on service provider
                ContextMenuStrip menu = MenusManager.AuthMenu(actionOnAuthClick);

                // authenticator type
                xmlrpc.AuthenticatorType authType = gui.ActionTree.authType(auth, authsTypes);

                TreeNode a = new TreeNode(auth.name);
                a.Name = AUTHENTICATOR;
                a.Tag = auth;   // We keep provider at tag, so we can easyly modify/delete or add new services for that provider
                a.ToolTipText = auth.typeName + ".\n" + auth.comments;
                a.ImageKey = auth.type + DIMMED_OUT;
                a.SelectedImageKey = auth.type;
                a.ContextMenuStrip = menu;

                TreeNode users = new TreeNode(Strings.users);
                users.Name = USERS;
                users.ToolTipText = Strings.manageUsers;
                users.ImageKey = USERS + DIMMED_OUT;
                users.SelectedImageKey = USERS;
                if( authType.canCreateUsers )
                    users.ContextMenuStrip = newMenu;

                // Udpate users for this authenticator

                a.Nodes.Add(users);

                TreeNode groups = new TreeNode(Strings.groups);
                groups.Name = GROUPS;
                groups.ToolTipText = Strings.manageGroups;
                groups.ImageKey = GROUPS + DIMMED_OUT;
                groups.SelectedImageKey = GROUPS;
                groups.ContextMenuStrip = newMenu;
                a.Nodes.Add(groups);


                // Add to tree
                node.Nodes.Add(a);
            }
        }

        static public void FillOSManagers(TreeNode node, EventHandler action)
        {
            xmlrpc.OSManager[] osManagers = xmlrpc.UdsAdminService.GetOSManagers();

            node.Nodes.Clear();
            foreach (xmlrpc.OSManager osm in osManagers)
            {
                TreeNode se = new TreeNode(osm.name);
                se.Name = OS_MANAGER;
                se.Tag = osm;
                se.ToolTipText = osm.typeName + ".\n" + osm.comments;
                se.ImageKey = osm.type + DIMMED_OUT;
                se.SelectedImageKey = osm.type;
                se.ContextMenuStrip = MenusManager.OSManagerMenu(action, osm);

                node.Nodes.Add(se);
            }
        }

        static public void FillTransports(TreeNode transNode, EventHandler actionTransports)
        {
            xmlrpc.Transport[] transports = xmlrpc.UdsAdminService.GetTransports();


            transNode.Nodes.Clear();
            foreach (xmlrpc.Transport trans in transports)
            {
                TreeNode se = new TreeNode(trans.name);
                se.Name = TRANSPORT;
                se.Tag = trans;
                se.ToolTipText = trans.typeName + ".\n" + trans.comments;
                se.ImageKey = trans.type + DIMMED_OUT;
                se.SelectedImageKey = trans.type;
                se.ContextMenuStrip = MenusManager.TransportMenu(actionTransports, trans);

                transNode.Nodes.Add(se);
            }


        }

        static public void FillDeployedServices(TreeNode node, EventHandler action)
        {
            xmlrpc.DeployedService[] depServices = xmlrpc.UdsAdminService.GetDeployedServices();

            node.Nodes.Clear();
            foreach (xmlrpc.DeployedService ds in depServices)
            {
                TreeNode se = new TreeNode(ds.name);
                se.Name = DEPLOYED_SERVICE;
                se.Tag = ds;
                se.ToolTipText = ds.comments;
                se.ImageKey = DEPLOYED_SERVICE + DIMMED_OUT;
                se.SelectedImageKey = DEPLOYED_SERVICE;
                se.ContextMenuStrip = MenusManager.DeployedServiceMenu(action, ds);

                // Add constant child nodes, that are Allowed Groups, Deployments (this only if needed), Assigned Services & Cache (also if needed)
                TreeNode a = new TreeNode(Strings.assignedServices);
                a.Name = ASSIGNED_SERVICES; a.Tag = ds; a.ToolTipText = Strings.assignedServicesToolTip;
                a.ImageKey = ASSIGNED_SERVICES + DIMMED_OUT; a.SelectedImageKey = ASSIGNED_SERVICES;
                se.Nodes.Add(a);

                if (ds.info.usesCache)
                {
                    a = new TreeNode(Strings.cache);
                    a.Name = CACHE; a.Tag = ds; a.ToolTipText = Strings.cacheServicesToolTip;
                    a.ImageKey = CACHE + DIMMED_OUT; a.SelectedImageKey = CACHE;
                    se.Nodes.Add(a);
                }

                if (ds.info.mustAssignManually == false)
                {
                    a = new TreeNode(Strings.allowedGroups);
                    a.Name = ALLOWED_GROUPS; a.Tag = ds; a.ToolTipText = Strings.allowedGroupsToolTip;
                    a.ImageKey = GROUPS + DIMMED_OUT; a.SelectedImageKey = GROUPS;
                    se.Nodes.Add(a);
                }

                // Transports are always associated with deployed services
                a = new TreeNode(Strings.transports);
                a.Name = ASSIGNED_TRANSPORTS; a.Tag = ds; a.ToolTipText = "";
                a.ImageKey = TRANSPORTS + DIMMED_OUT; a.SelectedImageKey = TRANSPORTS;
                se.Nodes.Add(a);

                if (ds.info.needsPublication)
                {
                    a = new TreeNode(Strings.publications);
                    a.Name = PUBLICATIONS; a.Tag = ds; a.ToolTipText = Strings.publicationsToolTip;
                    a.ImageKey = PUBLICATIONS + DIMMED_OUT; a.SelectedImageKey = PUBLICATIONS;
                    // Now the menu for publication
                    a.ContextMenuStrip = MenusManager.PublicationMenu(action);
                    se.Nodes.Add(a);
                }

                node.Nodes.Add(se);
            }
        }

        static public void InitializeImageList(TreeView tree)
        {
            tree.ImageList = new ImageList();

            tree.ImageList.Images.Add(SERVICES_PROVIDERS, Images.serviceProviders16);
            tree.ImageList.Images.Add(SERVICES_PROVIDERS + DIMMED_OUT, Helpers.SetImageOpacity(Images.serviceProviders16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(DEPLOYED_SERVICES, Images.deployedServices16);
            tree.ImageList.Images.Add(DEPLOYED_SERVICES + DIMMED_OUT, Helpers.SetImageOpacity(Images.deployedServices16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(AUTHENTICATORS, Images.authenticators16);
            tree.ImageList.Images.Add(AUTHENTICATORS + DIMMED_OUT, Helpers.SetImageOpacity(Images.authenticators16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(OS_MANAGERS, Images.osmanagers16);
            tree.ImageList.Images.Add(OS_MANAGERS + DIMMED_OUT, Helpers.SetImageOpacity(Images.osmanagers16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(TRANSPORTS, Images.transports16);
            tree.ImageList.Images.Add(TRANSPORTS + DIMMED_OUT, Helpers.SetImageOpacity(Images.transports16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(SERVICES, Images.services16);
            tree.ImageList.Images.Add(SERVICES + DIMMED_OUT, Helpers.SetImageOpacity(Images.services16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(DEPLOYED_SERVICE, Images.deployedService16);
            tree.ImageList.Images.Add(DEPLOYED_SERVICE + DIMMED_OUT, Helpers.SetImageOpacity(Images.deployedService16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(ASSIGNED_SERVICES, Images.assignedServices16);
            tree.ImageList.Images.Add(ASSIGNED_SERVICES + DIMMED_OUT, Helpers.SetImageOpacity(Images.assignedServices16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(CACHE, Images.cache16);
            tree.ImageList.Images.Add(CACHE + DIMMED_OUT, Helpers.SetImageOpacity(Images.cache16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(PUBLICATIONS, Images.publications16);
            tree.ImageList.Images.Add(PUBLICATIONS + DIMMED_OUT, Helpers.SetImageOpacity(Images.publications16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(USERS, Images.users16);
            tree.ImageList.Images.Add(USERS + DIMMED_OUT, Helpers.SetImageOpacity(Images.users16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(GROUPS, Images.groups16);
            tree.ImageList.Images.Add(GROUPS + DIMMED_OUT, Helpers.SetImageOpacity(Images.groups16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(NETWORKS, Images.networks16);
            tree.ImageList.Images.Add(NETWORKS + DIMMED_OUT, Helpers.SetImageOpacity(Images.networks16, UNSELECTED_OPACITY));

            tree.ImageList.Images.Add(CONNECTIVITY, Images.connectivity16);
            tree.ImageList.Images.Add(CONNECTIVITY + DIMMED_OUT, Helpers.SetImageOpacity(Images.connectivity16, UNSELECTED_OPACITY));
        }

        static public void addTypesImages(TreeView tree, xmlrpc.ServiceProviderType[] providersTypes, 
            xmlrpc.AuthenticatorType[] authsTypes, xmlrpc.OSManagerType[] osManagerTypes, xmlrpc.TransportType[] transportTypes)
        {
            ImageList lst = tree.ImageList;
            foreach (xmlrpc.ServiceProviderType spt in providersTypes)
            {
                lst.Images.Add(spt.type, Helpers.ImageFromBase64(spt.icon));
                lst.Images.Add(spt.type + DIMMED_OUT, Helpers.SetImageOpacity(Helpers.ImageFromBase64(spt.icon), UNSELECTED_OPACITY));
            }
            foreach (xmlrpc.AuthenticatorType at in authsTypes)
            {
                lst.Images.Add(at.type, Helpers.ImageFromBase64(at.icon));
                lst.Images.Add(at.type + DIMMED_OUT, Helpers.SetImageOpacity(Helpers.ImageFromBase64(at.icon), UNSELECTED_OPACITY));
            }
            foreach (xmlrpc.OSManagerType osm in osManagerTypes)
            {
                lst.Images.Add(osm.type, Helpers.ImageFromBase64(osm.icon));
                lst.Images.Add(osm.type + DIMMED_OUT, Helpers.SetImageOpacity(Helpers.ImageFromBase64(osm.icon), UNSELECTED_OPACITY));
            }
            foreach (xmlrpc.TransportType trans in transportTypes)
            {
                lst.Images.Add(trans.type, Helpers.ImageFromBase64(trans.icon));
                lst.Images.Add(trans.type + DIMMED_OUT, Helpers.SetImageOpacity(Helpers.ImageFromBase64(trans.icon), UNSELECTED_OPACITY));
            }

        }

        static private string getKey(TreeNode node)
        {
            switch (node.Name)
            {
                case USERS:
                    {
                        xmlrpc.Authenticator auth = (xmlrpc.Authenticator)(node.Parent.Tag);
                        return USERS + auth.id;
                    }
                case GROUPS:
                    {
                        xmlrpc.Authenticator auth = (xmlrpc.Authenticator)(node.Parent.Tag);
                        return GROUPS + auth.id;
                    }
                case SERVICES:
                    {
                        xmlrpc.ServiceProvider prov = (xmlrpc.ServiceProvider)(node.Parent.Tag);
                        return SERVICE_PROVIDER + prov.id;
                    }
                case SERVICE:
                    {
                        xmlrpc.Service serv = (xmlrpc.Service)node.Tag;
                        return SERVICE + serv.id;
                    }
                case SERVICE_PROVIDER:
                    {
                        xmlrpc.ServiceProvider prov = (xmlrpc.ServiceProvider)(node.Tag);
                        return SERVICE_PROVIDER + prov.id;
                    }
                case DEPLOYED_SERVICE:
                    {
                        xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(node.Tag);
                        return DEPLOYED_SERVICE + ds.id;
                    }
                case CACHE:
                    {
                        xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(node.Tag);
                        return CACHE + ds.id;
                    }
                case ASSIGNED_SERVICES:
                    {
                        xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(node.Tag);
                        return ASSIGNED_SERVICES + ds.id;
                    }
                case ASSIGNED_TRANSPORTS:
                    {
                        xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(node.Tag);
                        return ASSIGNED_TRANSPORTS + ds.id;
                    }
                case PUBLICATIONS:
                    {
                        xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(node.Tag);
                        return PUBLICATIONS + ds.id;
                    }
                case ALLOWED_GROUPS:
                    {
                        xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(node.Tag);
                        return ALLOWED_GROUPS + ds.id;
                    }

                default:
                    return node.Name;
            }
        }

        static public xmlrpc.AuthenticatorType authType(xmlrpc.Authenticator auth, xmlrpc.AuthenticatorType[] types)
        {
            xmlrpc.AuthenticatorType type = new xmlrpc.AuthenticatorType();
            foreach (xmlrpc.AuthenticatorType a in types)
            {
                if (a.type == auth.type)
                {
                    type = a;
                    break;
                }
            }
            return type;
        }

        static public void showAssociatedPanel(SplitterPanel panel, TreeView view, forms.MainForm mainForm)
        {
            TreeNode selected = view.SelectedNode;

            // Hides all visible controls
            foreach (Control ctrl in panel.Controls)
                ctrl.Hide();

            string key = getKey(selected);
            if (panel.Controls.ContainsKey(key))
                panel.Controls[key].Show();
            else // Don't exists, creates a new panel associated with the tree view and initializes it
            {
                Control ctrl;
                switch( selected.Name )
                {
                    case USERS:
                        {
                            xmlrpc.Authenticator auth = (xmlrpc.Authenticator)(selected.Parent.Tag);
                            xmlrpc.AuthenticatorType type = authType(auth, mainForm._authenticatorsTypes);
                            ctrl = new controls.panel.UsersPanel(auth, type);
                            break;
                        }
                    case GROUPS:
                        {
                            xmlrpc.Authenticator auth = (xmlrpc.Authenticator)(selected.Parent.Tag);
                            xmlrpc.AuthenticatorType type = authType(auth, mainForm._authenticatorsTypes);
                            ctrl = new controls.panel.GroupsPanel(auth, type);
                            break;
                        }
                    case TRANSPORTS:
                        {
                            ctrl = new controls.panel.TransportsPanel();
                            break;
                        }
                    case OS_MANAGERS:
                        {
                            ctrl = new controls.panel.OsManagersPanel();
                            break;
                        }
                    case AUTHENTICATORS:
                        {
                            ctrl = new controls.panel.AuthsPanel();
                            break;
                        }
                    case SERVICES_PROVIDERS:
                        {
                            ctrl = new controls.panel.ServiceProvidersPanel();
                            break;
                        }
                    case SERVICE_PROVIDER:
                        {
                            ctrl = new controls.panel.ServicesPanel(((xmlrpc.ServiceProvider)selected.Tag));
                            break;
                        }
                    case SERVICES:
                        {
                            ctrl = new controls.panel.ServicesPanel(((xmlrpc.ServiceProvider)selected.Parent.Tag));
                            break;
                        }
                    case DEPLOYED_SERVICE:
                        {
                            xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(selected.Tag);
                            ctrl = new controls.panel.DeployedServicePanel(ds);
                            break;
                        }
                    case DEPLOYED_SERVICES:
                        {
                            ctrl = new controls.panel.DeployedServicesPanel();
                            break;
                        }
                    case CACHE:
                        {
                            xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(selected.Tag);
                            ctrl = new controls.panel.DeployedPanel(ds, true);
                            break;
                        }
                    case ASSIGNED_SERVICES:
                        {
                            xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(selected.Tag);
                            ctrl = new controls.panel.DeployedPanel(ds, false);
                            break;
                        }
                    case ASSIGNED_TRANSPORTS:
                        {
                            xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(selected.Tag);
                            ctrl = new controls.panel.TransportsPanel(ds);
                            break;
                        }
                    case PUBLICATIONS:
                        {
                            xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(selected.Tag);
                            ctrl = new controls.panel.PublicationsPanel(ds);
                            break;
                        }
                    case ALLOWED_GROUPS:
                        {
                            xmlrpc.DeployedService ds = (xmlrpc.DeployedService)(selected.Tag);
                            ctrl = new controls.panel.DeployedGroupsPanel(ds);
                            break;
                        }
                    case NETWORKS:
                        {
                            ctrl = new controls.panel.NetworksPanel();
                            break;
                        }
                    default:
                        ctrl = new controls.panel.PanelEmpty("");
                        break;

                }
                ctrl.Name = key;
                ctrl.Dock = DockStyle.Fill;
                panel.Controls.Add(ctrl);
            }
        }

    }
}
