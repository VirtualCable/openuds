namespace uds.gui.forms
{
    partial class Config
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(Config));
            this.label1 = new System.Windows.Forms.Label();
            this.brokerAddress = new System.Windows.Forms.TextBox();
            this.label2 = new System.Windows.Forms.Label();
            this.useSecureConnection = new System.Windows.Forms.ComboBox();
            this.testConnectionButton = new System.Windows.Forms.Button();
            this.acceptButton = new System.Windows.Forms.Button();
            this.cancelButton = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // label1
            // 
            resources.ApplyResources(this.label1, "label1");
            this.label1.Name = "label1";
            // 
            // brokerAddress
            // 
            resources.ApplyResources(this.brokerAddress, "brokerAddress");
            this.brokerAddress.Name = "brokerAddress";
            // 
            // label2
            // 
            resources.ApplyResources(this.label2, "label2");
            this.label2.Name = "label2";
            // 
            // useSecureConnection
            // 
            resources.ApplyResources(this.useSecureConnection, "useSecureConnection");
            this.useSecureConnection.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.useSecureConnection.FormattingEnabled = true;
            this.useSecureConnection.Items.AddRange(new object[] {
            resources.GetString("useSecureConnection.Items"),
            resources.GetString("useSecureConnection.Items1")});
            this.useSecureConnection.Name = "useSecureConnection";
            // 
            // testConnectionButton
            // 
            resources.ApplyResources(this.testConnectionButton, "testConnectionButton");
            this.testConnectionButton.Name = "testConnectionButton";
            this.testConnectionButton.UseVisualStyleBackColor = true;
            this.testConnectionButton.Click += new System.EventHandler(this.testConnectionButton_Click);
            // 
            // acceptButton
            // 
            resources.ApplyResources(this.acceptButton, "acceptButton");
            this.acceptButton.Name = "acceptButton";
            this.acceptButton.UseVisualStyleBackColor = true;
            this.acceptButton.Click += new System.EventHandler(this.acceptButton_Click);
            // 
            // cancelButton
            // 
            resources.ApplyResources(this.cancelButton, "cancelButton");
            this.cancelButton.Name = "cancelButton";
            this.cancelButton.UseVisualStyleBackColor = true;
            this.cancelButton.Click += new System.EventHandler(this.cancelButton_Click);
            // 
            // Config
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.cancelButton);
            this.Controls.Add(this.acceptButton);
            this.Controls.Add(this.testConnectionButton);
            this.Controls.Add(this.useSecureConnection);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.brokerAddress);
            this.Controls.Add(this.label1);
            this.Name = "Config";
            this.Load += new System.EventHandler(this.Config_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.TextBox brokerAddress;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.ComboBox useSecureConnection;
        private System.Windows.Forms.Button testConnectionButton;
        private System.Windows.Forms.Button acceptButton;
        private System.Windows.Forms.Button cancelButton;
    }
}