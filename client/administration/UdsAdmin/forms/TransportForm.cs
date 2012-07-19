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
    public partial class TransportForm : Form
    {
        string _id;
        xmlrpc.GuiField[] _flds;
        xmlrpc.GuiFieldValue[] _fldValues;
        string _transportName;
        string _transportType;

        public TransportForm(string TransportName, string transportType, Icon icon)
        {
            InitializeComponent();
            _fldValues = null;
            _id = null;
            _flds = null;
            _transportName = TransportName;
            _transportType = transportType;
            Icon = icon;
            // Read networks
            nets.Items.AddRange(xmlrpc.UdsAdminService.GetNetworks());
            Text = Strings.titleTransport;
        }

        public void setData(string name, string comments, string id, xmlrpc.GuiFieldValue[] data)
        {
            this.name.Text = name;
            this.comments.Text = comments;
            this.priority.Value = Convert.ToInt32(xmlrpc.GuiFieldValue.getData(data, "priority"));
            this.positiveNets.Checked = xmlrpc.GuiFieldValue.getData(data, "positiveNet") == xmlrpc.Constants.TRUE;
            this._id = id;
            _fldValues = data;
            // Fill networks
            foreach( string netId in xmlrpc.UdsAdminService.GetNetworksForTransport(id))
            {
                for( int i = 0; i < nets.Items.Count; i++ )
                {
                    xmlrpc.Network net = (xmlrpc.Network)nets.Items[i];
                    if (net.id == netId)
                        nets.SetItemChecked(i, true);
                }
            }
        }

        private void Transport_Load(object sender, EventArgs e)
        {
            _flds = xmlrpc.UdsAdminService.GetTransportGui(_transportType);
            if (_flds == null)
            {
                Close();
                return;
            }
            Size sz = gui.DinamycFieldsManager.PutFields(dataPanel, _flds, _fldValues);
            groupData.Size = new Size(groupData.Size.Width, 32 + sz.Height);
            Size wSize = new Size();
            wSize.Width = Size.Width + 64;
            wSize.Height = groupData.Location.Y + tableLayoutPanel1.Size.Height + groupData.Size.Height + 96;
            Size = MinimumSize = MaximumSize = wSize;
            if (_flds.Length == 0)
                groupData.Visible = false;
            Text = _transportName;
            //this.Location = System.Windows.Forms.Cursor.Position;
            
            // Networks
            positiveNets_CheckedChanged(null, null);
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
                    _id = xmlrpc.UdsAdminService.CreateTransport(name.Text, comments.Text, Convert.ToInt32(priority.Value), positiveNets.Checked, _transportType, data);
                else
                    xmlrpc.UdsAdminService.ModifyTransport(name.Text, comments.Text, Convert.ToInt32(priority.Value), positiveNets.Checked, _id, data);
                List<string> ids = new List<string>();
                foreach (xmlrpc.Network net in nets.CheckedItems)
                    ids.Add(net.id);
                xmlrpc.UdsAdminService.SetNetworksForTransport(_id, ids.ToArray() );

                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

        }

        private void positiveNets_CheckedChanged(object sender, EventArgs e)
        {
            if (positiveNets.Checked == true)
            {
                positiveNets.Text = Strings.positiveNetCheck;
                positiveNets.BackColor = gui.Colors.ActiveBackColor;
                positiveNets.ForeColor = gui.Colors.ActiveForeColor;
            }
            else
            {
                positiveNets.Text = Strings.negativeNetCheck;
                positiveNets.BackColor = gui.Colors.InactiveBackColor;
                positiveNets.ForeColor = gui.Colors.InactiveForeColor;
            }
        }

    }
}
