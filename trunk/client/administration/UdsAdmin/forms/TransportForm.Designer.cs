namespace UdsAdmin.forms
{
    partial class TransportForm
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(TransportForm));
            this.tableLayoutPanel1 = new System.Windows.Forms.TableLayoutPanel();
            this.accept = new System.Windows.Forms.Button();
            this.cancel = new System.Windows.Forms.Button();
            this.tabs = new System.Windows.Forms.TabControl();
            this.commonPage = new System.Windows.Forms.TabPage();
            this.groupData = new System.Windows.Forms.GroupBox();
            this.dataPanel = new System.Windows.Forms.TableLayoutPanel();
            this.groupBox1 = new System.Windows.Forms.GroupBox();
            this.tableLayoutPanel2 = new System.Windows.Forms.TableLayoutPanel();
            this.label3 = new System.Windows.Forms.Label();
            this.comments = new System.Windows.Forms.TextBox();
            this.label2 = new System.Windows.Forms.Label();
            this.name = new System.Windows.Forms.TextBox();
            this.label1 = new System.Windows.Forms.Label();
            this.priority = new System.Windows.Forms.NumericUpDown();
            this.networks = new System.Windows.Forms.TabPage();
            this.positiveNets = new System.Windows.Forms.CheckBox();
            this.label4 = new System.Windows.Forms.Label();
            this.nets = new System.Windows.Forms.CheckedListBox();
            this.tableLayoutPanel1.SuspendLayout();
            this.tabs.SuspendLayout();
            this.commonPage.SuspendLayout();
            this.groupData.SuspendLayout();
            this.groupBox1.SuspendLayout();
            this.tableLayoutPanel2.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.priority)).BeginInit();
            this.networks.SuspendLayout();
            this.SuspendLayout();
            // 
            // tableLayoutPanel1
            // 
            resources.ApplyResources(this.tableLayoutPanel1, "tableLayoutPanel1");
            this.tableLayoutPanel1.Controls.Add(this.accept, 0, 0);
            this.tableLayoutPanel1.Controls.Add(this.cancel, 2, 0);
            this.tableLayoutPanel1.Name = "tableLayoutPanel1";
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
            // 
            // tabs
            // 
            resources.ApplyResources(this.tabs, "tabs");
            this.tabs.Controls.Add(this.commonPage);
            this.tabs.Controls.Add(this.networks);
            this.tabs.Name = "tabs";
            this.tabs.SelectedIndex = 0;
            // 
            // commonPage
            // 
            this.commonPage.Controls.Add(this.groupData);
            this.commonPage.Controls.Add(this.groupBox1);
            resources.ApplyResources(this.commonPage, "commonPage");
            this.commonPage.Name = "commonPage";
            this.commonPage.UseVisualStyleBackColor = true;
            // 
            // groupData
            // 
            resources.ApplyResources(this.groupData, "groupData");
            this.groupData.Controls.Add(this.dataPanel);
            this.groupData.Name = "groupData";
            this.groupData.TabStop = false;
            // 
            // dataPanel
            // 
            resources.ApplyResources(this.dataPanel, "dataPanel");
            this.dataPanel.Name = "dataPanel";
            // 
            // groupBox1
            // 
            resources.ApplyResources(this.groupBox1, "groupBox1");
            this.groupBox1.Controls.Add(this.tableLayoutPanel2);
            this.groupBox1.Name = "groupBox1";
            this.groupBox1.TabStop = false;
            // 
            // tableLayoutPanel2
            // 
            resources.ApplyResources(this.tableLayoutPanel2, "tableLayoutPanel2");
            this.tableLayoutPanel2.Controls.Add(this.label3, 0, 2);
            this.tableLayoutPanel2.Controls.Add(this.comments, 1, 1);
            this.tableLayoutPanel2.Controls.Add(this.label2, 0, 1);
            this.tableLayoutPanel2.Controls.Add(this.name, 1, 0);
            this.tableLayoutPanel2.Controls.Add(this.label1, 0, 0);
            this.tableLayoutPanel2.Controls.Add(this.priority, 1, 2);
            this.tableLayoutPanel2.Name = "tableLayoutPanel2";
            // 
            // label3
            // 
            resources.ApplyResources(this.label3, "label3");
            this.label3.Name = "label3";
            // 
            // comments
            // 
            resources.ApplyResources(this.comments, "comments");
            this.comments.Name = "comments";
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
            // label1
            // 
            resources.ApplyResources(this.label1, "label1");
            this.label1.Name = "label1";
            // 
            // priority
            // 
            resources.ApplyResources(this.priority, "priority");
            this.priority.Maximum = new decimal(new int[] {
            10,
            0,
            0,
            0});
            this.priority.Minimum = new decimal(new int[] {
            10,
            0,
            0,
            -2147483648});
            this.priority.Name = "priority";
            this.priority.Value = new decimal(new int[] {
            1,
            0,
            0,
            0});
            // 
            // networks
            // 
            this.networks.Controls.Add(this.positiveNets);
            this.networks.Controls.Add(this.label4);
            this.networks.Controls.Add(this.nets);
            resources.ApplyResources(this.networks, "networks");
            this.networks.Name = "networks";
            this.networks.UseVisualStyleBackColor = true;
            // 
            // positiveNets
            // 
            resources.ApplyResources(this.positiveNets, "positiveNets");
            this.positiveNets.AutoEllipsis = true;
            this.positiveNets.Checked = true;
            this.positiveNets.CheckState = System.Windows.Forms.CheckState.Checked;
            this.positiveNets.Name = "positiveNets";
            this.positiveNets.UseVisualStyleBackColor = true;
            this.positiveNets.CheckedChanged += new System.EventHandler(this.positiveNets_CheckedChanged);
            // 
            // label4
            // 
            resources.ApplyResources(this.label4, "label4");
            this.label4.Name = "label4";
            // 
            // nets
            // 
            resources.ApplyResources(this.nets, "nets");
            this.nets.FormattingEnabled = true;
            this.nets.Name = "nets";
            // 
            // TransportForm
            // 
            this.AcceptButton = this.accept;
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.CancelButton = this.cancel;
            this.Controls.Add(this.tabs);
            this.Controls.Add(this.tableLayoutPanel1);
            this.DoubleBuffered = true;
            this.Name = "TransportForm";
            this.Load += new System.EventHandler(this.Transport_Load);
            this.tableLayoutPanel1.ResumeLayout(false);
            this.tabs.ResumeLayout(false);
            this.commonPage.ResumeLayout(false);
            this.groupData.ResumeLayout(false);
            this.groupBox1.ResumeLayout(false);
            this.tableLayoutPanel2.ResumeLayout(false);
            this.tableLayoutPanel2.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.priority)).EndInit();
            this.networks.ResumeLayout(false);
            this.networks.PerformLayout();
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel1;
        private System.Windows.Forms.Button accept;
        private System.Windows.Forms.Button cancel;
        private System.Windows.Forms.TabControl tabs;
        private System.Windows.Forms.TabPage commonPage;
        private System.Windows.Forms.GroupBox groupData;
        private System.Windows.Forms.TableLayoutPanel dataPanel;
        private System.Windows.Forms.GroupBox groupBox1;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel2;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.TextBox comments;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.TextBox name;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.NumericUpDown priority;
        private System.Windows.Forms.TabPage networks;
        private System.Windows.Forms.CheckedListBox nets;
        private System.Windows.Forms.CheckBox positiveNets;
        private System.Windows.Forms.Label label4;

    }
}