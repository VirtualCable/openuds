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
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace UdsAdmin.controls.panel
{
    public partial class DeployedServicePanel : UserControl
    {
        private string _dsId;
        private DateTime shownToCharts = new DateTime();

        public DeployedServicePanel(xmlrpc.DeployedService ds)
        {
            _dsId = ds.id;
            InitializeComponent();

            updateData();
        }

        private void DeployedServicePanel_VisibleChanged(object sender, EventArgs e)
        {
            if (Visible == true)
                if (tabControl1.SelectedTab == tabPage2)
                    updateCharts();
                else
                    updateData();
        }

        private void updateData()
        {
            SuspendLayout();
            xmlrpc.DeployedService ds = xmlrpc.UdsAdminService.GetDeployedService(_dsId);
            lName.Text = ds.name;
            lComments.Text = ds.comments;
            lInitial.Text = ds.initialServices.ToString();
            lCache.Text = ds.cacheL1.ToString();
            lL2Cache.Text = ds.cacheL2.ToString();
            lMax.Text = ds.maxServices.ToString();
            lState.Text = ds.state;
            lBaseService.Text = ds.serviceName;
            lOsManager.Text = ds.osManagerName;

            updateLogs();

            ResumeLayout();
        }

        private void updateCharts()
        {
            SuspendLayout();
            DateTime now = DateTime.Now;
            DateTime to = new DateTime(now.Year, now.Month, now.Day, now.Hour, 0, 0);
            DateTime since = to.AddDays(-7);

            if (to == shownToCharts)
                return;

            try
            {
                xmlrpc.StatCounter assigned = xmlrpc.UdsAdminService.GetDeployedServiceCounters(_dsId,
                    xmlrpc.Constants.COUNTER_ASSIGNED, since, to, Properties.Settings.Default.StatsItems, true);
                xmlrpc.StatCounter inUse = xmlrpc.UdsAdminService.GetDeployedServiceCounters(_dsId,
                    xmlrpc.Constants.COUNTER_INUSE, since, to, Properties.Settings.Default.StatsItems, true);

                assignedChart.clearSeries();
                assignedChart.addSerie(assigned);
                inUseChart.clearSeries();
                inUseChart.addSerie(inUse);

                shownToCharts = to;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException e)
            {
                gui.UserNotifier.notifyRpcException(e);
            }

            ResumeLayout();
        }

        private void updateLogs()
        {
            List<xmlrpc.LogEntry> data = new List<xmlrpc.LogEntry>();
            try
            {
                xmlrpc.LogEntry[] logs = xmlrpc.UdsAdminService.GetDeployedServiceLogs(_dsId);
                data.AddRange(logs);
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }
            logViewer1.setLogs(data.ToArray());
        }

        private void tabControl1_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (tabControl1.SelectedTab == tabPage2)
            {
                if (sender == null)
                    shownToCharts = new DateTime();
                updateCharts();
            }
            else
                updateData();
        }

        private void tabControl1_KeyUp(object sender, KeyEventArgs e)
        {
            switch (e.KeyCode)
            {
                case Keys.F5:
                    tabControl1_SelectedIndexChanged(null, null);
                    break;

            }

        }

        private void DeployedServicePanel_Resize(object sender, EventArgs e)
        {
            // Workaround to "dock" not fitting the content correctly
            tabControl1.Size = this.Size;
        }

    }
}
