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
    public partial class ServiceForm : Form
    {
        string _id;
        string _idParent;
        xmlrpc.GuiField[] _flds;
        xmlrpc.GuiFieldValue[] _fldValues;
        string _serviceName;
        string _serviceType;

        public ServiceForm(string idParent, string serviceName, string serviceType, Icon icon)
        {
            InitializeComponent();
            _id = null;
            _idParent = idParent;
            _serviceName = serviceName;
            _serviceType = serviceType;
            _flds = null;
            _fldValues = null;
            Icon = icon;
            Text = Strings.titleService;
        }

        public void setData(string name, string comments, string id, xmlrpc.GuiFieldValue[] data)
        {
            this.name.Text = name;
            this.comments.Text = comments;
            this._id = id;
            _fldValues = data;
        }

        private void Service_Load(object sender, EventArgs e)
        {
            _flds = xmlrpc.UdsAdminService.GetServiceGui(_idParent, _serviceType);
            if (_flds == null)
            {
                Close();
                return;
            }
            Size sz = gui.DinamycFieldsManager.PutFields(dataPanel, _flds, _fldValues);
            groupData.Size = new Size(groupData.Size.Width, 32 + sz.Height);
            Size wSize = new Size();
            wSize.Width = Size.Width;
            wSize.Height = groupData.Location.Y + tableLayoutPanel1.Size.Height + groupData.Size.Height + 48;
            Size = MinimumSize = wSize;
            wSize.Width = Screen.GetWorkingArea(this).Width;
            MaximumSize = wSize;
            if (_flds.Length == 0)
                groupData.Visible = false;
            Text = _serviceName;
            //this.Location = System.Windows.Forms.Cursor.Position;
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
                {
                        xmlrpc.UdsAdminService.CreateService(_idParent, name.Text, comments.Text, _serviceType, data);
                }
                else
                {
                    xmlrpc.UdsAdminService.ModifyService(name.Text, comments.Text, _id, data);
                }
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
        }
    }
}
