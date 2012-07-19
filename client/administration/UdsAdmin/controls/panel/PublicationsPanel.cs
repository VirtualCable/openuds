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
    public partial class PublicationsPanel : UserControl
    {
        private xmlrpc.DeployedService _parent;
        ContextMenuStrip _fullMenu;
        gui.ListViewSorter _listSorter;

        public PublicationsPanel(xmlrpc.DeployedService parent)
        {
            _parent = parent;
            _fullMenu = new ContextMenuStrip();
            InitializeComponent();

            ToolStripMenuItem cancel = new ToolStripMenuItem(Strings.cancel); cancel.Click += cancelPublication; cancel.Image = Images.cancel16;

            _fullMenu.Items.AddRange(new ToolStripItem[] { cancel });

            listView.ListViewItemSorter = _listSorter = new gui.ListViewSorter(listView, new int[] {1});

            updateList();
        }

        private void DeployedPanel_VisibleChanged(object sender, EventArgs e)
        {
            if (Visible == true)
            {
                updateList();
            }
        }

        private void updateList()
        {
            xmlrpc.DeployedServicePublication[] pubs = UdsAdmin.xmlrpc.UdsAdminService.getPublications(_parent);
            List<ListViewItem> lst = new List<ListViewItem>();
            foreach (xmlrpc.DeployedServicePublication pub in pubs)
            {
                ListViewItem itm = new ListViewItem(new string[] { pub.revision, pub.publishDate.ToString(), xmlrpc.Util.GetStringFromState(pub.state), pub.reason });
                itm.Tag = pub.id;
                switch (pub.state)
                {
                    case xmlrpc.Constants.STATE_USABLE:
                        itm.ForeColor = gui.Colors.ActiveColor;
                        break;
                    case xmlrpc.Constants.STATE_ERROR:
                        itm.ForeColor = gui.Colors.ErrorColor;
                        break;
                    case xmlrpc.Constants.STATE_PREPARING:
                        itm.ForeColor = gui.Colors.RunningColor;
                        break;
                    default:
                        itm.ForeColor = gui.Colors.InactiveColor;
                        break;
                }
                lst.Add(itm);
            }
            listView.Items.Clear();
            listView.Items.AddRange(lst.ToArray());
        }

        private void cancelPublication(object sender, EventArgs e)
        {
            if (listView.SelectedItems.Count == 0)
                return;
            if (listView.SelectedItems.Count > 1)
            {
                MessageBox.Show(Strings.selectOnlyOne, Strings.error, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            ListViewItem itm = listView.SelectedItems[0];
            string id = (string)itm.Tag;
            try
            {
                xmlrpc.UdsAdminService.CancelPublication(id);
                updateList();

            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
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
                    return;
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
