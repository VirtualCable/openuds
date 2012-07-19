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
    public partial class UserPreferencesForm : Form
    {
        private struct PageData
        {
            public xmlrpc.GuiField[] fields;
            public TableLayoutPanel panel;

            public PageData(xmlrpc.GuiField[] flds, TableLayoutPanel tbl)
            {
                fields = flds;
                panel = tbl;
            }
        }

        private string _userId;
        private List<PageData> _data = new List<PageData>();

        public UserPreferencesForm(string userId)
        {
            _userId = userId;
            InitializeComponent();
            Text = Strings.titleUserPreferences;
        }

        private void UserPreferencesForm_Load(object sender, EventArgs e)
        {
            xmlrpc.PrefGroup[] prefs = xmlrpc.UdsAdminService.GetPrefsForUser(_userId);
            Size max = new Size(0, 0);
            foreach (xmlrpc.PrefGroup p in prefs)
            {
                TabPage page = new TabPage(p.moduleLabel);
                TableLayoutPanel table = new TableLayoutPanel();
                page.Controls.Add(table);
                modTabs.TabPages.Add(page);
                _data.Add(new PageData(p.prefs, table));

                Size sz = gui.DinamycFieldsManager.PutFields(table, p.prefs, null);
                if (max.Width < sz.Width)
                    max.Width = sz.Width;
                if (max.Height < sz.Height)
                    max.Height = sz.Height;
            }
            max.Height += 120;
            max.Width += 56;
            Size = max;
        }

        private void accept_Click(object sender, EventArgs e)
        {
            List<xmlrpc.GuiFieldValue> data = new List<xmlrpc.GuiFieldValue>();
            try
            {
                foreach( PageData p in _data )
                {
                    xmlrpc.GuiFieldValue[] partial = gui.DinamycFieldsManager.ReadFields(p.panel, p.fields);
                    data.AddRange(partial);
                }
                xmlrpc.UdsAdminService.SetPrefsForUser(_userId, data.ToArray());
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (gui.DinamycFieldsManager.ValidationError err)
            {
                gui.UserNotifier.notifyValidationException(err);
                return;
            }
        }
    }
}
