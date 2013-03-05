namespace UdsAdmin.forms
{
    partial class UserForm
    {
        /// <summary>
        /// Variable del diseñador requerida.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Limpiar los recursos que se estén utilizando.
        /// </summary>
        /// <param name="disposing">true si los recursos administrados se deben eliminar; false en caso contrario, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Código generado por el Diseñador de Windows Forms

        /// <summary>
        /// Método necesario para admitir el Diseñador. No se puede modificar
        /// el contenido del método con el editor de código.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(UserForm));
            this.tableLayoutPanel2 = new System.Windows.Forms.TableLayoutPanel();
            this.accept = new System.Windows.Forms.Button();
            this.cancel = new System.Windows.Forms.Button();
            this.tableLayoutPanel3 = new System.Windows.Forms.TableLayoutPanel();
            this.check = new System.Windows.Forms.Button();
            this.tabs = new System.Windows.Forms.TabControl();
            this.user = new System.Windows.Forms.TabPage();
            this.tableLayoutPanel1 = new System.Windows.Forms.TableLayoutPanel();
            this.realName = new System.Windows.Forms.TextBox();
            this.label4 = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.name = new System.Windows.Forms.TextBox();
            this.comments = new System.Windows.Forms.TextBox();
            this.searchButton = new System.Windows.Forms.Button();
            this.userNameLabel = new System.Windows.Forms.Label();
            this.state = new System.Windows.Forms.ComboBox();
            this.passwordLabel = new System.Windows.Forms.Label();
            this.staffMemberLabel = new System.Windows.Forms.Label();
            this.adminLabel = new System.Windows.Forms.Label();
            this.label5 = new System.Windows.Forms.Label();
            this.password = new System.Windows.Forms.TextBox();
            this.staffMember = new System.Windows.Forms.CheckBox();
            this.admin = new System.Windows.Forms.CheckBox();
            this.group = new System.Windows.Forms.TabPage();
            this.groupsList = new System.Windows.Forms.CheckedListBox();
            this.tableLayoutPanel2.SuspendLayout();
            this.tableLayoutPanel3.SuspendLayout();
            this.tabs.SuspendLayout();
            this.user.SuspendLayout();
            this.tableLayoutPanel1.SuspendLayout();
            this.group.SuspendLayout();
            this.SuspendLayout();
            // 
            // tableLayoutPanel2
            // 
            resources.ApplyResources(this.tableLayoutPanel2, "tableLayoutPanel2");
            this.tableLayoutPanel2.Controls.Add(this.accept, 0, 0);
            this.tableLayoutPanel2.Controls.Add(this.cancel, 2, 0);
            this.tableLayoutPanel2.Controls.Add(this.tableLayoutPanel3, 1, 0);
            this.tableLayoutPanel2.Name = "tableLayoutPanel2";
            // 
            // accept
            // 
            resources.ApplyResources(this.accept, "accept");
            this.accept.Name = "accept";
            this.accept.UseVisualStyleBackColor = true;
            this.accept.Click += new System.EventHandler(this.accept_Click);
            // 
            // cancel
            // 
            resources.ApplyResources(this.cancel, "cancel");
            this.cancel.DialogResult = System.Windows.Forms.DialogResult.Cancel;
            this.cancel.Name = "cancel";
            this.cancel.UseVisualStyleBackColor = true;
            this.cancel.Click += new System.EventHandler(this.cancel_Click);
            // 
            // tableLayoutPanel3
            // 
            resources.ApplyResources(this.tableLayoutPanel3, "tableLayoutPanel3");
            this.tableLayoutPanel3.Controls.Add(this.check, 1, 0);
            this.tableLayoutPanel3.Name = "tableLayoutPanel3";
            // 
            // check
            // 
            resources.ApplyResources(this.check, "check");
            this.check.Name = "check";
            this.check.UseVisualStyleBackColor = true;
            // 
            // tabs
            // 
            resources.ApplyResources(this.tabs, "tabs");
            this.tabs.Controls.Add(this.user);
            this.tabs.Controls.Add(this.group);
            this.tabs.Name = "tabs";
            this.tabs.SelectedIndex = 0;
            // 
            // user
            // 
            this.user.Controls.Add(this.tableLayoutPanel1);
            resources.ApplyResources(this.user, "user");
            this.user.Name = "user";
            this.user.UseVisualStyleBackColor = true;
            // 
            // tableLayoutPanel1
            // 
            resources.ApplyResources(this.tableLayoutPanel1, "tableLayoutPanel1");
            this.tableLayoutPanel1.Controls.Add(this.realName, 1, 1);
            this.tableLayoutPanel1.Controls.Add(this.label4, 0, 1);
            this.tableLayoutPanel1.Controls.Add(this.label2, 0, 2);
            this.tableLayoutPanel1.Controls.Add(this.name, 1, 0);
            this.tableLayoutPanel1.Controls.Add(this.comments, 1, 2);
            this.tableLayoutPanel1.Controls.Add(this.searchButton, 2, 0);
            this.tableLayoutPanel1.Controls.Add(this.userNameLabel, 0, 0);
            this.tableLayoutPanel1.Controls.Add(this.state, 1, 3);
            this.tableLayoutPanel1.Controls.Add(this.passwordLabel, 0, 6);
            this.tableLayoutPanel1.Controls.Add(this.staffMemberLabel, 0, 4);
            this.tableLayoutPanel1.Controls.Add(this.adminLabel, 0, 5);
            this.tableLayoutPanel1.Controls.Add(this.label5, 0, 3);
            this.tableLayoutPanel1.Controls.Add(this.password, 1, 6);
            this.tableLayoutPanel1.Controls.Add(this.staffMember, 1, 4);
            this.tableLayoutPanel1.Controls.Add(this.admin, 1, 5);
            this.tableLayoutPanel1.Name = "tableLayoutPanel1";
            // 
            // realName
            // 
            this.tableLayoutPanel1.SetColumnSpan(this.realName, 2);
            resources.ApplyResources(this.realName, "realName");
            this.realName.Name = "realName";
            // 
            // label4
            // 
            resources.ApplyResources(this.label4, "label4");
            this.label4.Name = "label4";
            // 
            // label2
            // 
            resources.ApplyResources(this.label2, "label2");
            this.label2.Name = "label2";
            // 
            // name
            // 
            resources.ApplyResources(this.name, "name");
            this.name.Name = "name";
            // 
            // comments
            // 
            this.tableLayoutPanel1.SetColumnSpan(this.comments, 2);
            resources.ApplyResources(this.comments, "comments");
            this.comments.Name = "comments";
            // 
            // searchButton
            // 
            this.searchButton.Image = global::UdsAdmin.Images.find16;
            resources.ApplyResources(this.searchButton, "searchButton");
            this.searchButton.Name = "searchButton";
            this.searchButton.UseVisualStyleBackColor = true;
            this.searchButton.Click += new System.EventHandler(this.searchButton_Click_1);
            // 
            // userNameLabel
            // 
            resources.ApplyResources(this.userNameLabel, "userNameLabel");
            this.userNameLabel.Name = "userNameLabel";
            // 
            // state
            // 
            this.tableLayoutPanel1.SetColumnSpan(this.state, 2);
            resources.ApplyResources(this.state, "state");
            this.state.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.state.FormattingEnabled = true;
            this.state.Name = "state";
            // 
            // passwordLabel
            // 
            resources.ApplyResources(this.passwordLabel, "passwordLabel");
            this.passwordLabel.Name = "passwordLabel";
            // 
            // staffMemberLabel
            // 
            resources.ApplyResources(this.staffMemberLabel, "staffMemberLabel");
            this.staffMemberLabel.Name = "staffMemberLabel";
            // 
            // adminLabel
            // 
            resources.ApplyResources(this.adminLabel, "adminLabel");
            this.adminLabel.Name = "adminLabel";
            // 
            // label5
            // 
            resources.ApplyResources(this.label5, "label5");
            this.label5.Name = "label5";
            // 
            // password
            // 
            this.tableLayoutPanel1.SetColumnSpan(this.password, 2);
            resources.ApplyResources(this.password, "password");
            this.password.Name = "password";
            this.password.UseSystemPasswordChar = true;
            // 
            // staffMember
            // 
            resources.ApplyResources(this.staffMember, "staffMember");
            this.staffMember.Name = "staffMember";
            this.staffMember.UseVisualStyleBackColor = true;
            // 
            // admin
            // 
            resources.ApplyResources(this.admin, "admin");
            this.admin.Name = "admin";
            this.admin.UseVisualStyleBackColor = true;
            // 
            // group
            // 
            this.group.Controls.Add(this.groupsList);
            resources.ApplyResources(this.group, "group");
            this.group.Name = "group";
            this.group.UseVisualStyleBackColor = true;
            // 
            // groupsList
            // 
            this.groupsList.CheckOnClick = true;
            this.groupsList.FormattingEnabled = true;
            resources.ApplyResources(this.groupsList, "groupsList");
            this.groupsList.Name = "groupsList";
            // 
            // UserForm
            // 
            this.AcceptButton = this.accept;
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.CancelButton = this.cancel;
            this.Controls.Add(this.tabs);
            this.Controls.Add(this.tableLayoutPanel2);
            this.Name = "UserForm";
            this.Load += new System.EventHandler(this.UserForm_Load);
            this.tableLayoutPanel2.ResumeLayout(false);
            this.tableLayoutPanel3.ResumeLayout(false);
            this.tabs.ResumeLayout(false);
            this.user.ResumeLayout(false);
            this.tableLayoutPanel1.ResumeLayout(false);
            this.tableLayoutPanel1.PerformLayout();
            this.group.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel2;
        private System.Windows.Forms.Button accept;
        private System.Windows.Forms.Button cancel;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel3;
        private System.Windows.Forms.Button check;
        private System.Windows.Forms.TabControl tabs;
        private System.Windows.Forms.TabPage user;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel1;
        private System.Windows.Forms.Label staffMemberLabel;
        private System.Windows.Forms.Label label2;
        public System.Windows.Forms.TextBox name;
        public System.Windows.Forms.TextBox comments;
        private System.Windows.Forms.Button searchButton;
        private System.Windows.Forms.TabPage group;
        private System.Windows.Forms.CheckedListBox groupsList;
        public System.Windows.Forms.TextBox realName;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.ComboBox state;
        public System.Windows.Forms.TextBox password;
        private System.Windows.Forms.Label passwordLabel;
        private System.Windows.Forms.Label adminLabel;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.CheckBox staffMember;
        private System.Windows.Forms.CheckBox admin;
        private System.Windows.Forms.Label userNameLabel;
    }
}