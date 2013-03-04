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
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace UdsAdmin.controls.panel
{
    public partial class UsersPanel : UserControl
    {
        private xmlrpc.Authenticator _auth;
        private xmlrpc.AuthenticatorType _authType;
        ContextMenuStrip _emptyMenu;
        ContextMenuStrip _fullMenu;
        gui.ListViewSorter _listSorter;

        public UsersPanel(xmlrpc.Authenticator auth, xmlrpc.AuthenticatorType authType)
        {
            _auth = auth;
            _authType = authType;
            InitializeComponent();

            _emptyMenu = new ContextMenuStrip();
            _fullMenu = new ContextMenuStrip();


            ToolStripMenuItem newU1 = new ToolStripMenuItem(Strings.newItem); newU1.Click += newItem; newU1.Image = Images.new16;

            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Click += modifyItem;
            ToolStripMenuItem prefs = new ToolStripMenuItem(Strings.userPreferences); prefs.Click += preferences;
            ToolStripMenuItem enable = new ToolStripMenuItem(Strings.enable); enable.Click += enableItem; enable.Image = Images.apply16;
            ToolStripMenuItem disable = new ToolStripMenuItem(Strings.disable); disable.Click += disableItem; disable.Image = Images.cancel16;
            ToolStripMenuItem newU2 = new ToolStripMenuItem(Strings.newItem); newU2.Click += newItem; newU2.Image = Images.new16;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Click += deleteItem; delete.Image = Images.delete16;

            _fullMenu.Items.AddRange(new ToolStripItem[] { modify, new ToolStripSeparator(), enable, disable, new ToolStripSeparator(), 
                prefs, new ToolStripSeparator()});

            if (_authType.canCreateUsers == true)
            {
                _emptyMenu.Items.Add(newU1);
                _fullMenu.Items.Add(newU2);
            }

            _fullMenu.Items.Add(delete);

            listView.Columns[0].Text = _authType.userNameLabel;

            listView.ListViewItemSorter = _listSorter = new gui.ListViewSorter(listView, new int[]{3});
            updateList();
        }

        private void UsersPanel_VisibleChanged(object sender, EventArgs e)
        {
            if (Visible == true)
            {
                updateList();
            }
        }


        private string getStateString(string state)
        {
            string res;
            switch (state)
            {
                case xmlrpc.Constants.STATE_ACTIVE:
                    res = Strings.active;
                    break;
                case xmlrpc.Constants.STATE_INACTIVE:
                    res = Strings.inactive;
                    break;
                default:
                    res = Strings.blocked;
                    break;
            }
            return res;
        }

        private Color getStateColor(string state)
        {
            Color color;
            switch (state)
            {
                case xmlrpc.Constants.STATE_ACTIVE:
                    color = gui.Colors.ActiveColor;
                    break;
                case xmlrpc.Constants.STATE_INACTIVE:
                    color = gui.Colors.InactiveColor;
                    break;
                default:
                    color = gui.Colors.BlockedColor;
                    break;
            }
            return color;
        }

        private void updateList()
        {
            int[] selected = new int[listView.SelectedIndices.Count];
            listView.SelectedIndices.CopyTo(selected, 0);

            try
            {
                xmlrpc.User[] usrs = xmlrpc.UdsAdminService.GetUsers(_auth.id);
                List<ListViewItem> lst = new List<ListViewItem>();
                foreach (xmlrpc.User usr in usrs)
                {

                    ListViewItem itm = new ListViewItem(new string[] { usr.name, usr.realName, getStateString(usr.state), usr.lastAccess.ToString(), usr.comments });
                    itm.ForeColor = getStateColor(usr.state);
                    itm.Tag = usr.id;
                    lst.Add(itm);
                }
                listView.Items.Clear();
                listView.Items.AddRange(lst.ToArray());
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

            foreach (int i in selected)
            {
                try
                {
                    listView.SelectedIndices.Add(i);
                }
                catch (Exception)
                { }
            }
        }

        private void newItem(object sender, EventArgs e)
        {
            if (_authType.canCreateUsers == false)
            {
                gui.UserNotifier.notifyError(Strings.cantCreateUsers);
                return;
            }
            UdsAdmin.forms.UserForm form = new UdsAdmin.forms.UserForm(_auth, _authType, new xmlrpc.User());
            if (form.ShowDialog() == DialogResult.OK)
            {
                updateList();
            }
        }

        private void modifyItem(object sender, EventArgs e)
        {
            xmlrpc.User usr = xmlrpc.UdsAdminService.GetUser((string)(listView.SelectedItems[0].Tag));
            UdsAdmin.forms.UserForm form = new UdsAdmin.forms.UserForm(_auth, _authType, usr);
            if (form.ShowDialog() == DialogResult.OK )
            {
                updateList();
            }
        }

        private void preferences(object sender, EventArgs e)
        {
            xmlrpc.User usr = xmlrpc.UdsAdminService.GetUser((string)(listView.SelectedItems[0].Tag));
            UdsAdmin.forms.UserPreferencesForm form = new UdsAdmin.forms.UserPreferencesForm(usr.id);
            form.ShowDialog();
        }

        private void setSelectedStates(string newState)
        {
            if( listView.SelectedItems.Count == 0 )
                return;
            string info = getStateString(newState);
            Color col = getStateColor(newState);
            string[] ids = new string[listView.SelectedItems.Count];
            int n = 0;
            foreach (ListViewItem i in listView.SelectedItems)
            {
                ids[n++] = (string)i.Tag;
                i.SubItems[2].Text = info;
                i.ForeColor = col;
            }
            xmlrpc.UdsAdminService.ChangeUsersState(ids, newState);

        }

        private void enableItem(object sender, EventArgs e)
        {
            setSelectedStates(xmlrpc.Constants.STATE_ACTIVE);
        }

        private void disableItem(object sender, EventArgs e)
        {
            setSelectedStates(xmlrpc.Constants.STATE_INACTIVE);
        }

        private void deleteItem(object sender, EventArgs e)
        {
            if (listView.SelectedItems.Count == 0)
                return;
            string[] ids = new string[listView.SelectedItems.Count];
            int n = 0;
            foreach (ListViewItem i in listView.SelectedItems)
            {
                ids[n++] = (string)i.Tag;
                listView.Items.Remove(i);
            }
            xmlrpc.UdsAdminService.RemoveUsers(ids);
        }

        private void listView_ColumnClick(object sender, ColumnClickEventArgs e)
        {
            _listSorter.ColumnClick(sender, e);
        }

        private void listView_MouseUp(object sender, MouseEventArgs e)
        {
            if (e.Button == System.Windows.Forms.MouseButtons.Right)
            {
                if (listView.SelectedItems.Count == 0)
                {
                    if( _emptyMenu.Items.Count > 0 )
                    _emptyMenu.Show(Control.MousePosition.X, Control.MousePosition.Y);
                }
                else
                    _fullMenu.Show(Control.MousePosition.X, Control.MousePosition.Y);
            }
        }

        private void listView_KeyUp(object sender, KeyEventArgs e)
        {
            switch (e.KeyCode)
            {
                case Keys.F5:
                    updateList();
                    break;
                case Keys.E:
                    if (e.Modifiers == Keys.Control)
                        foreach (ListViewItem i in listView.Items)
                            i.Selected = true;
                    break;
            }
        }

        private void listView_SelectedIndexChanged(object sender, EventArgs e)
        {
            List<xmlrpc.LogEntry> data = new List<xmlrpc.LogEntry>();
            foreach (ListViewItem i in listView.SelectedItems)
            {
                try
                {
                    xmlrpc.LogEntry[] logs = xmlrpc.UdsAdminService.GetUserLogs((string)i.Tag);
                    data.AddRange(logs);
                    break;
                }
                catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                {
                    gui.UserNotifier.notifyRpcException(ex);
                }

            }
            logViewer1.setLogs(data.ToArray());
        }

    }
}
