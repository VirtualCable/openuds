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
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Globalization;
using System.Threading;

namespace UdsAdmin.forms
{
    public partial class MainForm : Form
    {
        public xmlrpc.ServiceProviderType[] _serviceProvidersTypes = null;
        public xmlrpc.AuthenticatorType[] _authenticatorsTypes = null;
        public xmlrpc.OSManagerType[] _osManagersTypes = null;
        public xmlrpc.TransportType[] _transportTypes = null;

        public static MainForm form = null;

        private Icon getIcon( xmlrpc.BaseType[] bas, string type)
        {
            Icon icon = null;
            foreach (xmlrpc.BaseType bt in bas)
            {
                if (bt.type == type)
                {
                    icon = gui.Helpers.IconFromBase64(bt.icon);
                    break;
                }
            }
            return icon;
        }

        public MainForm()
        {
            InitializeComponent();
            form = this;
            Text = Strings.titleMain;
        }

        private void MainForm_Load(object sender, EventArgs e)
        {
            // Adjust split position
            splitContainer1.SplitterDistance = 200;

            // Saves the providers known by this server
            _serviceProvidersTypes = xmlrpc.UdsAdminService.GetServiceProvidersTypes();
            _authenticatorsTypes = xmlrpc.UdsAdminService.GetAuthenticatorsTypes();
            _osManagersTypes = xmlrpc.UdsAdminService.GetOSManagersTypes();
            _transportTypes = xmlrpc.UdsAdminService.GetTransportsTypes();

            // Initialize the base images for the action tree
            gui.ActionTree.InitializeImageList(treeActions);
            // Fill the types of servers for service providers, authenticators
            gui.ActionTree.addTypesImages(treeActions, _serviceProvidersTypes, _authenticatorsTypes, _osManagersTypes, _transportTypes);

            // Menus for top level items
            ContextMenuStrip servicesProvidersContextMenu = new System.Windows.Forms.ContextMenuStrip();
            ContextMenuStrip authenticatorsContextMenu = new System.Windows.Forms.ContextMenuStrip();
            ContextMenuStrip osManagersContextMenu = new System.Windows.Forms.ContextMenuStrip();
            ContextMenuStrip transportsContextMenu = new System.Windows.Forms.ContextMenuStrip();
            ContextMenuStrip deployedServiceContextMenu = new System.Windows.Forms.ContextMenuStrip();
            ContextMenuStrip networkContexMenu = new System.Windows.Forms.ContextMenuStrip();

            // Contextual menu for Services Providers
            ToolStripMenuItem newService = new ToolStripMenuItem(Strings.newItem);
            gui.MenusManager.InitProvidersMenu(newService, newServiceProviderMenu_Click, _serviceProvidersTypes);
            servicesProvidersContextMenu.Items.Add(newService);

            // Contextual menu for authenticators
            ToolStripMenuItem newAuth = new ToolStripMenuItem(Strings.newItem);
            gui.MenusManager.InitAuthenticatorsMenu(newAuth, newAuthenticatorMenu_Click, _authenticatorsTypes);
            authenticatorsContextMenu.Items.Add(newAuth);

            // Contextual menu for os managers
            ToolStripMenuItem newOSManager = new ToolStripMenuItem(Strings.newItem);
            gui.MenusManager.InitOSManagersMenu(newOSManager, newOSManagerMenu_Click, _osManagersTypes);
            osManagersContextMenu.Items.Add(newOSManager);

            // Contextual menu for transports
            ToolStripMenuItem newTransport = new ToolStripMenuItem(Strings.newItem);
            gui.MenusManager.InitTransportsMenu(newTransport, newTransportMenu_Click, _transportTypes);
            transportsContextMenu.Items.Add(newTransport);

            // Contextual menu for Deployed Services
            ToolStripMenuItem newDeployed = new ToolStripMenuItem(Strings.newItem);
            gui.MenusManager.InitDeployedServicesMenu(newDeployed, newDeployed_Click);
            deployedServiceContextMenu.Items.Add(newDeployed);

            // Contextual menu for Networks
            ToolStripMenuItem newNetwork = new ToolStripMenuItem(Strings.newItem);
            newNetwork.Click += newNetwork_Click;
            networkContexMenu.Items.Add(newNetwork);

            // Generate main tree
            treeActions.Nodes.Add(gui.ActionTree.SERVICES_PROVIDERS, Strings.serviceProviders, 
                gui.ActionTree.SERVICES_PROVIDERS + gui.ActionTree.DIMMED_OUT,  gui.ActionTree.SERVICES_PROVIDERS);
            treeActions.Nodes.Add(gui.ActionTree.AUTHENTICATORS, Strings.authenticators,
                gui.ActionTree.AUTHENTICATORS + gui.ActionTree.DIMMED_OUT,  gui.ActionTree.AUTHENTICATORS);
            treeActions.Nodes.Add(gui.ActionTree.OS_MANAGERS, Strings.osManagers,
                gui.ActionTree.OS_MANAGERS + gui.ActionTree.DIMMED_OUT, gui.ActionTree.OS_MANAGERS);

            treeActions.Nodes.Add(gui.ActionTree.CONNECTIVITY, Strings.connectivity,
                gui.ActionTree.CONNECTIVITY + gui.ActionTree.DIMMED_OUT, gui.ActionTree.CONNECTIVITY);
            treeActions.Nodes[gui.ActionTree.CONNECTIVITY].Nodes.Add(gui.ActionTree.TRANSPORTS, Strings.transports,
                gui.ActionTree.TRANSPORTS + gui.ActionTree.DIMMED_OUT, gui.ActionTree.TRANSPORTS);
            treeActions.Nodes[gui.ActionTree.CONNECTIVITY].Nodes.Add(gui.ActionTree.NETWORKS, Strings.networks,
                gui.ActionTree.NETWORKS + gui.ActionTree.DIMMED_OUT, gui.ActionTree.NETWORKS);

            treeActions.Nodes.Add(gui.ActionTree.DEPLOYED_SERVICES, Strings.deployedServices,
                gui.ActionTree.DEPLOYED_SERVICES + gui.ActionTree.DIMMED_OUT, gui.ActionTree.DEPLOYED_SERVICES);

            // Add context menus
            treeActions.Nodes[gui.ActionTree.SERVICES_PROVIDERS].ContextMenuStrip = servicesProvidersContextMenu;
            treeActions.Nodes[gui.ActionTree.AUTHENTICATORS].ContextMenuStrip = authenticatorsContextMenu;
            treeActions.Nodes[gui.ActionTree.OS_MANAGERS].ContextMenuStrip = osManagersContextMenu;

            treeActions.Nodes[gui.ActionTree.CONNECTIVITY].Nodes[gui.ActionTree.TRANSPORTS].ContextMenuStrip = transportsContextMenu;
            treeActions.Nodes[gui.ActionTree.CONNECTIVITY].Nodes[gui.ActionTree.NETWORKS].ContextMenuStrip = networkContexMenu;

            treeActions.Nodes[gui.ActionTree.DEPLOYED_SERVICES].ContextMenuStrip = deployedServiceContextMenu;

            updateServicesProvidersTree();
            updateAuthenticatorsTree();
            updateOSManagersTree();
            updateTransportsTree();
            updateDeployedServicesTree();
        }

