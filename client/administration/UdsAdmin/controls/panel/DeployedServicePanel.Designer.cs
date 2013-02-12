namespace UdsAdmin.controls.panel
{
    partial class DeployedServicePanel
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(DeployedServicePanel));
            this.tabControl1 = new System.Windows.Forms.TabControl();
            this.tabPage1 = new System.Windows.Forms.TabPage();
            this.splitContainer1 = new System.Windows.Forms.SplitContainer();
            this.label4 = new System.Windows.Forms.Label();
            this.tableLayoutPanel1 = new System.Windows.Forms.TableLayoutPanel();
            this.groupLabel = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.lName = new System.Windows.Forms.Label();
            this.lComments = new System.Windows.Forms.Label();
            this.lBaseService = new System.Windows.Forms.Label();
            this.label3 = new System.Windows.Forms.Label();
            this.lOsManager = new System.Windows.Forms.Label();
            this.lInitial = new System.Windows.Forms.Label();
            this.cacheLabel = new System.Windows.Forms.Label();
            this.lCache = new System.Windows.Forms.Label();
            this.cacheL2Label = new System.Windows.Forms.Label();
            this.lL2Cache = new System.Windows.Forms.Label();
            this.lMax = new System.Windows.Forms.Label();
            this.label6 = new System.Windows.Forms.Label();
            this.lState = new System.Windows.Forms.Label();
            this.label10 = new System.Windows.Forms.Label();
            this.label7 = new System.Windows.Forms.Label();
            this.tabPage2 = new System.Windows.Forms.TabPage();
            this.tableLayoutPanel2 = new System.Windows.Forms.TableLayoutPanel();
            this.logViewer1 = new UdsAdmin.controls.panel.LogViewer();
            this.inUseChart = new UdsAdmin.controls.panel.ChartPanel();
            this.assignedChart = new UdsAdmin.controls.panel.ChartPanel();
            this.tabControl1.SuspendLayout();
            this.tabPage1.SuspendLayout();
            this.splitContainer1.Panel1.SuspendLayout();
            this.splitContainer1.Panel2.SuspendLayout();
            this.splitContainer1.SuspendLayout();
            this.tableLayoutPanel1.SuspendLayout();
            this.tabPage2.SuspendLayout();
            this.tableLayoutPanel2.SuspendLayout();
            this.SuspendLayout();
            // 
            // tabControl1
            // 
            this.tabControl1.Controls.Add(this.tabPage1);
            this.tabControl1.Controls.Add(this.tabPage2);
            resources.ApplyResources(this.tabControl1, "tabControl1");
            this.tabControl1.Name = "tabControl1";
            this.tabControl1.SelectedIndex = 0;
            this.tabControl1.SelectedIndexChanged += new System.EventHandler(this.tabControl1_SelectedIndexChanged);
            this.tabControl1.KeyUp += new System.Windows.Forms.KeyEventHandler(this.tabControl1_KeyUp);
            // 
            // tabPage1
            // 
            this.tabPage1.Controls.Add(this.splitContainer1);
            resources.ApplyResources(this.tabPage1, "tabPage1");
            this.tabPage1.Name = "tabPage1";
            this.tabPage1.UseVisualStyleBackColor = true;
            // 
            // splitContainer1
            // 
            resources.ApplyResources(this.splitContainer1, "splitContainer1");
            this.splitContainer1.Name = "splitContainer1";
            // 
            // splitContainer1.Panel1
            // 
            this.splitContainer1.Panel1.Controls.Add(this.label4);
            this.splitContainer1.Panel1.Controls.Add(this.tableLayoutPanel1);
            // 
            // splitContainer1.Panel2
            // 
            this.splitContainer1.Panel2.Controls.Add(this.logViewer1);
            // 
            // label4
            // 
            resources.ApplyResources(this.label4, "label4");
            this.label4.Name = "label4";
            this.label4.UseMnemonic = false;
            // 
            // tableLayoutPanel1
            // 
            resources.ApplyResources(this.tableLayoutPanel1, "tableLayoutPanel1");
            this.tableLayoutPanel1.Controls.Add(this.groupLabel, 0, 0);
            this.tableLayoutPanel1.Controls.Add(this.label2, 0, 1);
            this.tableLayoutPanel1.Controls.Add(this.label1, 0, 2);
            this.tableLayoutPanel1.Controls.Add(this.lName, 1, 0);
            this.tableLayoutPanel1.Controls.Add(this.lComments, 1, 1);
            this.tableLayoutPanel1.Controls.Add(this.lBaseService, 1, 2);
            this.tableLayoutPanel1.Controls.Add(this.label3, 0, 3);
            this.tableLayoutPanel1.Controls.Add(this.lOsManager, 1, 3);
            this.tableLayoutPanel1.Controls.Add(this.lInitial, 1, 4);
            this.tableLayoutPanel1.Controls.Add(this.cacheLabel, 0, 5);
            this.tableLayoutPanel1.Controls.Add(this.lCache, 1, 5);
            this.tableLayoutPanel1.Controls.Add(this.cacheL2Label, 0, 6);
            this.tableLayoutPanel1.Controls.Add(this.lL2Cache, 1, 6);
            this.tableLayoutPanel1.Controls.Add(this.lMax, 1, 7);
            this.tableLayoutPanel1.Controls.Add(this.label6, 0, 8);
            this.tableLayoutPanel1.Controls.Add(this.lState, 1, 8);
            this.tableLayoutPanel1.Controls.Add(this.label10, 0, 4);
            this.tableLayoutPanel1.Controls.Add(this.label7, 0, 7);
            this.tableLayoutPanel1.Name = "tableLayoutPanel1";
            // 
            // groupLabel
            // 
            resources.ApplyResources(this.groupLabel, "groupLabel");
            this.groupLabel.CausesValidation = false;
            this.groupLabel.Name = "groupLabel";
            // 
            // label2
            // 
            resources.ApplyResources(this.label2, "label2");
            this.label2.CausesValidation = false;
            this.label2.Name = "label2";
            // 
            // label1
            // 
            resources.ApplyResources(this.label1, "label1");
            this.label1.CausesValidation = false;
            this.label1.Name = "label1";
            // 
            // lName
            // 
            resources.ApplyResources(this.lName, "lName");
            this.lName.BackColor = System.Drawing.Color.Transparent;
            this.lName.Name = "lName";
            // 
            // lComments
            // 
            resources.ApplyResources(this.lComments, "lComments");
            this.lComments.BackColor = System.Drawing.Color.Transparent;
            this.lComments.Name = "lComments";
            // 
            // lBaseService
            // 
            resources.ApplyResources(this.lBaseService, "lBaseService");
            this.lBaseService.BackColor = System.Drawing.Color.Transparent;
            this.lBaseService.Name = "lBaseService";
            // 
            // label3
            // 
            resources.ApplyResources(this.label3, "label3");
            this.label3.CausesValidation = false;
            this.label3.Name = "label3";
            // 
            // lOsManager
            // 
            resources.ApplyResources(this.lOsManager, "lOsManager");
            this.lOsManager.BackColor = System.Drawing.Color.Transparent;
            this.lOsManager.Name = "lOsManager";
            // 
            // lInitial
            // 
            resources.ApplyResources(this.lInitial, "lInitial");
            this.lInitial.BackColor = System.Drawing.Color.Transparent;
            this.lInitial.Name = "lInitial";
            // 
            // cacheLabel
            // 
            resources.ApplyResources(this.cacheLabel, "cacheLabel");
            this.cacheLabel.CausesValidation = false;
            this.cacheLabel.Name = "cacheLabel";
            // 
            // lCache
            // 
            resources.ApplyResources(this.lCache, "lCache");
            this.lCache.BackColor = System.Drawing.Color.Transparent;
            this.lCache.Name = "lCache";
            // 
            // cacheL2Label
            // 
            resources.ApplyResources(this.cacheL2Label, "cacheL2Label");
            this.cacheL2Label.CausesValidation = false;
            this.cacheL2Label.Name = "cacheL2Label";
            // 
            // lL2Cache
            // 
            resources.ApplyResources(this.lL2Cache, "lL2Cache");
            this.lL2Cache.BackColor = System.Drawing.Color.Transparent;
            this.lL2Cache.Name = "lL2Cache";
            // 
            // lMax
            // 
            resources.ApplyResources(this.lMax, "lMax");
            this.lMax.BackColor = System.Drawing.Color.Transparent;
            this.lMax.Name = "lMax";
            // 
            // label6
            // 
            resources.ApplyResources(this.label6, "label6");
            this.label6.CausesValidation = false;
            this.label6.Name = "label6";
            // 
            // lState
            // 
            resources.ApplyResources(this.lState, "lState");
            this.lState.BackColor = System.Drawing.Color.Transparent;
            this.lState.Name = "lState";
            // 
            // label10
            // 
            resources.ApplyResources(this.label10, "label10");
            this.label10.CausesValidation = false;
            this.label10.Name = "label10";
            // 
            // label7
            // 
            resources.ApplyResources(this.label7, "label7");
            this.label7.CausesValidation = false;
            this.label7.Name = "label7";
            // 
            // tabPage2
            // 
            this.tabPage2.Controls.Add(this.tableLayoutPanel2);
            resources.ApplyResources(this.tabPage2, "tabPage2");
            this.tabPage2.Name = "tabPage2";
            this.tabPage2.UseVisualStyleBackColor = true;
            // 
            // tableLayoutPanel2
            // 
            resources.ApplyResources(this.tableLayoutPanel2, "tableLayoutPanel2");
            this.tableLayoutPanel2.Controls.Add(this.inUseChart, 0, 1);
            this.tableLayoutPanel2.Controls.Add(this.assignedChart, 0, 0);
            this.tableLayoutPanel2.Name = "tableLayoutPanel2";
            // 
            // logViewer1
            // 
            resources.ApplyResources(this.logViewer1, "logViewer1");
            this.logViewer1.Name = "logViewer1";
            // 
            // inUseChart
            // 
            resources.ApplyResources(this.inUseChart, "inUseChart");
            this.inUseChart.Name = "inUseChart";
            // 
            // assignedChart
            // 
            resources.ApplyResources(this.assignedChart, "assignedChart");
            this.assignedChart.Name = "assignedChart";
            // 
            // DeployedServicePanel
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackColor = System.Drawing.SystemColors.Window;
            this.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.Controls.Add(this.tabControl1);
            this.Name = "DeployedServicePanel";
            this.VisibleChanged += new System.EventHandler(this.DeployedServicePanel_VisibleChanged);
            this.tabControl1.ResumeLayout(false);
            this.tabPage1.ResumeLayout(false);
            this.splitContainer1.Panel1.ResumeLayout(false);
            this.splitContainer1.Panel1.PerformLayout();
            this.splitContainer1.Panel2.ResumeLayout(false);
            this.splitContainer1.ResumeLayout(false);
            this.tableLayoutPanel1.ResumeLayout(false);
            this.tableLayoutPanel1.PerformLayout();
            this.tabPage2.ResumeLayout(false);
            this.tableLayoutPanel2.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.TabControl tabControl1;
        private System.Windows.Forms.TabPage tabPage1;
        private System.Windows.Forms.SplitContainer splitContainer1;
        private System.Windows.Forms.TabPage tabPage2;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel1;
        private System.Windows.Forms.Label groupLabel;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Label lName;
        private System.Windows.Forms.Label lComments;
        private System.Windows.Forms.Label lBaseService;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Label lOsManager;
        private System.Windows.Forms.Label lInitial;
        private System.Windows.Forms.Label cacheLabel;
        private System.Windows.Forms.Label lCache;
        private System.Windows.Forms.Label cacheL2Label;
        private System.Windows.Forms.Label lL2Cache;
        private System.Windows.Forms.Label lMax;
        private System.Windows.Forms.Label label6;
        private System.Windows.Forms.Label lState;
        private System.Windows.Forms.Label label10;
        private System.Windows.Forms.Label label7;
        private LogViewer logViewer1;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel2;
        private ChartPanel assignedChart;
        private ChartPanel inUseChart;

    }
}
