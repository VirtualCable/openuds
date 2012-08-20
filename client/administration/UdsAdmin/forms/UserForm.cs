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
    public partial class UserForm : Form
    {
        private xmlrpc.Authenticator _auth;
        private xmlrpc.AuthenticatorType _authType;
        private xmlrpc.User _user;
        private string[] states = new string[] { xmlrpc.Constants.STATE_ACTIVE, xmlrpc.Constants.STATE_INACTIVE, xmlrpc.Constants.STATE_BLOCKED };

        public UserForm(xmlrpc.Authenticator auth, xmlrpc.AuthenticatorType authType, xmlrpc.User user)
        {
            _auth = auth;
            _authType = authType;
            _user = user;

            InitializeComponent();
            Text = Strings.user;
        }

        private void UserForm_Load(object sender, EventArgs e)
        {
            state.Items.AddRange(new string[] { Strings.active, Strings.inactive, Strings.blocked });
            state.SelectedIndex = 0;

            if (_authType.canSearchUsers)
            {
                searchButton.Enabled = true;
                check.Visible = true;
            }
            else
            {
                searchButton.Enabled = false;
                check.Visible = false;
            }

            if (_authType.needsPassword)
            {
                password.Visible = passwordLabel.Visible = true;
            }
            else
            {
                password.Visible = passwordLabel.Visible = false;
            }

            userNameLabel.Text = _authType.userNameLabel;
            passwordLabel.Text = _authType.passwordLabel;


            xmlrpc.Group[] groups = new xmlrpc.Group[0];
            if (_user.id != null)
            {
                groups = _user.groups; // xmlrpc.UdsAdminService.GetUserGroups(_user.id);
                name.Text = _user.name; realName.Text = _user.realName;
                comments.Text = _user.comments; password.Text = _user.password;
                name.ReadOnly = true;
                searchButton.Enabled = false;
                for( int i = 0; i < states.Length; i++ )
                    if( states[i] == _user.state )
                    {
                        state.SelectedIndex = i;
                        break;
                    }
                _user.comments = comments.Text; 

            }

            if (_authType.isExternalSource )
            {
                groupsList.Enabled = false;
                if (_user.id != null)
                    foreach (xmlrpc.Group grp in groups)
                        groupsList.Items.Add(grp, true);
            }
            else
            {
                (tabs.TabPages["group"] as Control).Enabled = true;
                try
                {
                    xmlrpc.Group[] grps = xmlrpc.UdsAdminService.GetAuthenticatorGroups(_auth.id);
                    foreach (xmlrpc.Group grp in grps)
                    {
                        bool active = groups.Length > 0 && Array.Find(groups, g => g.id == grp.id).active;
                        groupsList.Items.Add(grp, active);
                    }
                }
                catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                {
                    gui.UserNotifier.notifyRpcException(ex);
                }
            }

            staffMember.Enabled = staffMemberLabel.Enabled = admin.Enabled = adminLabel.Enabled = xmlrpc.UdsAdminService.isAdmin;
            staffMember.Checked = _user.staffMember;
            admin.Checked = _user.isAdmin;

            Location = MainForm.centerLocation(this);
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (name.Text.Trim().Length == 0)
            {
                gui.UserNotifier.notifyError(Strings.nameRequired);
                return;
            }
            try
            {
                if (_authType.isExternalSource == false)
                {
                    _user.groups = new xmlrpc.Group[groupsList.CheckedItems.Count];
                    int n = 0;
                    foreach (xmlrpc.Group grp in groupsList.CheckedItems)
                    {
                        _user.groups[n++] = grp;
                    }
                }
                _user.idParent = _auth.id; _user.name = name.Text; _user.realName = realName.Text;
                _user.comments = comments.Text; _user.state = states[state.SelectedIndex];
                _user.password = password.Text;
                // If the user is not admin, server will ignore these parameters
                _user.isAdmin = admin.Checked;
                _user.staffMember = staffMember.Checked;
                if (_user.id == null || _user.id == "")
                {
                    // New user
                    _user.id = "";
                    _user.oldPassword = "";
                    xmlrpc.UdsAdminService.CreateUser(_user);
                }
                else
                {
                    xmlrpc.UdsAdminService.ModifyUser(_user);
                }
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
        }

        private void cancel_Click(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.Cancel;
        }

        private void searchButton_Click_1(object sender, EventArgs e)
        {
            SearchForm form = new SearchForm(SearchForm.Type.userSearch, _auth, name.Text);
            if (form.ShowDialog() == System.Windows.Forms.DialogResult.Yes)
                name.Text = form.selection;
        }
    }
}