        private void changeLangTo(string lang)
        {
            if (MessageBox.Show(Strings.changeLanguage, Strings.language, MessageBoxButtons.YesNo) == System.Windows.Forms.DialogResult.Yes)
            {
                UdsAdmin.Properties.Settings.Default.Locale = lang;
                //CultureInfo culture = new CultureInfo(UdsAdmin.Properties.Settings.Default.Locale);
                //Thread.CurrentThread.CurrentCulture = culture;
                //Thread.CurrentThread.CurrentUICulture = culture;

                //UdsAdmin.Properties.Settings.Default.Save(); done at Program.cs
            }
        }

        private void englishToolStripMenuItem_Click(object sender, EventArgs e)
        {
            changeLangTo("en-US");
        }

        private void spanishToolStripMenuItem_Click(object sender, EventArgs e)
        {
            changeLangTo("es-ES");
        }

        private void frenchToolStripMenuItem_Click(object sender, EventArgs e)
        {
            changeLangTo("fr-FR");
        }

        private void germanToolStripMenuItem_Click(object sender, EventArgs e)
        {
            changeLangTo("de-DE");
        }

        private void treeActions_AfterSelect(object sender, TreeViewEventArgs e)
        {
            if (treeActions.SelectedNode == null)
                return;
            try
            {
                gui.ActionTree.showAssociatedPanel(splitContainer1.Panel2, treeActions, this);
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
            catch (Exception ex2)
            {
                gui.UserNotifier.notifyError(ex2.Message);
            }

        }

        private void newServiceProviderMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            ServiceProviderForm dlg = new ServiceProviderForm(s.Text, s.Name, getIcon(_serviceProvidersTypes, s.Name));
            dlg.ShowDialog();
            updateServicesProvidersTree();
        }

