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
    public partial class GroupForm : Form
    {
        private xmlrpc.Authenticator _auth;
        private xmlrpc.AuthenticatorType _authType;
        private string _id;

        public GroupForm(xmlrpc.Authenticator auth, xmlrpc.AuthenticatorType authType, string groupId)
        {
            _auth = auth;
            _authType = authType;
            _id = groupId;
            InitializeComponent();
            Text = Strings.titleGroup;
        }

        private void GroupForm_Load(object sender, EventArgs e)
        {
            active.Checked = true;
            active.Text = Strings.active;
            if (_authType.canSearchGroups)
            {
                searchButton.Enabled = true;
                check.Visible = true;
            }
            else
            {
                searchButton.Enabled = false;
                check.Visible = false;
            }
            groupLabel.Text = _authType.groupNameLabel;
            if (_id != null)
            {
                try
                {
                    xmlrpc.Group grp = xmlrpc.UdsAdminService.GetGroup(_id);
                    name.Text = grp.name;
                    comments.Text = grp.comments;
                    active.Checked = grp.active;
                }
                catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                {
                    gui.UserNotifier.notifyRpcException(ex);
                    Close();
                }
            }

            Location = MainForm.centerLocation(this);
        }

        private void searchButton_Click(object sender, EventArgs e)
        {
            SearchForm form = new SearchForm(SearchForm.Type.groupSearch, _auth, name.Text);
            if (form.ShowDialog() == System.Windows.Forms.DialogResult.Yes)
                name.Text = form.selection;
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (name.Text.Trim().Length == 0)
            {
                gui.UserNotifier.notifyError(Strings.nameRequired);
                return;
            }
            xmlrpc.Group grp = new xmlrpc.Group();
            grp.idParent = _auth.id; grp.id = ""; grp.name = name.Text; grp.comments = comments.Text; grp.active = active.Checked;

            try
            {
                if (_id == null)
                {
                    xmlrpc.UdsAdminService.CreateGroup(grp);
                }
                else
                {
                    grp.id = _id;
                    xmlrpc.UdsAdminService.ModifyGroup(grp);
                }
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
        }

        private void active_CheckedChanged(object sender, EventArgs e)
        {
            active.Text = active.Checked ? Strings.active : Strings.inactive;
        }

        private void cancel_Click(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.Cancel;
        }
    }
}
