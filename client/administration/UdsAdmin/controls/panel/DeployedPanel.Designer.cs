namespace UdsAdmin.controls.panel
{
    partial class DeployedPanel
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(DeployedPanel));
            this.splitContainer1 = new SplitContainerEx();
            this.listView = new System.Windows.Forms.ListView();
            this.Id = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.friendlyName = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.Revision = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.CreationDate = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.State = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.StatusDate = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.logViewer1 = new UdsAdmin.controls.panel.LogViewer();
            this.splitContainer1.Panel1.SuspendLayout();
            this.splitContainer1.Panel2.SuspendLayout();
            this.splitContainer1.SuspendLayout();
            this.SuspendLayout();
            // 
            // splitContainer1
            // 
            resources.ApplyResources(this.splitContainer1, "splitContainer1");
            this.splitContainer1.Name = "splitContainer1";
            // 
            // splitContainer1.Panel1
            // 
            this.splitContainer1.Panel1.Controls.Add(this.listView);
            // 
            // splitContainer1.Panel2
            // 
            this.splitContainer1.Panel2.Controls.Add(this.logViewer1);
            // 
            // listView
            // 
            this.listView.AutoArrange = false;
            this.listView.Columns.AddRange(new System.Windows.Forms.ColumnHeader[] {
            this.Id,
            this.friendlyName,
            this.Revision,
            this.CreationDate,
            this.State,
            this.StatusDate});
            resources.ApplyResources(this.listView, "listView");
            this.listView.FullRowSelect = true;
            this.listView.GridLines = true;
            this.listView.Name = "listView";
            this.listView.UseCompatibleStateImageBehavior = false;
            this.listView.View = System.Windows.Forms.View.Details;
            this.listView.SelectedIndexChanged += new System.EventHandler(this.listView_SelectedIndexChanged);
            this.listView.KeyUp += new System.Windows.Forms.KeyEventHandler(this.listView_KeyUp);
            this.listView.MouseUp += new System.Windows.Forms.MouseEventHandler(this.listView_MouseUp);
            // 
            // Id
            // 
            resources.ApplyResources(this.Id, "Id");
            // 
            // friendlyName
            // 
            resources.ApplyResources(this.friendlyName, "friendlyName");
            // 
            // Revision
            // 
            resources.ApplyResources(this.Revision, "Revision");
            // 
            // CreationDate
            // 
            resources.ApplyResources(this.CreationDate, "CreationDate");
            // 
            // State
            // 
            resources.ApplyResources(this.State, "State");
            // 
            // StatusDate
            // 
            resources.ApplyResources(this.StatusDate, "StatusDate");
            // 
            // logViewer1
            // 
            resources.ApplyResources(this.logViewer1, "logViewer1");
            this.logViewer1.Name = "logViewer1";
            // 
            // DeployedPanel
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.splitContainer1);
            this.Name = "DeployedPanel";
            this.VisibleChanged += new System.EventHandler(this.DeployedPanel_VisibleChanged);
            this.splitContainer1.Panel1.ResumeLayout(false);
            this.splitContainer1.Panel2.ResumeLayout(false);
            this.splitContainer1.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private SplitContainerEx splitContainer1;
        private LogViewer logViewer1;
        private System.Windows.Forms.ListView listView;
        private System.Windows.Forms.ColumnHeader Id;
        private System.Windows.Forms.ColumnHeader friendlyName;
        private System.Windows.Forms.ColumnHeader Revision;
        private System.Windows.Forms.ColumnHeader CreationDate;
        private System.Windows.Forms.ColumnHeader State;
        private System.Windows.Forms.ColumnHeader StatusDate;

    }
}
