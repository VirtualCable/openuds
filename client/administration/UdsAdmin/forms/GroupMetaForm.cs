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
    public partial class GroupMetaForm : Form
    {
        private xmlrpc.Authenticator _auth;
        private string _id;

        public GroupMetaForm(xmlrpc.Authenticator auth, string groupId)
        {
            InitializeComponent();
            _auth = auth;
            _id = groupId;
        }

        private void GroupMetaForm_Load(object sender, EventArgs e)
        {
            availableGroups.BeginUpdate();
            selectedGroups.BeginUpdate();

            try
            {
                foreach (xmlrpc.Group grp in xmlrpc.UdsAdminService.GetGroups(_auth.id))
                {
                    if (grp.isMeta == false)
                        availableGroups.Items.Add(grp);
                }
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
                Close();
            }

            if (_id != null)
            {
                try
                {
                    xmlrpc.Group grp = xmlrpc.UdsAdminService.GetGroup(_id);
                    name.Text = grp.name;
                    comments.Text = grp.comments;
                    active.Checked = grp.active;
                    // Sanity check
                    if (grp.isMeta == false)
                        throw new CookComputing.XmlRpc.XmlRpcFaultException(-1, Strings.groupIsNotMeta);


                    foreach (string id in grp.groupsIds)
                    {
                        foreach( xmlrpc.Group av in availableGroups.Items )
                        {
                            if (av.id == id)
                            {
                                selectedGroups.Items.Add(av);
                                availableGroups.Items.Remove(av);
                                break;
                            }
                        }
                    }

                    sortListbox(availableGroups);
                    sortListbox(selectedGroups);

                }
                catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
                {
                    gui.UserNotifier.notifyRpcException(ex);
                    Close();
                }
            }

            availableGroups.EndUpdate();
            selectedGroups.EndUpdate();

            Location = MainForm.centerLocation(this);
        }

        private static int compareGroups(xmlrpc.Group g1, xmlrpc.Group g2)
        {
            return String.Compare(g1.name, g2.name);
        }

        private void sortListbox(ListBox l)
        {
            List<xmlrpc.Group> lst = new List<xmlrpc.Group>(l.Items.OfType<xmlrpc.Group>());
            lst.Sort(compareGroups);
            l.Items.Clear();
            l.Items.AddRange(lst.ToArray());
        }

        private void button1_Click(object sender, EventArgs e)
        {
            if (availableGroups.SelectedItems.Count == 0)
                return;

            availableGroups.BeginUpdate();
            selectedGroups.BeginUpdate();

            List<xmlrpc.Group> toRemove = new List<xmlrpc.Group>();
            foreach (xmlrpc.Group grp in availableGroups.SelectedItems)
            {
                toRemove.Add(grp);
                selectedGroups.Items.Add(grp);
            }
            // Now remove groups from availables
            foreach( xmlrpc.Group grp in toRemove )
                availableGroups.Items.Remove(grp);

            sortListbox(availableGroups);
            sortListbox(selectedGroups);

            selectedGroups.EndUpdate();
            availableGroups.EndUpdate();
        }

        private void button2_Click(object sender, EventArgs e)
        {
            if (selectedGroups.SelectedItems.Count == 0)
                return;

            availableGroups.BeginUpdate();
            selectedGroups.BeginUpdate();

            List<xmlrpc.Group> toRemove = new List<xmlrpc.Group>();
            foreach (xmlrpc.Group grp in selectedGroups.SelectedItems)
            {
                toRemove.Add(grp);
                availableGroups.Items.Add(grp);
            }
            // Now remove groups from availables
            foreach (xmlrpc.Group grp in toRemove)
                selectedGroups.Items.Remove(grp);

            sortListbox(availableGroups);
            sortListbox(selectedGroups);

            selectedGroups.EndUpdate();
            availableGroups.EndUpdate();
        }

        private void cancel_Click(object sender, EventArgs e)
        {
            DialogResult = System.Windows.Forms.DialogResult.Cancel;
        }

        private void accept_Click(object sender, EventArgs e)
        {
            if (name.Text.Trim().Length == 0)
            {
                gui.UserNotifier.notifyError(Strings.nameRequired);
                return;
            }
            xmlrpc.Group grp = new xmlrpc.Group();
            grp.idParent = _auth.id; grp.id = ""; grp.name = name.Text; grp.comments = comments.Text; grp.active = active.Checked;

            grp.isMeta = true;
            List<string> groupsIds = new List<string>();
            foreach( xmlrpc.Group g in selectedGroups.Items )
                groupsIds.Add(g.id);

            grp.groupsIds = groupsIds.ToArray();

            try
            {
                if (_id == null)
                {
                    xmlrpc.UdsAdminService.CreateGroup(grp);
                }
                else
                {
                    grp.id = _id;
                    xmlrpc.UdsAdminService.ModifyGroup(grp);
                }
                DialogResult = System.Windows.Forms.DialogResult.OK;
            }
            catch (CookComputing.XmlRpc.XmlRpcFaultException ex)
            {
                gui.UserNotifier.notifyRpcException(ex);
            }

        }
    }
}
