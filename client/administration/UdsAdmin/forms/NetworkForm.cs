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
    public partial class NetworkForm : Form
    {
        private xmlrpc.Network _net;

        public NetworkForm(xmlrpc.Network net = null)
        {
            InitializeComponent();

            if (net != null)
                _net = net;
            else
                _net = new xmlrpc.Network();

            netStart.KeyPress += HandleKeyPress;
            netEnd.KeyPress += HandleKeyPress;

            Text = Strings.titleNetwork;
        }

        private void NetworkForm_Load(object sender, EventArgs e)
        {
            if (_net == null)
            {
                name.Text = _net.name;
                netStart.Text = _net.netStart;
                netEnd.Text = _net.netEnd;
            }
            Location = MainForm.centerLocation(this);
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (name.Text.Trim().Length == 0)
            {
                gui.UserNotifier.notifyError(Strings.nameRequired);
                return;
            }
            System.Net.IPAddress ip;
            System.Net.IPAddress ip2;
            if (System.Net.IPAddress.TryParse(netStart.Text, out ip) == false)
            {
                MessageBox.Show(Strings.invalidIpAddress, Strings.netStart, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            if (System.Net.IPAddress.TryParse(netEnd.Text, out ip2) == false)
            {
                MessageBox.Show(Strings.invalidIpAddress, Strings.netEnd, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            
            if (ip.Address > ip2.Address)
            {
                MessageBox.Show(Strings.netRangeError, Strings.netStart + "/" + Strings.netEnd, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            _net.name = name.Text;
            _net.netStart = netStart.Text;
            _net.netEnd = netEnd.Text;
            try {
                if (_net.id == "")
                {
                    xmlrpc.UdsAdminService.CreateNetwork(_net);
                }
                else
                {
                    xmlrpc.UdsAdminService.ModifyNetwork(_net);
                }
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

        }

        private void HandleKeyPress(object sender, KeyPressEventArgs e)
        {
            if (!(char.IsDigit(e.KeyChar) || char.IsControl(e.KeyChar)) && e.KeyChar != '.')
                e.Handled = true;
        }

    }
}
