namespace UdsAdmin.controls
{
    public partial class ListEditor
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

        #region Código generado por el Diseñador de componentes

        /// <summary> 
        /// Método necesario para admitir el Diseñador. No se puede modificar 
        /// el contenido del método con el editor de código.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(ListEditor));
            this.bntOpen = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // bntOpen
            // 
            resources.ApplyResources(this.bntOpen, "bntOpen");
            this.bntOpen.Name = "bntOpen";
            this.bntOpen.UseVisualStyleBackColor = true;
            this.bntOpen.Click += new System.EventHandler(this.bntOpen_Click);
            // 
            // ListEditor
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.bntOpen);
            this.Name = "ListEditor";
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.Button bntOpen;

    }
}
