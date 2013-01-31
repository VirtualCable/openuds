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

namespace UdsAdmin.gui
{
    public class MenusManager
    {
        public static void InitProvidersMenu(ToolStripMenuItem menu, EventHandler action, xmlrpc.ServiceProviderType[] providersTypes)
        {
            menu.DropDownItems.Clear();
            menu.Text = Strings.newItem;
            List<xmlrpc.ServiceProviderType> lst = new List<xmlrpc.ServiceProviderType>(providersTypes);
            lst.Sort(new xmlrpc.ServiceProviderTypeSorterByName());
            foreach (xmlrpc.ServiceProviderType pt in lst)
            {
                ToolStripItem m = new ToolStripMenuItem(pt.name);
                m.Name = pt.type;
                m.ToolTipText = pt.description;
                m.Image = gui.Helpers.ImageFromBase64(pt.icon);
                m.Click += action;

                menu.DropDownItems.Add(m);
            }
        }

        public static ContextMenuStrip ServicesMenu(EventHandler action, xmlrpc.ServiceType[] servicesTypes, bool withModifyDelete)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem newA = new ToolStripMenuItem(); newA.Name = "" ;

            newA.DropDownItems.Clear();
            newA.Text = Strings.newItem;

            List<xmlrpc.ServiceType> lst = new List<xmlrpc.ServiceType>(servicesTypes);
            lst.Sort(new xmlrpc.ServiceTypeSorterByName());

            foreach (xmlrpc.ServiceType st in lst)
            {
                ToolStripItem m = new ToolStripMenuItem(st.name);
                m.Name = ActionTree.NEW_ACTION;
                m.Tag = st;
                m.ToolTipText = st.description;
                m.Image = gui.Helpers.ImageFromBase64(st.icon);
                m.Click += action;

                newA.DropDownItems.Add(m);
            }

            if (withModifyDelete)
            {
                ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Name = ActionTree.MODIFY_ACTION; modify.Click += action;
                ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Name = ActionTree.DELETE_ACTION; delete.Click += action;
                ToolStripMenuItem check = new ToolStripMenuItem(Strings.checkServiceProvider); check.Name = ActionTree.CHECK_ACTION; check.Click += action;
                if( servicesTypes.Length > 0 )
                    menu.Items.AddRange(new ToolStripItem[] { newA, modify, delete, check });
                else
                    menu.Items.AddRange(new ToolStripItem[] { modify, delete, check });
            }
            else
                menu.Items.Add(newA);
            return menu;
        }

