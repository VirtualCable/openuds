using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Resources;
using System.Text;
using System.Windows.Forms;

namespace uds.gui.forms
{
    public partial class Config : Form
    {
        public Config()
        {
            InitializeComponent();
        }

        private void Config_Load(object sender, EventArgs e)
        {
            brokerAddress.Text = config.broker;
            useSecureConnection.SelectedIndex = config.ssl ? 0 : 1;
            if (Info.Computer.IsUserAdministrator() == false)
            {
                MessageBox.Show(Lang.AdminNeeded, Lang.Error, MessageBoxButtons.OK, MessageBoxIcon.Error);
                Close();
                return;
            }

        }

        private void cancelButton_Click(object sender, EventArgs e)
        {
            Close();
        }

        private void testConnectionButton_Click(object sender, EventArgs e)
        {
            rpc.Initialize(brokerAddress.Text, useSecureConnection.SelectedIndex == 0);
            if (rpc.Manager.Test() == false)
            {
                MessageBox.Show(Lang.ConnectionError, Lang.ConnectionTest, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            else
            {
                MessageBox.Show(Lang.ConnectionOK, Lang.ConnectionTest, MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
            }
        }

        private void acceptButton_Click(object sender, EventArgs e)
        {
            config.broker = brokerAddress.Text;
            config.ssl = useSecureConnection.SelectedIndex == 0;
            config.SaveConfig();
            Close();
        }
    }
}
