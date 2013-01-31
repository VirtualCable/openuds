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
    public partial class LoginForm : Form
    {
        private const int HEIGHT_REDUCED = 80;
        private const int HEIGHT_EXPANDED = 220;

        private string savedAuth = "";
        private string savedUser = "";

        public LoginForm()
        {
            InitializeComponent();
            Height = HEIGHT_REDUCED;
            Text = Strings.titleLogin;
        }

        private void LoginForm_Load(object sender, EventArgs e)
        {
            LoadFormData();
            AcceptButton = extendButton;
        }

        private void exit_Click(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.Cancel;
        }

        private void button1_Click(object sender, EventArgs e)
        {
            try
            {
                string auth = "";
                if (authenticator.SelectedItem != null)
                    auth = ((xmlrpc.SimpleInfo)authenticator.SelectedItem).id;
                xmlrpc.UdsAdminService.Login(username.Text, passwordText.Text, auth);
                SaveAuthUser();
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                if (ex.FaultCode == xmlrpc.ExceptionExplainer.AUTH_FAILED)
                    MessageBox.Show(Strings.invalidCredentials, Strings.error, MessageBoxButtons.OK, MessageBoxIcon.Error);
                else
                    gui.UserNotifier.notifyRpcException(ex);
            }
            catch (exceptions.NewVersionRequiredException ex)
            {
                if (MessageBox.Show(Strings.newVersionRequired, Strings.downloadQuery, MessageBoxButtons.YesNo, MessageBoxIcon.Hand) == System.Windows.Forms.DialogResult.Yes)
                {
                    string url = "http" + (useSSLCheck.Checked ? "s" : "") + "://" + serverCombo.Text + ex.Url;
                    (new FileDownloader(url)).ShowDialog();
                }
                DialogResult = System.Windows.Forms.DialogResult.Cancel;
            }
        }

        private void button2_Click(object sender, EventArgs e)
        {
            if (extendButton.Text == ">>>")
            {
                try
                {
                    xmlrpc.SimpleInfo[] info = xmlrpc.UdsAdminService.GetAdminAuths(serverCombo.Text, useSSLCheck.Checked);
                    authenticator.Items.Clear();
                    foreach( xmlrpc.SimpleInfo i in info)
                    {
                        authenticator.Items.Add(i);
                    }
                    if (info.Length > 0)
                        authenticator.SelectedIndex = 0;
                    SaveServerData();
                    SetAuthUser();
                }
                catch (exceptions.CommunicationException)
                {
                    MessageBox.Show(Strings.cantConnect);
                    return;
                }
                extendButton.Text = "<<<";
                serverCombo.Enabled = false;
                useSSLCheck.Enabled = false;
                Height = HEIGHT_EXPANDED;
                username.Focus();
                AcceptButton = connectButton;
            }
            else
            {
                extendButton.Text = ">>>";
                serverCombo.Enabled = true;
                useSSLCheck.Enabled = true;
                Height = HEIGHT_REDUCED;
                AcceptButton = extendButton;
            }
        }

        private void SaveServerData()
        {
            List<string> items = new List<string>();
            bool addNewItem = true;
            string value = serverCombo.Text;
            foreach (object i in serverCombo.Items)
            {
                string s = i.ToString();
                items.Add(s);
                if (s == value)
                    addNewItem = false;
            }
            if (addNewItem)
            {
                items.Add(value);
                serverCombo.Items.Add(value);
            }
            Application.UserAppDataRegistry.SetValue("server", string.Join(",", items.ToArray()));
            Application.UserAppDataRegistry.SetValue("ssl", useSSLCheck.Checked ? "y" : "n");
        }

        private void SetAuthUser()
        {
            if (savedAuth != "")
            {
                foreach (xmlrpc.SimpleInfo i in authenticator.Items)
                {
                    if (i.id == savedAuth)
                    {
                        authenticator.SelectedItem = i;
                        break;
                    }
                }
            }
            if (savedUser != "")
            {
                username.Text = savedUser;
            }
        }

        private void SaveAuthUser()
        {
            savedAuth = ((xmlrpc.SimpleInfo)authenticator.SelectedItem).id;
            savedUser = username.Text;
            Application.UserAppDataRegistry.SetValue("auth", savedAuth);
            Application.UserAppDataRegistry.SetValue("user", savedUser);
        }

        private void LoadFormData()
        {
            string server = (string)Application.UserAppDataRegistry.GetValue("server", "");
            if (server != "")
            {
                string[] items = server.Split(',');
                serverCombo.Items.Clear();
                foreach (string i in items)
                    serverCombo.Items.Insert(0, i);
            }
            useSSLCheck.Checked = ((string)Application.UserAppDataRegistry.GetValue("ssl", "n")) == "y";
            savedAuth = (string)Application.UserAppDataRegistry.GetValue("auth", "");
            savedUser = (string)Application.UserAppDataRegistry.GetValue("user", "");
        }

    }
}
