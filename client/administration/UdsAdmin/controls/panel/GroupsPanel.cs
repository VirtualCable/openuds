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
    public partial class GroupsPanel : UserControl
    {
        private xmlrpc.Authenticator _auth;
        private xmlrpc.AuthenticatorType _authType;
        ContextMenuStrip _emptyMenu;
        ContextMenuStrip _fullMenu;
        gui.ListViewSorter _listSorter;


        public GroupsPanel(xmlrpc.Authenticator auth, xmlrpc.AuthenticatorType authType)
        {
            _auth = auth;
            _authType = authType;
            InitializeComponent();

            _emptyMenu = new ContextMenuStrip();
            _fullMenu = new ContextMenuStrip();

            ToolStripMenuItem modify = new ToolStripMenuItem(Strings.modifyItem); modify.Click += modifyItem; modify.Image = Images.groups16;
            ToolStripMenuItem enable = new ToolStripMenuItem(Strings.enable); enable.Click += enableItem; enable.Image = Images.apply16;
            ToolStripMenuItem disable = new ToolStripMenuItem(Strings.disable); disable.Click += disableItem; disable.Image = Images.cancel16;
            ToolStripSeparator sep = new ToolStripSeparator();
            ToolStripMenuItem newG1 = new ToolStripMenuItem(Strings.newItem); newG1.Click += newGroup; newG1.Image = Images.new16;
            ToolStripMenuItem newMG1 = new ToolStripMenuItem(Strings.newMetaGroup); newMG1.Click += newMetaGroup; newMG1.Image = Images.new16;
            ToolStripMenuItem newG2 = new ToolStripMenuItem(Strings.newItem); newG2.Click += newGroup; newG2.Image = Images.new16;
            ToolStripMenuItem newMG2 = new ToolStripMenuItem(Strings.newMetaGroup); newMG2.Click += newMetaGroup; newMG2.Image = Images.new16;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Click += deleteItem; delete.Image = Images.delete16;

            _emptyMenu.Items.AddRange(new ToolStripItem[] { newG1, newMG1 });
            _fullMenu.Items.AddRange(new ToolStripItem[] { enable, disable, sep, newG2, newMG2, modify, delete });

            listView.Columns[0].Text = _authType.groupNameLabel;

            listView.ListViewItemSorter = _listSorter = new gui.ListViewSorter(listView);
            updateList();
        }

        private void UsersPanel_VisibleChanged(object sender, EventArgs e)
        {
            if (Visible == true)
            {
                updateList();
            }
        }

        private void updateList()
        {
            try
            {
                xmlrpc.Group[] grps = xmlrpc.UdsAdminService.GetGroups(_auth.id);
                List<ListViewItem> lst = new List<ListViewItem>();
                foreach (xmlrpc.Group grp in grps)
                {
                    ListViewItem itm = new ListViewItem(new string[]{ grp.name, grp.active ? Strings.active : Strings.inactive , grp.comments});
                    if (grp.isMeta == true)
                    {
                        itm.ImageKey = "meta";

                    }
                    itm.ForeColor = grp.active ? gui.Colors.ActiveColor : gui.Colors.InactiveColor;
                    itm.Tag = grp;
                    lst.Add(itm);
                }
                listView.Items.Clear();
                listView.Items.AddRange(lst.ToArray());
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

        }

        private void newGroup(object sender, EventArgs e)
        {
            UdsAdmin.forms.GroupForm form = new UdsAdmin.forms.GroupForm(_auth, _authType, null);
            if (form.ShowDialog() == DialogResult.OK)
            {
                updateList();
            }
        }

        private void newMetaGroup(object sender, EventArgs e)
        {
            UdsAdmin.forms.GroupMetaForm form = new UdsAdmin.forms.GroupMetaForm(_auth, null);
            if (form.ShowDialog() == DialogResult.OK)
            {
                updateList();
            }
        }

        private void modifyItem(object sender, EventArgs e)
        {
            if (listView.SelectedItems.Count != 1)
                return;

            xmlrpc.Group group = (xmlrpc.Group)listView.SelectedItems[0].Tag;
            DialogResult res = DialogResult.No;

            if (group.isMeta == true)
            {
                res = (new UdsAdmin.forms.GroupMetaForm(_auth, group.id)).ShowDialog();
            }
            else
            {
                res = (new UdsAdmin.forms.GroupForm(_auth, _authType, group.id)).ShowDialog();
            }

            if (res == DialogResult.OK)
            {
                updateList();
            }
        }

        private void setSelectedStates(bool newState)
        {
            if( listView.SelectedItems.Count == 0 )
                return;
            string info = newState == true ? Strings.active : Strings.inactive;
            Color col = newState == true ? gui.Colors.ActiveColor : gui.Colors.InactiveColor;
            string[] ids = new string[listView.SelectedItems.Count];
            int n = 0;
            foreach (ListViewItem i in listView.SelectedItems)
            {
                ids[n++] = ((xmlrpc.Group)i.Tag).id;
                i.SubItems[1].Text = info;
                i.ForeColor = col;
            }
            xmlrpc.UdsAdminService.ChangeGroupsState(ids, newState);

        }

        private void enableItem(object sender, EventArgs e)
        {
            setSelectedStates(true);
        }

        private void disableItem(object sender, EventArgs e)
        {
            setSelectedStates(false);
        }

        private void deleteItem(object sender, EventArgs e)
        {
            if (listView.SelectedItems.Count == 0)
                return;
            string[] ids = new string[listView.SelectedItems.Count];
            int n = 0;
            foreach (ListViewItem i in listView.SelectedItems)
            {
                ids[n++] = ((xmlrpc.Group)i.Tag).id;
                listView.Items.Remove(i);
            }
            xmlrpc.UdsAdminService.RemoveGroups(ids);
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
                    _emptyMenu.Show(Control.MousePosition.X, Control.MousePosition.Y);
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

    }
}
