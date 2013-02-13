//
// Copyright (c) 2012-2013 Virtual Cable S.L.
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
    public partial class DeployedServicesPanel : UserControl
    {
        gui.ListViewSorter _listSorter;
        private DateTime shownToCharts = new DateTime();

        public DeployedServicesPanel()
        {
            InitializeComponent();

            listView.ListViewItemSorter = _listSorter = new gui.ListViewSorter(listView);
            updateList();
        }

        private void UsersPanel_VisibleChanged(object sender, EventArgs e)
        {
            if (Visible == true)
                if (tabControl1.SelectedTab == tabPage2)
                    updateCharts();
                else
                    updateList();
        }

        private void updateList()
        {
            try
            {
                xmlrpc.DeployedService[] dps = xmlrpc.UdsAdminService.GetDeployedServices(true);
                List<ListViewItem> lst = new List<ListViewItem>();
                foreach (xmlrpc.DeployedService ser in dps)
                {
                    ListViewItem itm = new ListViewItem(new string[]{ser.name, ser.info.typeName, xmlrpc.Util.GetStringFromState(ser.state), ser.comments});
                    itm.ForeColor = gui.Colors.getColorForState(ser.state);
                    itm.Tag = ser.id;
                    lst.Add(itm);
                }
                listView.BeginUpdate();
                listView.Items.Clear();
                listView.Items.AddRange(lst.ToArray());
                listView.EndUpdate();
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

            if (listView.Items.Count > 0)
            {
                listView.Items[0].Selected = listView.Items[0].Focused = true;
                listView.Focus();
            }
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
                xmlrpc.StatCounter assigned = xmlrpc.UdsAdminService.GetDeployedServiceCounters(xmlrpc.Constants.ALL, 
                    xmlrpc.Constants.COUNTER_ASSIGNED, since, to, Properties.Settings.Default.StatsItems, true);
                xmlrpc.StatCounter inUse = xmlrpc.UdsAdminService.GetDeployedServiceCounters(xmlrpc.Constants.ALL,
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
            foreach (ListViewItem i in listView.SelectedItems)
            {
                try
                {
                    xmlrpc.LogEntry[] logs = xmlrpc.UdsAdminService.GetDeployedServiceLogs((string)i.Tag);
                    data.AddRange(logs);
                }
                catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                {
                    gui.UserNotifier.notifyRpcException(ex);
                }

            }
            logViewer1.setLogs(data.ToArray());
        }

        private void listView_KeyUp(object sender, KeyEventArgs e)
        {
            switch (e.KeyCode)
            {
                case Keys.F5:
                    tabControl1_SelectedIndexChanged(null, null);
                    break;
                case Keys.E:
                    if (e.Modifiers == Keys.Control && tabControl1.SelectedTab == tabPage1)
                        foreach (ListViewItem i in listView.Items)
                            i.Selected = true;
                    break;
            }
        }

        private void listView_ColumnClick(object sender, ColumnClickEventArgs e)
        {
            _listSorter.ColumnClick(sender, e);
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
                updateList();
        }

        private void listView_SelectedIndexChanged(object sender, EventArgs e)
        {
            updateLogs();
        }

        private void DeployedServicesPanel_Resize(object sender, EventArgs e)
        {
            // Workaround to "dock" not fitting the content correctly
            tabControl1.Size = this.Size;
        }

    }
}
