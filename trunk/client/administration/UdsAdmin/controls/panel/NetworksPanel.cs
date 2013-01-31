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
    public partial class NetworksPanel : UserControl
    {
        ContextMenuStrip _emptyMenu;
        ContextMenuStrip _fullMenu;
        gui.ListViewSorter _listSorter;

        public NetworksPanel()
        {
            InitializeComponent();

            _emptyMenu = new ContextMenuStrip();
            _fullMenu = new ContextMenuStrip();

            ToolStripMenuItem newG1 = new ToolStripMenuItem(Strings.newItem); newG1.Click += newItem; newG1.Image = Images.new16;
            ToolStripMenuItem newG2 = new ToolStripMenuItem(Strings.newItem); newG2.Click += newItem; newG2.Image = Images.new16;
            ToolStripMenuItem delete = new ToolStripMenuItem(Strings.deleteItem); delete.Click += deleteItem; delete.Image = Images.delete16;

            _emptyMenu.Items.Add(newG1);
            _fullMenu.Items.AddRange(new ToolStripItem[] { newG2, delete });

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
                xmlrpc.Network[] nets = xmlrpc.UdsAdminService.GetNetworks();
                List<ListViewItem> lst = new List<ListViewItem>();
                foreach (xmlrpc.Network net in nets)
                {
                    ListViewItem itm = new ListViewItem(new string[]{net.name, net.netStart, net.netEnd});
                    itm.ForeColor = gui.Colors.ActiveColor;
                    itm.Tag = net;
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

        private void newItem(object sender, EventArgs e)
        {
            UdsAdmin.forms.NetworkForm form = new UdsAdmin.forms.NetworkForm();
            if (form.ShowDialog() == DialogResult.OK)
            {
                updateList();
            }
        }

        private void deleteItem(object sender, EventArgs e)
        {
            if (listView.SelectedItems.Count == 0)
                return;
            string[] ids = new string[listView.SelectedItems.Count];
            int n = 0;
            foreach (ListViewItem i in listView.SelectedItems)
            {
                ids[n++] = ((xmlrpc.Network)i.Tag).id;
                listView.Items.Remove(i);
            }
            xmlrpc.UdsAdminService.RemoveNetworks(ids); 
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

        private void listView_ColumnClick(object sender, ColumnClickEventArgs e)
        {
            _listSorter.ColumnClick(sender, e);
        }

    }
}
