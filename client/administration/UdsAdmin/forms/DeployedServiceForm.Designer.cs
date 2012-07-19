namespace UdsAdmin.forms
{
    partial class DeployedServiceForm
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(DeployedServiceForm));
            this.tabs = new System.Windows.Forms.TabControl();
            this.Service = new System.Windows.Forms.TabPage();
            this.publishOnSave = new System.Windows.Forms.CheckBox();
            this.tableLayoutPanel2 = new System.Windows.Forms.TableLayoutPanel();
            this.label3 = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.osManagerCombo = new System.Windows.Forms.ComboBox();
            this.baseServiceCombo = new System.Windows.Forms.ComboBox();
            this.label9 = new System.Windows.Forms.Label();
            this.label8 = new System.Windows.Forms.Label();
            this.nameBox = new System.Windows.Forms.TextBox();
            this.commentsBox = new System.Windows.Forms.TextBox();
            this.Transports = new System.Windows.Forms.TabPage();
            this.tableLayoutPanel3 = new System.Windows.Forms.TableLayoutPanel();
            this.label4 = new System.Windows.Forms.Label();
            this.allowedTransports = new System.Windows.Forms.CheckedListBox();
            this.Cache = new System.Windows.Forms.TabPage();
            this.tableLayoutPanel4 = new System.Windows.Forms.TableLayoutPanel();
            this.cacheL2ServicesBox = new System.Windows.Forms.NumericUpDown();
            this.cacheL2Label = new System.Windows.Forms.Label();
            this.cacheServicesBox = new System.Windows.Forms.NumericUpDown();
            this.label5 = new System.Windows.Forms.Label();
            this.cacheLabel = new System.Windows.Forms.Label();
            this.initialServicesBox = new System.Windows.Forms.NumericUpDown();
            this.label7 = new System.Windows.Forms.Label();
            this.maxServicesBox = new System.Windows.Forms.NumericUpDown();
            this.tableLayoutPanel1 = new System.Windows.Forms.TableLayoutPanel();
            this.accept = new System.Windows.Forms.Button();
            this.cancel = new System.Windows.Forms.Button();
            this.tabs.SuspendLayout();
            this.Service.SuspendLayout();
            this.tableLayoutPanel2.SuspendLayout();
            this.Transports.SuspendLayout();
            this.tableLayoutPanel3.SuspendLayout();
            this.Cache.SuspendLayout();
            this.tableLayoutPanel4.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.cacheL2ServicesBox)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.cacheServicesBox)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.initialServicesBox)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.maxServicesBox)).BeginInit();
            this.tableLayoutPanel1.SuspendLayout();
            this.SuspendLayout();
            // 
            // tabs
            // 
            resources.ApplyResources(this.tabs, "tabs");
            this.tabs.Controls.Add(this.Service);
            this.tabs.Controls.Add(this.Transports);
            this.tabs.Controls.Add(this.Cache);
            this.tabs.Name = "tabs";
            this.tabs.SelectedIndex = 0;
            // 
            // Service
            // 
            this.Service.BackColor = System.Drawing.Color.Transparent;
            this.Service.Controls.Add(this.publishOnSave);
            this.Service.Controls.Add(this.tableLayoutPanel2);
            resources.ApplyResources(this.Service, "Service");
            this.Service.Name = "Service";
            this.Service.UseVisualStyleBackColor = true;
            // 
            // publishOnSave
            // 
            resources.ApplyResources(this.publishOnSave, "publishOnSave");
            this.publishOnSave.Name = "publishOnSave";
            this.publishOnSave.UseVisualStyleBackColor = true;
            // 
            // tableLayoutPanel2
            // 
            resources.ApplyResources(this.tableLayoutPanel2, "tableLayoutPanel2");
            this.tableLayoutPanel2.Controls.Add(this.label3, 0, 3);
            this.tableLayoutPanel2.Controls.Add(this.label1, 0, 2);
            this.tableLayoutPanel2.Controls.Add(this.osManagerCombo, 1, 3);
            this.tableLayoutPanel2.Controls.Add(this.baseServiceCombo, 1, 2);
            this.tableLayoutPanel2.Controls.Add(this.label9, 0, 0);
            this.tableLayoutPanel2.Controls.Add(this.label8, 0, 1);
            this.tableLayoutPanel2.Controls.Add(this.nameBox, 1, 0);
            this.tableLayoutPanel2.Controls.Add(this.commentsBox, 1, 1);
            this.tableLayoutPanel2.Name = "tableLayoutPanel2";
            // 
            // label3
            // 
            resources.ApplyResources(this.label3, "label3");
            this.label3.Name = "label3";
            // 
            // label1
            // 
            resources.ApplyResources(this.label1, "label1");
            this.label1.Name = "label1";
            // 
            // osManagerCombo
            // 
            resources.ApplyResources(this.osManagerCombo, "osManagerCombo");
            this.osManagerCombo.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.osManagerCombo.FormattingEnabled = true;
            this.osManagerCombo.Name = "osManagerCombo";
            // 
            // baseServiceCombo
            // 
            resources.ApplyResources(this.baseServiceCombo, "baseServiceCombo");
            this.baseServiceCombo.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.baseServiceCombo.FormattingEnabled = true;
            this.baseServiceCombo.Name = "baseServiceCombo";
            this.baseServiceCombo.SelectionChangeCommitted += new System.EventHandler(this.baseServiceCombo_SelectionChangeCommitted);
            // 
            // label9
            // 
            resources.ApplyResources(this.label9, "label9");
            this.label9.Name = "label9";
            // 
            // label8
            // 
            resources.ApplyResources(this.label8, "label8");
            this.label8.Name = "label8";
            // 
            // nameBox
            // 
            resources.ApplyResources(this.nameBox, "nameBox");
            this.nameBox.Name = "nameBox";
            // 
            // commentsBox
            // 
            resources.ApplyResources(this.commentsBox, "commentsBox");
            this.commentsBox.Name = "commentsBox";
            // 
            // Transports
            // 
            this.Transports.Controls.Add(this.tableLayoutPanel3);
            resources.ApplyResources(this.Transports, "Transports");
            this.Transports.Name = "Transports";
            this.Transports.UseVisualStyleBackColor = true;
            // 
            // tableLayoutPanel3
            // 
            resources.ApplyResources(this.tableLayoutPanel3, "tableLayoutPanel3");
            this.tableLayoutPanel3.Controls.Add(this.label4, 0, 0);
            this.tableLayoutPanel3.Controls.Add(this.allowedTransports, 0, 1);
            this.tableLayoutPanel3.Name = "tableLayoutPanel3";
            // 
            // label4
            // 
            resources.ApplyResources(this.label4, "label4");
            this.label4.Name = "label4";
            // 
            // allowedTransports
            // 
            resources.ApplyResources(this.allowedTransports, "allowedTransports");
            this.allowedTransports.FormattingEnabled = true;
            this.allowedTransports.Name = "allowedTransports";
            // 
            // Cache
            // 
            this.Cache.Controls.Add(this.tableLayoutPanel4);
            resources.ApplyResources(this.Cache, "Cache");
            this.Cache.Name = "Cache";
            this.Cache.UseVisualStyleBackColor = true;
            // 
            // tableLayoutPanel4
            // 
            resources.ApplyResources(this.tableLayoutPanel4, "tableLayoutPanel4");
            this.tableLayoutPanel4.Controls.Add(this.cacheL2ServicesBox, 1, 2);
            this.tableLayoutPanel4.Controls.Add(this.cacheL2Label, 0, 2);
            this.tableLayoutPanel4.Controls.Add(this.cacheServicesBox, 1, 1);
            this.tableLayoutPanel4.Controls.Add(this.label5, 0, 0);
            this.tableLayoutPanel4.Controls.Add(this.cacheLabel, 0, 1);
            this.tableLayoutPanel4.Controls.Add(this.initialServicesBox, 1, 0);
            this.tableLayoutPanel4.Controls.Add(this.label7, 0, 3);
            this.tableLayoutPanel4.Controls.Add(this.maxServicesBox, 1, 3);
            this.tableLayoutPanel4.Name = "tableLayoutPanel4";
            // 
            // cacheL2ServicesBox
            // 
            resources.ApplyResources(this.cacheL2ServicesBox, "cacheL2ServicesBox");
            this.cacheL2ServicesBox.Name = "cacheL2ServicesBox";
            // 
            // cacheL2Label
            // 
            resources.ApplyResources(this.cacheL2Label, "cacheL2Label");
            this.cacheL2Label.Name = "cacheL2Label";
            // 
            // cacheServicesBox
            // 
            resources.ApplyResources(this.cacheServicesBox, "cacheServicesBox");
            this.cacheServicesBox.Name = "cacheServicesBox";
            // 
            // label5
            // 
            resources.ApplyResources(this.label5, "label5");
            this.label5.Name = "label5";
            // 
            // cacheLabel
            // 
            resources.ApplyResources(this.cacheLabel, "cacheLabel");
            this.cacheLabel.Name = "cacheLabel";
            // 
            // initialServicesBox
            // 
            resources.ApplyResources(this.initialServicesBox, "initialServicesBox");
            this.initialServicesBox.Name = "initialServicesBox";
            // 
            // label7
            // 
            resources.ApplyResources(this.label7, "label7");
            this.label7.Name = "label7";
            // 
            // maxServicesBox
            // 
            resources.ApplyResources(this.maxServicesBox, "maxServicesBox");
            this.maxServicesBox.Name = "maxServicesBox";
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
            // DeployedServiceForm
            // 
            this.AcceptButton = this.accept;
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.CancelButton = this.cancel;
            this.Controls.Add(this.tableLayoutPanel1);
            this.Controls.Add(this.tabs);
            this.Name = "DeployedServiceForm";
            this.Load += new System.EventHandler(this.DeployedServiceForm_Load);
            this.tabs.ResumeLayout(false);
            this.Service.ResumeLayout(false);
            this.Service.PerformLayout();
            this.tableLayoutPanel2.ResumeLayout(false);
            this.tableLayoutPanel2.PerformLayout();
            this.Transports.ResumeLayout(false);
            this.tableLayoutPanel3.ResumeLayout(false);
            this.tableLayoutPanel3.PerformLayout();
            this.Cache.ResumeLayout(false);
            this.tableLayoutPanel4.ResumeLayout(false);
            this.tableLayoutPanel4.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.cacheL2ServicesBox)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.cacheServicesBox)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.initialServicesBox)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.maxServicesBox)).EndInit();
            this.tableLayoutPanel1.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.TabControl tabs;
        private System.Windows.Forms.TabPage Service;
        private System.Windows.Forms.TabPage Transports;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel1;
        private System.Windows.Forms.Button accept;
        private System.Windows.Forms.Button cancel;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel2;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel3;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.CheckedListBox allowedTransports;
        private System.Windows.Forms.TabPage Cache;
        private System.Windows.Forms.ComboBox osManagerCombo;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel4;
        private System.Windows.Forms.NumericUpDown maxServicesBox;
        private System.Windows.Forms.NumericUpDown cacheServicesBox;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.Label cacheLabel;
        private System.Windows.Forms.Label label7;
        private System.Windows.Forms.NumericUpDown initialServicesBox;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.ComboBox baseServiceCombo;
        private System.Windows.Forms.Label label9;
        private System.Windows.Forms.Label label8;
        private System.Windows.Forms.TextBox nameBox;
        private System.Windows.Forms.TextBox commentsBox;
        private System.Windows.Forms.NumericUpDown cacheL2ServicesBox;
        private System.Windows.Forms.Label cacheL2Label;
        private System.Windows.Forms.CheckBox publishOnSave;
    }
}