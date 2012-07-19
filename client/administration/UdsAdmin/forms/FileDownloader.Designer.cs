namespace UdsAdmin.forms
{
    partial class FileDownloader
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(FileDownloader));
            this.progress = new System.Windows.Forms.ProgressBar();
            this.info = new System.Windows.Forms.Label();
            this.cancel = new System.Windows.Forms.Button();
            this.bgTask = new System.ComponentModel.BackgroundWorker();
            this.install = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // progress
            // 
            resources.ApplyResources(this.progress, "progress");
            this.progress.Name = "progress";
            this.progress.Style = System.Windows.Forms.ProgressBarStyle.Continuous;
            // 
            // info
            // 
            resources.ApplyResources(this.info, "info");
            this.info.Name = "info";
            // 
            // cancel
            // 
            resources.ApplyResources(this.cancel, "cancel");
            this.cancel.Name = "cancel";
            this.cancel.UseVisualStyleBackColor = true;
            this.cancel.Click += new System.EventHandler(this.cancel_Click);
            // 
            // bgTask
            // 
            this.bgTask.WorkerSupportsCancellation = true;
            this.bgTask.DoWork += new System.ComponentModel.DoWorkEventHandler(this.bgTask_DoWork);
            // 
            // install
            // 
            resources.ApplyResources(this.install, "install");
            this.install.Name = "install";
            this.install.UseVisualStyleBackColor = true;
            this.install.Click += new System.EventHandler(this.install_Click);
            // 
            // FileDownloader
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.install);
            this.Controls.Add(this.cancel);
            this.Controls.Add(this.info);
            this.Controls.Add(this.progress);
            this.Name = "FileDownloader";
            this.Load += new System.EventHandler(this.FileDownloader_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.ProgressBar progress;
        private System.Windows.Forms.Label info;
        private System.Windows.Forms.Button cancel;
        private System.ComponentModel.BackgroundWorker bgTask;
        private System.Windows.Forms.Button install;
    }
}