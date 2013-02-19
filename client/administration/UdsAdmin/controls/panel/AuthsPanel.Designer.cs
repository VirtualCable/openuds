namespace UdsAdmin.controls.panel
{
    partial class AuthsPanel
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(AuthsPanel));
            this.splitContainer1 = new UdsAdmin.controls.SplitContainerEx();
            this.listView = new System.Windows.Forms.ListView();
            this.name = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.typeName = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.comments = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
            this.priority = ((System.Windows.Forms.ColumnHeader)(new System.Windows.Forms.ColumnHeader()));
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
            this.name,
            this.typeName,
            this.comments,
            this.priority});
            resources.ApplyResources(this.listView, "listView");
            this.listView.FullRowSelect = true;
            this.listView.GridLines = true;
            this.listView.Name = "listView";
            this.listView.UseCompatibleStateImageBehavior = false;
            this.listView.View = System.Windows.Forms.View.Details;
            this.listView.ColumnClick += new System.Windows.Forms.ColumnClickEventHandler(this.listView_ColumnClick);
            this.listView.SelectedIndexChanged += new System.EventHandler(this.listView_SelectedIndexChanged);
            this.listView.KeyUp += new System.Windows.Forms.KeyEventHandler(this.listView_KeyUp);
            // 
            // name
            // 
            resources.ApplyResources(this.name, "name");
            this.name.Width = global::UdsAdmin.Properties.Settings.Default.wNameCol;
            // 
            // typeName
            // 
            resources.ApplyResources(this.typeName, "typeName");
            // 
            // comments
            // 
            resources.ApplyResources(this.comments, "comments");
            this.comments.Width = global::UdsAdmin.Properties.Settings.Default.wCommentsCol;
            // 
            // priority
            // 
            resources.ApplyResources(this.priority, "priority");
            // 
            // logViewer1
            // 
            resources.ApplyResources(this.logViewer1, "logViewer1");
            this.logViewer1.Name = "logViewer1";
            // 
            // AuthsPanel
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.splitContainer1);
            this.Name = "AuthsPanel";
            this.VisibleChanged += new System.EventHandler(this.UsersPanel_VisibleChanged);
            this.Resize += new System.EventHandler(this.AuthsPanel_Resize);
            this.splitContainer1.Panel1.ResumeLayout(false);
            this.splitContainer1.Panel2.ResumeLayout(false);
            this.splitContainer1.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.ListView listView;
        private System.Windows.Forms.ColumnHeader name;
        private System.Windows.Forms.ColumnHeader comments;
        private System.Windows.Forms.ColumnHeader typeName;
        private System.Windows.Forms.ColumnHeader priority;
        private SplitContainerEx splitContainer1;
        private LogViewer logViewer1;
    }
}
