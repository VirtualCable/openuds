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
    public partial class DeployedServiceForm : Form
    {
        private xmlrpc.DeployedService _dps;

        private xmlrpc.Service[] _services = null;
        private xmlrpc.OSManager[] _osManagers = null;
        private xmlrpc.Transport[] _transports;
        private ToolTip tooltipCache = new ToolTip();
        private ToolTip tooltipCacheL2 = new ToolTip();

        public DeployedServiceForm()
        {
            InitializeComponent();
            _dps = new xmlrpc.DeployedService();
            _dps.id = "";
            Text = Strings.titleDeployedService;
        }

        public void setData(xmlrpc.DeployedService dps)
        {
            _dps = dps;
        }

        private void DeployedServiceForm_Load(object sender, EventArgs e)
        {
            _services = xmlrpc.UdsAdminService.GetAllServices();
            _osManagers = xmlrpc.UdsAdminService.GetOSManagers();
            _transports = xmlrpc.UdsAdminService.GetTransports();
            
            tooltipCache.SetToolTip(cacheLabel, "");
            tooltipCacheL2.SetToolTip(cacheL2Label, "");

            Text = Strings.titleDeployedService;

            if (_services.Length == 0)
            {
                UdsAdmin.gui.UserNotifier.notifyError(Strings.needsServices);
                Close();
                return;
            }

            if (_osManagers.Length == 0)
            {
                UdsAdmin.gui.UserNotifier.notifyError(Strings.needsOsManagers);
                Close();
                return;
            }

            if (_transports.Length == 0 )
            {
                UdsAdmin.gui.UserNotifier.notifyError(Strings.needsTransports);
            }

            baseServiceCombo.Items.AddRange(_services);
            osManagerCombo.Items.AddRange(_osManagers);
            allowedTransports.Items.AddRange(_transports);

            // Modifying, update form to modify operation
            if (_dps.id != "")
            {
                Text = Strings.modifying + " " + _dps.name;

                baseServiceCombo.Enabled = false;
                osManagerCombo.Enabled = false;
                publishOnSave.Enabled = false;
                publishOnSave.Checked = false;
                foreach (xmlrpc.OSManager osm in _osManagers)
                    if (osm.id == _dps.idOsManager)
                    {
                        osManagerCombo.SelectedItem = osm;
                        break;
                    }
                foreach (xmlrpc.Service serv in _services)
                    if (serv.id == _dps.idService)
                    {
                        baseServiceCombo.SelectedItem = serv;
                        ((Control)tabs.TabPages["Cache"]).Enabled = serv.info.usesCache;
                        cacheL2Label.Enabled = cacheL2ServicesBox.Enabled = serv.info.usesCacheL2;
                        tooltipCache.SetToolTip(cacheLabel, serv.info.cacheTooltip);
                        tooltipCacheL2.SetToolTip(cacheL2Label, serv.info.cacheTooltipL2);
                        break;
                    }
                foreach (xmlrpc.SimpleInfo trans in _dps.transports)
                {
                    for (int i = 0; i < allowedTransports.Items.Count; i++)
                    {
                        xmlrpc.Transport tr = (xmlrpc.Transport)allowedTransports.Items[i];
                        if (tr.id == trans.id)
                            allowedTransports.SetItemChecked(i, true);
                    }
                }
                nameBox.Text = _dps.name;
                commentsBox.Text = _dps.comments;
                initialServicesBox.Value = _dps.initialServices;
                cacheServicesBox.Value = _dps.cacheL1;
                cacheL2ServicesBox.Value = _dps.cacheL2;
                maxServicesBox.Value = _dps.maxServices;
            }
            else
            {
                publishOnSave.Checked = true;
            }

            Location = MainForm.centerLocation(this);
        }

        private void baseServiceCombo_SelectionChangeCommitted(object sender, EventArgs e)
        {
            xmlrpc.Service selected = (xmlrpc.Service)baseServiceCombo.SelectedItem;
            if (_dps.id == "")
            {
                osManagerCombo.Enabled = selected.info.needsManager;
            }
            publishOnSave.Enabled = selected.info.needsPublication;
            ((Control)tabs.TabPages["Cache"]).Enabled = selected.info.usesCache;
            cacheL2Label.Enabled = cacheL2ServicesBox.Enabled = selected.info.usesCacheL2;
            tooltipCache.SetToolTip(cacheLabel, selected.info.cacheTooltip);
            tooltipCacheL2.SetToolTip(cacheL2Label, selected.info.cacheTooltipL2);
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (nameBox.Text.Trim().Length == 0)
            {
                gui.UserNotifier.notifyError(Strings.nameRequired);
                return;
            }

            if( baseServiceCombo.SelectedItem == null )
            {
                gui.UserNotifier.notifyError(Strings.specifyBaseService);
                return;
            }

            if( ((xmlrpc.Service)baseServiceCombo.SelectedItem).info.needsManager && osManagerCombo.SelectedItem == null )
            {
                gui.UserNotifier.notifyError(Strings.specifyOsManager);
                return;
            }

            if (initialServicesBox.Value > maxServicesBox.Value)
                maxServicesBox.Value = initialServicesBox.Value;
            if (cacheServicesBox.Value > maxServicesBox.Value)
                maxServicesBox.Value = cacheServicesBox.Value;

            _dps.initialServices = (int)initialServicesBox.Value;
            _dps.cacheL1 = (int)cacheServicesBox.Value;
            _dps.cacheL2 = (int)cacheL2ServicesBox.Value;
            _dps.maxServices = (int)maxServicesBox.Value;
            _dps.name = nameBox.Text;
            _dps.comments = commentsBox.Text;
            _dps.idService = ((xmlrpc.Service)baseServiceCombo.SelectedItem).id;
            if (osManagerCombo.SelectedItem != null)
                _dps.idOsManager = ((xmlrpc.OSManager)osManagerCombo.SelectedItem).id;
            else
                _dps.idOsManager = "-1";

            xmlrpc.SimpleInfo[] transports = new xmlrpc.SimpleInfo[allowedTransports.CheckedItems.Count];
            int n = 0;
            foreach( xmlrpc.Transport trns in allowedTransports.CheckedItems )
                transports[n++] = new xmlrpc.SimpleInfo(trns.id, trns.name);

            _dps.transports = transports;

            try
            {
                if (_dps.id == "") // Create a new deployed Service
                {
                    _dps.state = xmlrpc.Constants.STATE_ACTIVE;
                    _dps.id = xmlrpc.UdsAdminService.CreateDeployedService(_dps);
                    if ( publishOnSave.Enabled && publishOnSave.Checked)
                        xmlrpc.UdsAdminService.PublishDeployedService(_dps);
                }
                else
                {
                    xmlrpc.UdsAdminService.ModifyDeployedService(_dps);
                }
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch( CookComputing.XmlRpc.XmlRpcFaultException ex )
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

        }


    }
}
