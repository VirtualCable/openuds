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

namespace UdsAdmin.forms
{
    public partial class SearchForm : Form
    {
        public enum Type { userSearch, groupSearch };

        private Type _type;
        private string _authId;
        gui.ListViewSorter _listSorter;

        public SearchForm(Type type, xmlrpc.Authenticator auth, string defText = null)
        {
            InitializeComponent();
            _type = type;
            _authId = auth.id;
            if (defText != null)
                searchText.Text = defText;

            resultsList.ListViewItemSorter = _listSorter = new gui.ListViewSorter(resultsList);
        }

        private void SearchForm_Load(object sender, EventArgs e)
        {
            if (_type == Type.userSearch)
            {
                Text = Strings.searchUser;
                searchLabel.Text = Strings.user;
            }
            else
            {
                Text = Strings.searchGroup;
                searchLabel.Text = Strings.group;
            }
        }

        public string selection
        {
            get { return resultsList.SelectedItems[0].SubItems[0].Text; }
        }

        private void cancel_Click(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.No;
        }

        private void searchButton_Click(object sender, EventArgs e)
        {
            string srch = searchText.Text.Trim();
            try
            {
                xmlrpc.SimpleInfo[] res = xmlrpc.UdsAdminService.SearchAuthenticator(_authId, _type == Type.userSearch, srch);
                resultsList.Items.Clear();
                foreach (xmlrpc.SimpleInfo r in res)
                {
                    ListViewItem itm = new ListViewItem(new string[]{r.id, r.name});
                    resultsList.Items.Add(itm);
                }
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
        }

        private void resultsList_ColumnClick(object sender, ColumnClickEventArgs e)
        {
            _listSorter.ColumnClick(sender, e);
        }

        private void resultsList_DoubleClick(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.Yes;
        }
    }
}
