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
    public partial class ConfigurationForm : Form
    {
        List<TableLayoutPanel> panels = new List<TableLayoutPanel>();

        public ConfigurationForm()
        {
            InitializeComponent();
            Text = Strings.titleConfiguration;
        }

        private void ConfigurationForm_Load(object sender, EventArgs e)
        {
            xmlrpc.Configuration[] configuration = xmlrpc.UdsAdminService.GetConfiguration();
            Dictionary<string, List<xmlrpc.Configuration>> dict = new Dictionary<string,List<xmlrpc.Configuration>>();
            // Create the different tabs
            foreach (xmlrpc.Configuration cfg in configuration)
            {
                if (!dict.ContainsKey(cfg.section))
                {
                    dict.Add(cfg.section, new List<xmlrpc.Configuration>());
                }
                dict[cfg.section].Add(cfg);
            }

            // Now we create the tabs with fields
            foreach (KeyValuePair<string, List<xmlrpc.Configuration>> entry in dict)
            {
                int rows = entry.Value.Count;
                TableLayoutPanel pan = new TableLayoutPanel();
                pan.RowCount = rows;
                pan.ColumnCount = 2;
                pan.AutoSize = true;
                pan.Left = 8;
                pan.Top = 8;
                pan.Dock = DockStyle.Fill;
                pan.AutoScroll = true;

                int row = 0;
                foreach (xmlrpc.Configuration cfg in entry.Value)
                {
                    Label lab = new Label();
                    lab.Text = cfg.key;
                    lab.Margin = new System.Windows.Forms.Padding(3, 6, 3, 0);
                    lab.AutoSize = true;
                    lab.Dock = DockStyle.Fill;
                    pan.Controls.Add(lab, 0, row);
                    TextBox txt = new TextBox();
                    txt.Tag = cfg; 
                    txt.Text = cfg.value;
                    txt.Width = 180;
                    txt.UseSystemPasswordChar = cfg.crypt;
                    txt.Dock = DockStyle.Fill;
                    pan.Controls.Add(txt, 1, row);
                    row++;
                }

                // Set panel column and rows styles
                TableLayoutColumnStyleCollection styles = pan.ColumnStyles;

                foreach (ColumnStyle style in styles)
                {
                    style.SizeType = SizeType.AutoSize;
                }

                TableLayoutRowStyleCollection stylesR = pan.RowStyles;
                foreach (RowStyle style in stylesR)
                {
                    style.SizeType = SizeType.AutoSize;
                }

                TabPage page = new TabPage(entry.Key);
                page.Controls.Add(pan);
                panels.Add(pan);
                modTabs.TabPages.Add(page);
            }
            Location = MainForm.centerLocation(this);
        }

        private void accept_Click(object sender, EventArgs e)
        {
            // Locate changed items and submit them to save
            List<xmlrpc.Configuration> changed = new List<xmlrpc.Configuration>();
            foreach (TableLayoutPanel pan in panels )
            {
                foreach (Control ctrl in pan.Controls)
                {
                    if (ctrl is TextBox)
                    {
                        TextBox txt = (TextBox)ctrl;
                        xmlrpc.Configuration cfg = (xmlrpc.Configuration)ctrl.Tag;
                        if( cfg.value != txt.Text )
                            changed.Add( new xmlrpc.Configuration(cfg.section, cfg.key, txt.Text, cfg.crypt ) );
                    }
                }
            }

            xmlrpc.UdsAdminService.UpdateConfiguration(changed.ToArray());

            DialogResult = System.Windows.Forms.DialogResult.OK;
        }
    }
}
