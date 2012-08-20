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
    public partial class ServiceProviderForm : Form
    {
        string _id;
        xmlrpc.GuiField[] _flds;
        xmlrpc.GuiFieldValue[] _fldValues;
        string _providerName;
        string _providerType;

        public ServiceProviderForm(string providerName, string providerType, Icon icon)
        {
            InitializeComponent();
            _fldValues = null;
            _id = null;
            _flds = null;
            _providerName = providerName;
            _providerType = providerType;
            Icon = icon;
            Text = Strings.titleServiceProvider;
        }

        public void setData(string name, string comments, string id, xmlrpc.GuiFieldValue[] data)
        {
            this.name.Text = name;
            this.comments.Text = comments;
            this._id = id;
            _fldValues = data;
        }

        private void ServiceProvider_Load(object sender, EventArgs e)
        {
            _flds = xmlrpc.UdsAdminService.GetServiceProviderGui(_providerType);
            if (_flds == null)
            {
                Close();
                return;
            }
            Size sz = gui.DinamycFieldsManager.PutFields(dataPanel, _flds, _fldValues);
            groupData.Size = new Size(groupData.Size.Width, 32 + sz.Height);
            Size wSize = new Size();
            wSize.Width = Size.Width;
            int w = groupData.Location.X + groupData.Size.Width + 48;
            if (wSize.Width < w)
                wSize.Width = w;
            wSize.Height = groupData.Location.Y + tableLayoutPanel1.Size.Height + groupData.Size.Height + 48;
            Size = MinimumSize = MaximumSize = wSize;
            if (_flds.Length == 0)
                groupData.Visible = false;
            Text = _providerName;
            Location = MainForm.centerLocation(this);
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (name.Text.Trim().Length == 0)
            {
                gui.UserNotifier.notifyError(Strings.nameRequired);
                return;
            }
            xmlrpc.GuiFieldValue[] data;
            try {
                data = gui.DinamycFieldsManager.ReadFields(dataPanel, _flds);
            }
            catch (gui.DinamycFieldsManager.ValidationError err)
            {
                gui.UserNotifier.notifyValidationException(err);
                return;
            }

            try {
                if (_id == null)
                    xmlrpc.UdsAdminService.CreateServiceProvider(name.Text, comments.Text, _providerType, data);
                else
                    xmlrpc.UdsAdminService.ModifyServiceProvider(name.Text, comments.Text, _id, data);
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
        }

        private void test_Click(object sender, EventArgs e)
        {
            xmlrpc.GuiFieldValue[] data = gui.DinamycFieldsManager.ReadFields(dataPanel, _flds);
            xmlrpc.ResultTest res = xmlrpc.UdsAdminService.testServiceProvider(_providerType, data);
            gui.UserNotifier.notifyTestResult(res);
        }
    }
}
