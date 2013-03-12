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
    public partial class LogViewer : UserControl
    {
        gui.ListViewSorter _listSorter;
        private readonly int[] levelIndex = new int[] { xmlrpc.Constants.LEVEL_DEBUG_I, xmlrpc.Constants.LEVEL_INFO_I,
                xmlrpc.Constants.LEVEL_WARN_I, xmlrpc.Constants.LEVEL_ERROR_I, xmlrpc.Constants.LEVEL_FATAL_I };

        xmlrpc.LogEntry[] logs = null;

        public LogViewer()
        {
            InitializeComponent();

            ResizeRedraw = true;

            listView.ListViewItemSorter = _listSorter = new gui.ListViewSorter(listView, new int[] { 3, 5 });

            levelFilterCombo.Items.AddRange(new string[] { xmlrpc.Constants.LEVEL_DEBUG, xmlrpc.Constants.LEVEL_INFO,
                xmlrpc.Constants.LEVEL_WARN, xmlrpc.Constants.LEVEL_ERROR, xmlrpc.Constants.LEVEL_FATAL });
            levelFilterCombo.SelectedIndex = 1;
        }

        public void setLogs(xmlrpc.LogEntry[] logs)
        {
            this.logs = logs;
            updateList();
        }

        private void updateList()
        {
            if( logs == null )
                return;
            listView.BeginUpdate();

            List<ListViewItem> lst = new List<ListViewItem>();
            int minLevel = levelIndex[levelFilterCombo.SelectedIndex];

            foreach (xmlrpc.LogEntry l in logs)
            {
                if (l.level < minLevel)
                    continue;

                ListViewItem itm = new ListViewItem(new string[] { l.date.ToString(), xmlrpc.Constants.stringFromLevel(l.level), l.source, l.message });
                // Color is got from ranges
                itm.ForeColor = gui.Colors.getColorForLogLevel(l.level);
                lst.Add(itm);
            }
            listView.Items.Clear();
            listView.Items.AddRange(lst.ToArray());
            if (listView.Items.Count > 0)
                listView.TopItem = listView.Items[listView.Items.Count - 1];

            listView.EndUpdate();
        }


        private void listView_ColumnClick(object sender, ColumnClickEventArgs e)
        {
            _listSorter.ColumnClick(sender, e);
        }

        private void levelFilterCombo_SelectedIndexChanged(object sender, EventArgs e)
        {
            updateList();
        }

        private void listView_KeyUp(object sender, KeyEventArgs e)
        {
            /*switch (e.KeyCode)
            {
                case Keys.F5:
                    updateList();
                    break;
            }*/
        }
    }
}
