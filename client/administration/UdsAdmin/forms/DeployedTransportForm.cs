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
    public partial class DeployedTransportForm : Form
    {
        private xmlrpc.DeployedService _ds;

        public DeployedTransportForm(xmlrpc.DeployedService ds)
        {
            _ds = ds;
            InitializeComponent();
            Text = Strings.titleAssignNewGroup;
        }

        private void DeployedTransportForm_Load(object sender, EventArgs e)
        {
            xmlrpc.Transport[] trans = xmlrpc.UdsAdminService.GetTransports();
            transCombo.Items.AddRange(trans);

            if (trans.Length > 0)
            {
                transCombo.SelectedIndex = 0;
            }
            else
            {
                MessageBox.Show(Strings.error, Strings.transports, MessageBoxButtons.OK, MessageBoxIcon.Error);
                Close();
            }
            Location = MainForm.centerLocation(this);
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (transCombo.SelectedItem != null)
            {
                xmlrpc.Transport trans = (xmlrpc.Transport)transCombo.SelectedItem;
                xmlrpc.UdsAdminService.AssignTransportToDeployedService(_ds.id, trans.id);
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            else
                gui.UserNotifier.notifyError(Strings.transportRequired);

        }

    }
}
