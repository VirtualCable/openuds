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
    public partial class DeployedGroupsPanel : UserControl
    {
        private xmlrpc.DeployedService _ds;
        ContextMenuStrip _selectedMenu;
        ContextMenuStrip _unselectedMenu;
        gui.ListViewSorter _listSorter;

        public DeployedGroupsPanel(xmlrpc.DeployedService dps)
        {
            _ds = dps;
            InitializeComponent();

            _selectedMenu = new ContextMenuStrip();
            _unselectedMenu = new ContextMenuStrip();

            ToolStripMenuItem enable = new ToolStripMenuItem(Strings.enable); enable.Click += enableItem; enable.Image = Images.apply16;
            ToolStripMenuItem disable = new ToolStripMenuItem(Strings.disable); disable.Click += disableItem; disable.Image = Images.cancel16;
            ToolStripSeparator sep = new ToolStripSeparator();
            ToolStripMenuItem newG = new ToolStripMenuItem(Strings.newItem); newG.Click += newItem; newG.Image = Images.new16;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Click += deleteItem; delete.Image = Images.delete16;

            ToolStripMenuItem newG2 = new ToolStripMenuItem(Strings.newItem); newG2.Click += newItem; newG2.Image = Images.new16;
            ToolStripMenuItem delete2 = new ToolStripMenuItem(Strings.deleteItem); delete2.Click += deleteItem; delete2.Image = Images.delete16;

            _selectedMenu.Items.AddRange(new ToolStripItem[] { enable, disable, sep, newG, delete });
            _unselectedMenu.Items.AddRange(new ToolStripItem[] { newG2, delete2 });

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
            xmlrpc.Group[] grps = xmlrpc.UdsAdminService.GetGroupsAssignedToDeployedService(_ds.id);
            List<ListViewItem> lst = new List<ListViewItem>();
            foreach (xmlrpc.Group grp in grps)
            {
                ListViewItem itm = new ListViewItem(new string[]{grp.nameParent, grp.name, grp.active ? Strings.active : Strings.inactive , grp.comments});
                itm.ForeColor = grp.active ? gui.Colors.ActiveColor : gui.Colors.InactiveColor;
                itm.Tag = grp.id;
                lst.Add(itm);
            }
            listView.Items.Clear();
            listView.Items.AddRange(lst.ToArray());
        }

        private void newItem(object sender, EventArgs e)
        {
            UdsAdmin.forms.DeployedGroupForm form = new UdsAdmin.forms.DeployedGroupForm(_ds);
            if (form.ShowDialog() == DialogResult.OK)
                updateList();
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
                ids[n++] = (string)i.Tag;
                i.SubItems[2].Text = info;
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
                ids[n++] = (string)i.Tag;
                listView.Items.Remove(i);
            }
            xmlrpc.UdsAdminService.RemoveGroupsFromDeployedService(_ds.id, ids);
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
                    _unselectedMenu.Show(Control.MousePosition.X, Control.MousePosition.Y);
                else
                    _selectedMenu.Show(Control.MousePosition.X, Control.MousePosition.Y);
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