        private void newAuthenticatorMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            AuthenticatorForm dlg = new AuthenticatorForm(s.Text, s.Name, getIcon(_authenticatorsTypes, s.Name));
            dlg.ShowDialog();
            updateAuthenticatorsTree();
        }

        private void newOSManagerMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            OSManagerForm dlg = new OSManagerForm(s.Text, s.Name, getIcon(_osManagersTypes, s.Name));
            dlg.ShowDialog();
            updateOSManagersTree();
        }

        private void newTransportMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            TransportForm dlg = new TransportForm(s.Text, s.Name, getIcon(_transportTypes, s.Name));
            dlg.ShowDialog();
            updateTransportsTree();
        }

        private void newDeployed_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            DeployedServiceForm dlg = new DeployedServiceForm();
            DialogResult res = dlg.ShowDialog();
            updateDeployedServicesTree();
        }

        private void treeActions_BeforeExpand(object sender, TreeViewCancelEventArgs e)
        {
            // We can do a constant refresh here, but i think better not, F5 must be enought
            /*if (e.Node.Name == gui.ActionTree.SERVICES_PROVIDERS)
                updateServicesProvidersTree();*/
            switch( e.Node.Name )
            {
                case gui.ActionTree.SERVICE_PROVIDER:
                    xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)e.Node.Tag;
                    updateServicesTree(sp.id);
                    break;
            }
        }

        private void serviceProviderContextMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;

            switch (s.Name)
            {
                case gui.ActionTree.NEW_ACTION:
                    {
                        // Selects the corresponding "Services" node
                        if( treeActions.SelectedNode.Name == gui.ActionTree.SERVICE_PROVIDER )
                            treeActions.SelectedNode = treeActions.SelectedNode.Nodes[gui.ActionTree.SERVICES];
                        treeActions.SelectedNode.Expand();
                        xmlrpc.ServiceType st = (xmlrpc.ServiceType)s.Tag;
                        xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)treeActions.SelectedNode.Parent.Tag;

                        ServiceForm dlg = new ServiceForm(sp.id, st.name, st.type, gui.Helpers.IconFromBase64(st.icon));
                        if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                            updateServicesTree(sp.id);
                        break;
                    }
                case gui.ActionTree.MODIFY_ACTION:
                    {
                        xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)treeActions.SelectedNode.Tag;
                        ServiceProviderForm dlg = new ServiceProviderForm(sp.typeName, sp.type, getIcon(_serviceProvidersTypes, sp.type));
                        dlg.setData(sp.name, sp.comments, sp.id, xmlrpc.UdsAdminService.GetServiceProvider(sp.id));
                        if( dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK )
                            updateServicesProvidersTree();
                        break;
                    }
                case gui.ActionTree.DELETE_ACTION:
                    {
                        try
                        {
                            if (MessageBox.Show(Strings.removeQuestion, Strings.serviceProviders, MessageBoxButtons.YesNo) == System.Windows.Forms.DialogResult.Yes)
                            {
                                xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)treeActions.SelectedNode.Tag;
                                xmlrpc.UdsAdminService.RemoveServiceProvider(sp.id);
                                updateServicesProvidersTree();
                            }
                        }
                        catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                        {
                            gui.UserNotifier.notifyRpcException(ex);
                        }

                        break;
                    }
                case gui.ActionTree.CHECK_ACTION:
                    {
                        xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)treeActions.SelectedNode.Tag;
                        MessageBox.Show(xmlrpc.UdsAdminService.CheckServiceProvider(sp.id));
                        break;
                    }
            }
        }

        private void AuthenticatorContextMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            switch (s.Name)
            {
                case gui.ActionTree.MODIFY_ACTION:
                    {
                        xmlrpc.Authenticator auth = (xmlrpc.Authenticator)treeActions.SelectedNode.Tag;
                        AuthenticatorForm dlg = new AuthenticatorForm(auth.typeName, auth.type, getIcon(_authenticatorsTypes, auth.type));
                        dlg.setData(auth.name, auth.comments, auth.id, auth.smallName, xmlrpc.UdsAdminService.GetAuthenticator(auth.id));
                        if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                            updateAuthenticatorsTree();
                        break;
                    }
                case gui.ActionTree.DELETE_ACTION:
                    {
                        xmlrpc.Authenticator auth = (xmlrpc.Authenticator)treeActions.SelectedNode.Tag;
                        xmlrpc.UdsAdminService.RemoveAuthenticator(auth.id);
                        updateAuthenticatorsTree();
                        break;
                    }
                case gui.ActionTree.CHECK_ACTION:
                    {
                        xmlrpc.Authenticator auth = (xmlrpc.Authenticator)treeActions.SelectedNode.Tag;
                        MessageBox.Show(xmlrpc.UdsAdminService.CheckAuthenticator(auth.id));
                        break;
                    }
            }
        }


        private void serviceContextMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;

            switch (s.Name)
            {
                case gui.ActionTree.MODIFY_ACTION:
                    {
                        xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)treeActions.SelectedNode.Parent.Parent.Tag;
                        xmlrpc.Service se = (xmlrpc.Service)treeActions.SelectedNode.Tag;
                        xmlrpc.ServiceType st = (xmlrpc.ServiceType)s.Tag;
                        ServiceForm dlg = new ServiceForm(sp.id, se.typeName, se.type, gui.Helpers.IconFromBase64(st.icon));
                        dlg.setData(se.name, se.comments, se.id, xmlrpc.UdsAdminService.GetService(se.id));
                        if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                            updateServicesTree(sp.id);
                        break;
                    }
                case gui.ActionTree.DELETE_ACTION:
                    {
                        try
                        {
                            if (MessageBox.Show(Strings.removeQuestion, Strings.services, MessageBoxButtons.YesNo) == System.Windows.Forms.DialogResult.Yes)
                            {
                                xmlrpc.Service ser = (xmlrpc.Service)treeActions.SelectedNode.Tag;
                                xmlrpc.UdsAdminService.RemoveService(ser.id);
                                updateServicesTree(ser.idParent);
                            }
                        }
                        catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                        {
                            gui.UserNotifier.notifyRpcException(ex);
                        }
                        break;
                    }
            }
        }

        private void osManagerContextMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            switch (s.Name)
            {
                case gui.ActionTree.MODIFY_ACTION:
                    {
                        xmlrpc.OSManager osm = (xmlrpc.OSManager)treeActions.SelectedNode.Tag;
                        OSManagerForm dlg = new OSManagerForm(osm.typeName, osm.type, getIcon(_osManagersTypes,osm.type));
                        dlg.setData(osm.name, osm.comments, osm.id, xmlrpc.UdsAdminService.GetOSManager(osm.id));
                        if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                            updateOSManagersTree();
                        break;
                    }
                case gui.ActionTree.DELETE_ACTION:
                    {
                        xmlrpc.OSManager osm = (xmlrpc.OSManager)treeActions.SelectedNode.Tag;
                        if (MessageBox.Show(Strings.removeQuestion, Strings.osManager, MessageBoxButtons.YesNo) == System.Windows.Forms.DialogResult.Yes)
                        {
                            try
                            {
                                xmlrpc.UdsAdminService.RemoveOSManager(osm.id);
                                updateOSManagersTree();
                            }
                            catch(  CookComputing.XmlRpc.XmlRpcFaultException ex )
                            {
                                gui.UserNotifier.notifyRpcException(ex);
                            }
                        }
                        break;
                    }
                case gui.ActionTree.CHECK_ACTION:
                    {
                        xmlrpc.OSManager osm = (xmlrpc.OSManager)treeActions.SelectedNode.Tag;
                        MessageBox.Show(xmlrpc.UdsAdminService.CheckOSManager(osm.id));
                        break;
                    }
            }
        }

        private void transportContextMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            switch (s.Name)
            {
                case gui.ActionTree.MODIFY_ACTION:
                    {
                        xmlrpc.Transport trans = (xmlrpc.Transport)treeActions.SelectedNode.Tag;
                        TransportForm dlg = new TransportForm(trans.typeName, trans.type, getIcon(_transportTypes, trans.type));
                        dlg.setData(trans.name, trans.comments, trans.id, xmlrpc.UdsAdminService.GetTransport(trans.id));
                        if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                            updateTransportsTree();
                        break;
                    }
                case gui.ActionTree.DELETE_ACTION:
                    {
                        xmlrpc.Transport trans = (xmlrpc.Transport)treeActions.SelectedNode.Tag;
                        xmlrpc.UdsAdminService.RemoveTransport(trans.id);
                        updateTransportsTree();
                        break;
                    }
            }
        }

        private void deployedContextMenu_Click(object sender, EventArgs e)
        {
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            switch (s.Name)
            {
                case gui.ActionTree.MODIFY_ACTION:
                    {
                        xmlrpc.DeployedService dps = (xmlrpc.DeployedService)treeActions.SelectedNode.Tag;
                        dps = xmlrpc.UdsAdminService.GetDeployedService(dps.id);
                        DeployedServiceForm dlg = new DeployedServiceForm();
                        dlg.setData(dps);
                        if( dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK )
                            updateDeployedServicesTree();
                        break;
                    }
                case gui.ActionTree.DELETE_ACTION:
                    {
                        xmlrpc.DeployedService dps = (xmlrpc.DeployedService)treeActions.SelectedNode.Tag;
                        if (MessageBox.Show(Strings.removeQuestion, Strings.deployedService, MessageBoxButtons.YesNo) == System.Windows.Forms.DialogResult.Yes)
                        {
                            xmlrpc.UdsAdminService.RemoveDeployedService(dps.id);
                            updateDeployedServicesTree();
                        }
                        break;
                    }
                case gui.ActionTree.PUBLISH_ACTION:
                    {
                        // This can be trigered from 2 different places
                        if (treeActions.SelectedNode.Name == gui.ActionTree.DEPLOYED_SERVICE)
                            treeActions.SelectedNode = treeActions.SelectedNode.Nodes[gui.ActionTree.PUBLICATIONS];
                        xmlrpc.DeployedService dps = (xmlrpc.DeployedService)treeActions.SelectedNode.Parent.Tag;
                        if (MessageBox.Show(Strings.publishQuestion, Strings.publish, MessageBoxButtons.YesNo) == System.Windows.Forms.DialogResult.Yes)
                            try
                            {
                                xmlrpc.UdsAdminService.PublishDeployedService(dps);
                                treeActions_AfterSelect(null, null);
                            }
                            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                            {
                                gui.UserNotifier.notifyRpcException(ex);
                            }

                        break;
                    }
            }
        }

        private void UserGroupsMenu_Click(object sender, EventArgs e)
        {
            bool user = treeActions.SelectedNode.Name ==  gui.ActionTree.USERS;
            xmlrpc.Authenticator auth = (xmlrpc.Authenticator)(treeActions.SelectedNode.Parent.Tag);
            xmlrpc.AuthenticatorType type = gui.ActionTree.authType(auth, _authenticatorsTypes);
            ToolStripMenuItem s = (ToolStripMenuItem)sender;
            switch (s.Name)
            {
                case gui.ActionTree.NEW_ACTION:
                    {
                        if (user)
                        {
                            if (type.canCreateUsers == false)
                            {
                                gui.UserNotifier.notifyError(Strings.cantCreateUsers);
                                return;
                            }
                            forms.UserForm dlg = new UserForm(auth, type, new xmlrpc.User());
                            if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                            {
                                treeActions_AfterSelect(null, null);
                            }
                        }
                        else
                        {
                            forms.GroupForm dlg = new GroupForm(auth, type, null);
                            if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                                treeActions_AfterSelect(null, null);
                        }
                        break;
                    }
            }

        }

        private void newNetwork_Click(object sender, EventArgs e)
        {
            forms.NetworkForm dlg = new NetworkForm();
            if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                treeActions_AfterSelect(null, null);
        }


        private void treeActions_MouseDown(object sender, MouseEventArgs e)
        {
            // We force the selected item to be the one at witch we right-clicked
            if (e.Button == MouseButtons.Right)
            {
                treeActions.SelectedNode = treeActions.GetNodeAt(e.X, e.Y);
            }
        }

        private void treeActions_KeyUp(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.F5)
            {
                TreeNode node = treeActions.SelectedNode;
                switch (node.Name)
                {
                    case gui.ActionTree.SERVICES_PROVIDERS:
                        updateServicesProvidersTree();
                        break;
                    case gui.ActionTree.SERVICE_PROVIDER:
                        {
                            xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)node.Tag;
                            updateServicesTree(sp.id);
                        }
                        break;
                    case gui.ActionTree.AUTHENTICATORS:
                        updateAuthenticatorsTree();
                        break;
                    case gui.ActionTree.AUTHENTICATOR:
                        // TODO: Make this update the auth tree
                        break;
                    case gui.ActionTree.OS_MANAGERS:
                    case gui.ActionTree.OS_MANAGER:
                        updateOSManagersTree();
                        break;
                    case gui.ActionTree.TRANSPORTS:
                    case gui.ActionTree.TRANSPORT:
                        updateTransportsTree();
                        break;
                    case gui.ActionTree.NETWORKS:
                        updateTransportsTree();
                        break;
                    case gui.ActionTree.DEPLOYED_SERVICES:
                    case gui.ActionTree.DEPLOYED_SERVICE:
                        updateDeployedServicesTree();
                        break;
                    case gui.ActionTree.PUBLICATIONS:
                    case gui.ActionTree.ASSIGNED_SERVICES:
                    case gui.ActionTree.CACHE:
                    case gui.ActionTree.USERS:
                    case gui.ActionTree.GROUPS:
                        treeActions_AfterSelect(null, null);
                        break;

                }
                        
            }
        }

        // Test form
        private void testToolStripMenuItem1_Click(object sender, EventArgs e)
        {
        }


        // Helper methods, Tree updaters
        private void updateServicesProvidersTree()
        {
            gui.ActionTree.FillServicesProviders(treeActions.Nodes[gui.ActionTree.SERVICES_PROVIDERS], serviceProviderContextMenu_Click);
            treeActions_AfterSelect(null, null);
        }

        private void updateServicesTree(string idServiceProvider)
        {
            TreeNode nodeBase = treeActions.Nodes[gui.ActionTree.SERVICES_PROVIDERS];
            foreach (TreeNode node in nodeBase.Nodes)
            {
                if (node.Name == gui.ActionTree.SERVICE_PROVIDER)
                {
                    xmlrpc.ServiceProvider sp = (xmlrpc.ServiceProvider)node.Tag;
                    if (sp.id == idServiceProvider)
                        gui.ActionTree.FillServices(node, serviceContextMenu_Click);
                }
            }
            treeActions_AfterSelect(null, null);
        }

        private void updateAuthenticatorsTree()
        {
            gui.ActionTree.FillAuthenticators(treeActions.Nodes[gui.ActionTree.AUTHENTICATORS], _authenticatorsTypes,
                AuthenticatorContextMenu_Click, UserGroupsMenu_Click);
            treeActions_AfterSelect(null, null);
        }

        private void updateOSManagersTree()
        {
            gui.ActionTree.FillOSManagers(treeActions.Nodes[gui.ActionTree.OS_MANAGERS], osManagerContextMenu_Click);
            treeActions_AfterSelect(null, null);
        }

        private void updateTransportsTree()
        {
            gui.ActionTree.FillTransports(treeActions.Nodes[gui.ActionTree.CONNECTIVITY].Nodes[gui.ActionTree.TRANSPORTS], 
                transportContextMenu_Click);
            treeActions_AfterSelect(null, null);
        }

        private void updateDeployedServicesTree()
        {
            gui.ActionTree.FillDeployedServices(treeActions.Nodes[gui.ActionTree.DEPLOYED_SERVICES], deployedContextMenu_Click);
            treeActions_AfterSelect(this, null);
        }

        private void MainForm_FormClosed(object sender, FormClosedEventArgs e)
        {
            string url = xmlrpc.UdsAdminService.Logout();
            if (url != "")
            {
                try
                {
                    System.Net.WebRequest req = System.Net.WebRequest.Create(url);
                    System.Net.WebResponse response = req.GetResponse();
                    // We don't mind whatever result we get
                    response.Close();
                }
                catch (Exception)
                {
                }
            }
        }

        private void exitToolStripMenuItem_Click(object sender, EventArgs e)
        {
            Close();
        }

        private void toolStripButton1_Click(object sender, EventArgs e)
        {
            xmlrpc.UdsAdminService.FlushCache();
            MessageBox.Show(Strings.cacheFlushed, Strings.cache, MessageBoxButtons.OK);
        }

        private void configurationToolStripMenuItem_Click(object sender, EventArgs e)
        {
            new ConfigurationForm().ShowDialog();
        }

        public static Point centerLocation(Form f)
        {
            return new Point(form.Location.X + form.Width / 2 - f.Width / 2, form.Location.Y + form.Height / 2 - f.Height / 2);
        }

        private void aboutToolStripMenuItem1_Click(object sender, EventArgs e)
        {
            (new AboutBoxForm()).ShowDialog();
        }

    }
}
