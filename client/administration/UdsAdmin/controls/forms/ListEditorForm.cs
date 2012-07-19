using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.IO;

namespace UdsAdmin.controls.forms
{
    public partial class ListEditorForm : Form
    {
        public ListEditorForm()
        {
            InitializeComponent();
        }

        private void addTxtItem(string txt)
        {
            lstItems.Items.Add(txt);
        }

        private void addCommaSeparatedValues(string txt)
        {
            foreach (string item in txt.Split(','))
            {
                addTxtItem(item);
            }
        }

        public ListBox.ObjectCollection Items
        {
            get { return lstItems.Items; }
        }

        private void processTxt()
        {
            string item = textItem.Text;
            if (item.Length == 0)
                return;

            if (item.Contains(','))
                addCommaSeparatedValues(item);
            else
                addTxtItem(item);

            textItem.Text = "";
            textItem.Focus();
        }


        private void textItem_KeyPress(object sender, KeyPressEventArgs e)
        {
            if (e.KeyChar == 13)
            {
                processTxt();
            }
        }

        private void btnRemove_Click(object sender, EventArgs e)
        {
            if (lstItems.SelectedIndex != -1)
            {
                int sel = lstItems.SelectedIndex;
                lstItems.Items.RemoveAt(sel);
                if (sel > 0)
                    lstItems.SelectedIndex = sel - 1;
                else if (lstItems.Items.Count > 0)
                    lstItems.SelectedIndex = 0;
            }
        }

        private void btnAdd_Click(object sender, EventArgs e)
        {
            processTxt();
        }

        private void btnClose_Click(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.OK;
        }

        private void ListEditorForm_Load(object sender, EventArgs e)
        {
            this.Location = System.Windows.Forms.Cursor.Position;
        }

        private void btnImport_Click(object sender, EventArgs e)
        {
            OpenFileDialog dlg = new OpenFileDialog();
            dlg.Filter = Strings.importFilter;
            dlg.DefaultExt = "txt";
            dlg.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Personal);
            if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
            {
                StreamReader reader = File.OpenText(dlg.FileName);
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if( line.Contains(',') )
                        addCommaSeparatedValues(line);
                    else
                        addTxtItem(line);
                }
                reader.Close();
            }
        }
    }
}
