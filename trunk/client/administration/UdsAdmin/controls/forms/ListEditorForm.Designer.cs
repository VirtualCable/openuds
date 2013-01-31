namespace UdsAdmin.controls.forms
{
    partial class ListEditorForm
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(ListEditorForm));
            this.lstItems = new System.Windows.Forms.ListBox();
            this.textItem = new System.Windows.Forms.TextBox();
            this.btnImport = new System.Windows.Forms.Button();
            this.layout = new System.Windows.Forms.TableLayoutPanel();
            this.btnRemove = new System.Windows.Forms.Button();
            this.btnAdd = new System.Windows.Forms.Button();
            this.btnClose = new System.Windows.Forms.Button();
            this.layout.SuspendLayout();
            this.SuspendLayout();
            // 
            // lstItems
            // 
            this.layout.SetColumnSpan(this.lstItems, 2);
            resources.ApplyResources(this.lstItems, "lstItems");
            this.lstItems.FormattingEnabled = true;
            this.lstItems.Name = "lstItems";
            // 
            // textItem
            // 
            resources.ApplyResources(this.textItem, "textItem");
            this.textItem.Name = "textItem";
            this.textItem.KeyPress += new System.Windows.Forms.KeyPressEventHandler(this.textItem_KeyPress);
            // 
            // btnImport
            // 
            resources.ApplyResources(this.btnImport, "btnImport");
            this.btnImport.Name = "btnImport";
            this.btnImport.UseVisualStyleBackColor = true;
            this.btnImport.Click += new System.EventHandler(this.btnImport_Click);
            // 
            // layout
            // 
            resources.ApplyResources(this.layout, "layout");
            this.layout.Controls.Add(this.lstItems, 0, 0);
            this.layout.Controls.Add(this.textItem, 0, 1);
            this.layout.Controls.Add(this.btnImport, 0, 2);
            this.layout.Controls.Add(this.btnRemove, 1, 2);
            this.layout.Controls.Add(this.btnAdd, 1, 1);
            this.layout.Controls.Add(this.btnClose, 0, 3);
            this.layout.Name = "layout";
            // 
            // btnRemove
            // 
            resources.ApplyResources(this.btnRemove, "btnRemove");
            this.btnRemove.Name = "btnRemove";
            this.btnRemove.UseVisualStyleBackColor = true;
            this.btnRemove.Click += new System.EventHandler(this.btnRemove_Click);
            // 
            // btnAdd
            // 
            resources.ApplyResources(this.btnAdd, "btnAdd");
            this.btnAdd.Name = "btnAdd";
            this.btnAdd.UseVisualStyleBackColor = true;
            this.btnAdd.Click += new System.EventHandler(this.btnAdd_Click);
            // 
            // btnClose
            // 
            this.layout.SetColumnSpan(this.btnClose, 2);
            resources.ApplyResources(this.btnClose, "btnClose");
            this.btnClose.Name = "btnClose";
            this.btnClose.UseVisualStyleBackColor = true;
            this.btnClose.Click += new System.EventHandler(this.btnClose_Click);
            // 
            // ListEditorForm
            // 
            resources.ApplyResources(this, "$this");
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Controls.Add(this.layout);
            this.Name = "ListEditorForm";
            this.Load += new System.EventHandler(this.ListEditorForm_Load);
            this.layout.ResumeLayout(false);
            this.layout.PerformLayout();
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.ListBox lstItems;
        private System.Windows.Forms.TableLayoutPanel layout;
        private System.Windows.Forms.TextBox textItem;
        private System.Windows.Forms.Button btnImport;
        private System.Windows.Forms.Button btnRemove;
        private System.Windows.Forms.Button btnAdd;
        private System.Windows.Forms.Button btnClose;
    }
}