        public static ContextMenuStrip ServiceMenu(EventHandler action, xmlrpc.Service service, xmlrpc.ServiceType type)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Name = ActionTree.MODIFY_ACTION; modify.Click += action; modify.Tag = type;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Name = ActionTree.DELETE_ACTION; delete.Click += action;
            menu.Items.AddRange(new ToolStripItem[] { modify, delete });
            return menu;
        }

        public static void InitAuthenticatorsMenu(ToolStripMenuItem menu, EventHandler action, xmlrpc.AuthenticatorType[] authsTypes)
        {
            menu.DropDownItems.Clear();
            menu.Text = Strings.newItem;
            List<xmlrpc.AuthenticatorType> lst = new List<xmlrpc.AuthenticatorType>(authsTypes);
            lst.Sort(new xmlrpc.AuthenticatorTypeSorterByName());

            foreach (xmlrpc.AuthenticatorType authType in lst)
            {
                ToolStripItem m = new ToolStripMenuItem(authType.name);
                m.Name = authType.type;
                m.ToolTipText = authType.description;
                m.Image = gui.Helpers.ImageFromBase64(authType.icon);
                m.Click += action;

                menu.DropDownItems.Add(m);
            }
        }

        public static ContextMenuStrip AuthMenu(EventHandler action)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Name = ActionTree.MODIFY_ACTION; modify.Click += action;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Name = ActionTree.DELETE_ACTION; delete.Click += action;
            ToolStripMenuItem check = new ToolStripMenuItem(Strings.checkAuthenticator); check.Name = ActionTree.CHECK_ACTION; check.Click += action;
            menu.Items.AddRange(new ToolStripItem[] { modify, delete, check });
            return menu;
        }

        public static void InitOSManagersMenu(ToolStripMenuItem menu, EventHandler action, xmlrpc.OSManagerType[] osmTypes)
        {
            menu.DropDownItems.Clear();
            menu.Text = Strings.newItem;
            List<xmlrpc.OSManagerType> lst = new List<xmlrpc.OSManagerType>(osmTypes);
            lst.Sort(new xmlrpc.OSManagerTypeSorterByName());

            foreach (xmlrpc.OSManagerType osmType in lst)
            {
                ToolStripItem m = new ToolStripMenuItem(osmType.name);
                m.Name = osmType.type;
                m.ToolTipText = osmType.description;
                m.Image = gui.Helpers.ImageFromBase64(osmType.icon);
                m.Click += action;

                menu.DropDownItems.Add(m);
            }
        }

        public static ContextMenuStrip OSManagerMenu(EventHandler action, xmlrpc.OSManager osm)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Name = ActionTree.MODIFY_ACTION; modify.Click += action;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Name = ActionTree.DELETE_ACTION; delete.Click += action;
            ToolStripMenuItem check = new ToolStripMenuItem(Strings.checkOSManager); check.Name = ActionTree.CHECK_ACTION; check.Click += action;
            menu.Items.AddRange(new ToolStripItem[] { modify, delete, check });
            return menu;
        }

        public static void InitTransportsMenu(ToolStripMenuItem menu, EventHandler action, xmlrpc.TransportType[] transTypes)
        {
            menu.DropDownItems.Clear();
            menu.Text = Strings.newItem;
            List<xmlrpc.TransportType> lst = new List<xmlrpc.TransportType>(transTypes);
            lst.Sort(new xmlrpc.TransportTypeSorterByName());

            foreach (xmlrpc.TransportType tType in lst)
            {
                ToolStripItem m = new ToolStripMenuItem(tType.name);
                m.Name = tType.type;
                m.ToolTipText = tType.description;
                m.Image = gui.Helpers.ImageFromBase64(tType.icon);
                m.Click += action;

                menu.DropDownItems.Add(m);
            }
        }

        public static ContextMenuStrip TransportMenu(EventHandler action, xmlrpc.Transport trans)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Name = ActionTree.MODIFY_ACTION; modify.Click += action;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Name = ActionTree.DELETE_ACTION; delete.Click += action;
            menu.Items.AddRange(new ToolStripItem[] { modify, delete });
            return menu;
        }

        public static ContextMenuStrip NetworksMenu(EventHandler action)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem newNetwork = new ToolStripMenuItem(Strings.newItem);
            newNetwork.Click += action;
            menu.Items.Add(newNetwork);
            return menu;
        }


        public static void InitDeployedServicesMenu(ToolStripMenuItem menu, EventHandler action)
        {
            menu.Text = Strings.newItem;
            menu.Click += action;
        }

        public static ContextMenuStrip DeployedServiceMenu(EventHandler action, xmlrpc.DeployedService dps)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Name = ActionTree.MODIFY_ACTION; modify.Click += action;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Name = ActionTree.DELETE_ACTION; delete.Click += action;
            menu.Items.AddRange(new ToolStripItem[] { modify, delete});
            if (dps.info.needsPublication)
            {
                ToolStripSeparator sep = new ToolStripSeparator();
                ToolStripMenuItem publish = new ToolStripMenuItem(Strings.publish); publish.Name = ActionTree.PUBLISH_ACTION; publish.Click += action;
                menu.Items.AddRange(new ToolStripItem[] {sep, publish });
            }
            return menu;
        }

        public static ContextMenuStrip TreeUsersGroupsMenu(EventHandler action)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem newU = new ToolStripMenuItem(Strings.newItem); newU.Name = ActionTree.NEW_ACTION; newU.Click += action;
            menu.Items.Add(newU);
            return menu;
        }


        public static ContextMenuStrip PublicationMenu(EventHandler action)
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem publish = new ToolStripMenuItem(Strings.publish); publish.Name = ActionTree.PUBLISH_ACTION; publish.Click += action;
            menu.Items.Add(publish);
            return menu;
        }
    }
}
