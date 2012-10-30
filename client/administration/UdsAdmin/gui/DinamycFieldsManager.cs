//
// Copyright (c) 2012 Virtual Cable S.L.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without modification, 
// are permitted provided that the following conditions are met:
//
//    * Redistributions of source code must retain the above copyright notice, 
//      this list of conditions and the following disclaimer.
//    * Redistributions in binary form must reproduce the above copyright notice, 
//      this list of conditions and the following disclaimer in the documentation 
//      and/or other materials provided with the distribution.
//    * Neither the name of Virtual Cable S.L. nor the names of its contributors 
//      may be used to endorse or promote products derived from this software 
//      without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE 
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER 
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, 
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

// author: Adolfo Gómez, dkmaster at dkmon dot com

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Drawing;

namespace UdsAdmin.gui
{
    public class DinamycFieldsManager
    {
        const int DEF_FLD_HEIGHT = 24;
        const int DEF_FLD_WIDTH = 12;

        public class ValidationError : Exception
        {
            private string _msg;

            public ValidationError(string err) : base()
            {
                _msg = err;
            }

            public ValidationError(xmlrpc.GuiField fld) : base()
            {
                _msg = string.Format(Strings.fieldRequired, fld.gui.label);
            }

            public override string Message
            {
                get
                {
                    return _msg;
                }
            }

        }

        // I'll try to explain what i want to do with this struture here :-):
        // First, we need a translation table so we can easyly know how every single type behabiors.
        // This behabiors must include:
        //  - Generate the control itself, with default data if provided (Textbox, Combobox, ...)
        //  - Read data from controls (Text from textbox, selected item id from comboboc, selected itemS idS from listbox, ...)
        //  - Refill controls with data (used for callback invocation, on return it must refill som items)
        //  - Select values of controls, without refilling data (for "modify" operations, so we can recover the previous state)
        //  - Calculate the size of the control (so we can adjust the Panel acordly)
        // With all of this, we use the next items in every case:
        // - PutFields, First, it calculates the size of all cells, done via "sizeCalculator".
        //              Then, it creates the controls with the specified value/values (value for text controls, values for choices and multichoices)
        //              This is done via "ctrlGenerator" method
        //              When all controls r created, it starts, in order, to set values indicated, invoking callbacks if needed 
        //              (this way, if we need to recover the state of something, we can use same callbacks that we used at creation
        //               to allow modify). This is done via the "dataSelector".
        // - Callbacks, It uses the information provided on the callback to;
        //              * Invoke the remote procedure with indicated parameters (even hidden fields :-))
        //              * Receive data from callback and, using "dataWriter", refill the specified fields received on response.
        //                Choice and Multichoice uses the "values" field, and text ones uses the "value" field
        // - ReadFields. It simply reads the previously created controls, fills the pairs "name" "value" in case of single select value controls
        //               (text, choice) and the keys "name" "values" in case of multiselection controls (multichoice), returning this list.

        struct FldTypeData {
            public Func<xmlrpc.GuiField, Control, Control> ctrlGenerator;
            public Func<Control, xmlrpc.GuiField, bool, xmlrpc.GuiFieldValue> dataExtractor;
            public Action<Control, xmlrpc.GuiFieldValue> dataWriter;
            public Action<Control, xmlrpc.GuiFieldValue> dataSelector;
            public Func<xmlrpc.GuiField, Size> sizeCalculator;

            public FldTypeData(Func<xmlrpc.GuiField, Control, Control> generator,
                Func<Control, xmlrpc.GuiField, bool, xmlrpc.GuiFieldValue> dataExtractor,
                Action<Control, xmlrpc.GuiFieldValue> dataWriter,
                Action<Control, xmlrpc.GuiFieldValue> dataSelector,
                Func<xmlrpc.GuiField, Size> sizeCalculator, Size size)
            {
                this.ctrlGenerator = generator;
                this.dataExtractor = dataExtractor;
                this.dataWriter = dataWriter;
                this.dataSelector = dataSelector;
                this.sizeCalculator = sizeCalculator;
            }

            public FldTypeData(Func<xmlrpc.GuiField, Control, Control> generator,
                Func<Control, xmlrpc.GuiField, bool, xmlrpc.GuiFieldValue> dataExtractor,
                Action<Control, xmlrpc.GuiFieldValue> dataWriter,
                Action<Control, xmlrpc.GuiFieldValue> dataSelector,
                Func<xmlrpc.GuiField, Size> sizeCalculator)
            {
                this.ctrlGenerator = generator;
                this.dataExtractor = dataExtractor;
                this.dataWriter = dataWriter;
                this.dataSelector = dataSelector;
                this.sizeCalculator = sizeCalculator;
            }

            public FldTypeData(Func<xmlrpc.GuiField, Control, Control> generator,
                Func<Control, xmlrpc.GuiField, bool, xmlrpc.GuiFieldValue> dataExtractor,
                Action<Control, xmlrpc.GuiFieldValue> dataWriter,
                Action<Control, xmlrpc.GuiFieldValue> dataSelector)
            {
                this.ctrlGenerator = generator;
                this.dataExtractor = dataExtractor;
                this.dataWriter = dataWriter;
                this.dataSelector = dataSelector;
                this.sizeCalculator = DefaultSizeCalculator;
            }

            public Size size()
            {
                return new Size(DEF_FLD_WIDTH, DEF_FLD_HEIGHT);
            }

        };


       private static Dictionary<string, FldTypeData> ctrlTypeInfo =
            new Dictionary<string, FldTypeData>()
            {
                { xmlrpc.Constants.TEXT_TYPE, new FldTypeData(CreateTextBox, TextDataExtractor, TextDataWriter, TextSelector, TextSizeCalculator) },
                { xmlrpc.Constants.PASSWORD_TYPE, new FldTypeData(CreatePasswordBox, TextDataExtractor, TextDataWriter, TextSelector) },
                { xmlrpc.Constants.NUMERIC_TYPE, new FldTypeData(CreateNumericBox, NumericDataExtractor, NumericDataWriter, NumericSelector) },
                { xmlrpc.Constants.HIDDEN_TYPE, new FldTypeData(null, TextDataExtractor, TextDataWriter, TextSelector) },
                { xmlrpc.Constants.CHOICE_TYPE, new FldTypeData(CreateChoiceBox, ChoiceDataExtractor, ChoiceDataWriter, ChoiceSelector) },
                { xmlrpc.Constants.MULTI_CHOICE_TYPE, new FldTypeData(CreateMultiChoiceBox, MultiChoiceExtractor, MultichoiceDataWriter, MultiChoiceSelector, MultiChoiceSizeCalculator) },
                { xmlrpc.Constants.EDITABLE_LIST, new FldTypeData(CreateEditList, EditListExtractor, EditListDataWriter, EditListSelector, BtnSizeCalculator) },
                { xmlrpc.Constants.CHECKBOX_TYPE, new FldTypeData(CreateCheckBox, CheckBoxExtractor, CheckBoxDataWriter, CheckBoxSelector, CheckBoxSizeCalculator) },
            };

        // Put fields on the specified tablelayoutpanel so they can be edited
        public static Size PutFields(TableLayoutPanel panel, xmlrpc.GuiField[] fields, xmlrpc.GuiFieldValue[] values)
        {
            // Controls generator
            // Size getters

            // We count the fields, except for hiddend fields, so we know the number of rows
            int numRows = fields.Count(fld => (fld.gui.type != xmlrpc.Constants.HIDDEN_TYPE));
            panel.SuspendLayout();
            panel.Controls.Clear();
            panel.RowCount = numRows;
            panel.ColumnCount = 2;

            panel.AutoSize = true;

            // Sort the array by fielrd order
            Array.Sort(fields, delegate( xmlrpc.GuiField f1, xmlrpc.GuiField f2 ) {
                return f1.gui.order.CompareTo(f2.gui.order);
            });

            List<xmlrpc.GuiFieldValue> ordererValues = new List<xmlrpc.GuiFieldValue>();
            Dictionary<string, xmlrpc.GuiFieldValue> dict = new Dictionary<string, xmlrpc.GuiFieldValue>();

            if (values != null)
                foreach (xmlrpc.GuiFieldValue v in values)
                    dict.Add(v.name, v);

            int row = 0;
            foreach (xmlrpc.GuiField fld in fields)
            {
                if (fld.gui.type != xmlrpc.Constants.HIDDEN_TYPE) // Hiden fields are textbox that don't appears and don't add rows..
                {
                    ToolTip tt = new ToolTip();
                    // Creates the label
                    Label label = new Label();
                    label.AutoSize = true;
                    label.Margin = new Padding(3, 6, 3, 6);
                    label.Text = fld.gui.label;
                    label.TextAlign = ContentAlignment.MiddleLeft;
                    tt.SetToolTip(label, fld.gui.tooltip);
                    panel.Controls.Add(label, 0, row);
                    //panel.SetCellPosition(label, new TableLayoutPanelCellPosition(0, row));
                    Control ctrl = ctrlTypeInfo[fld.gui.type].ctrlGenerator(fld, panel);
                    ctrl.Dock = DockStyle.Fill;
                    if (dict.ContainsKey(fld.name))
                    {
                        // We have it in order
                        ordererValues.Add(dict[fld.name]);
                    }
                    if (fld.gui.rdonly == true && values != null)
                    {
                        label.Enabled = false;
                        ctrl.Enabled = false;
                    }
                    panel.Controls.Add(ctrl, 1, row);
                    // panel.SetCellPosition(ctrl, new TableLayoutPanelCellPosition(1, row));
                    row++;
                }
                else
                {
                    TextBox hidden = new TextBox();
                    if (fld.value != "")
                        hidden.Text = fld.value;
                    else
                        hidden.Text = fld.gui.defvalue;
                    hidden.Name = fld.name; hidden.Tag = fld; hidden.Visible = false;
                    panel.Controls.Add(hidden, 0, 0);
                }
            }

            // Set panel column and rows styles
            TableLayoutColumnStyleCollection styles = panel.ColumnStyles;

            foreach (ColumnStyle style in styles)
            {
                style.SizeType = SizeType.AutoSize;
            }

            TableLayoutRowStyleCollection stylesR = panel.RowStyles;
            foreach (RowStyle style in stylesR)
            {
                style.SizeType = SizeType.AutoSize;
            }

            panel.ResumeLayout();

            // Now stores the values of fields if needed (we do it now cause we need all controls to be created BEFORE this 
            // because the events of change fields will be launched
            // Generate a dict with the desired values
            foreach (xmlrpc.GuiFieldValue v in ordererValues)
            {
                Control[] ctrl = panel.Controls.Find(v.name, true);
                if (ctrl.Length > 0)
                {
                    xmlrpc.GuiField field = (xmlrpc.GuiField)ctrl[0].Tag;
                    ctrlTypeInfo[field.gui.type].dataSelector(ctrl[0], v);
                }
            }


            return panel.PreferredSize;
        }


        public static xmlrpc.GuiFieldValue[] ReadFields(TableLayoutPanel panel, xmlrpc.GuiField[] flds)
        {

            Dictionary<string, Control> ctrlsDict = new Dictionary<string,Control>();
            foreach (Control ctrl in panel.Controls)
            {
                if (ctrl.Name == "")  // Skip labels...
                    continue;
                ctrlsDict.Add(ctrl.Name, ctrl);
            }
            // Extract data from controls and put it on
            xmlrpc.GuiFieldValue[] res = new xmlrpc.GuiFieldValue[flds.Count()];
            int cnt = 0;
            foreach (xmlrpc.GuiField fld in flds)
            {
                res[cnt++] = ctrlTypeInfo[fld.gui.type].dataExtractor(ctrlsDict[fld.name], fld, true);
            }
            return res;
        }


        // Controls creator helpers
        private static Control CreateTextBox(xmlrpc.GuiField fld, Control container)
        {
            TextBox text = new TextBox();
            text.Name = fld.name;
            text.Tag = fld;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            text.Width = sz.Width;
            text.Height = sz.Height;
            text.MaxLength = fld.gui.length;
            string value = fld.value;
            if (value == "")
                value = fld.gui.defvalue;

            if (fld.gui.multiline > 1)
            {
                text.Multiline = true;
                text.ScrollBars = ScrollBars.Both;
                text.AcceptsReturn = true;
                text.WordWrap = false;
                StringBuilder bldr = new StringBuilder();
                foreach (string v in value.Split('\n'))
                    bldr.AppendLine(v);
                value = bldr.ToString();
            }
            text.Text = value;
            return text;
        }

        private static Control CreatePasswordBox(xmlrpc.GuiField fld, Control container)
        {
            TextBox text = new TextBox();
            text.Name = fld.name;
            text.Tag = fld;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            text.Width = sz.Width;
            text.Height = sz.Height;
            text.MaxLength = fld.gui.length;
            if (fld.value != "")
                text.Text = fld.value;
            else
                text.Text = fld.gui.defvalue;
            text.UseSystemPasswordChar = true;
            return text;
        }

        private static decimal ToDecimal(string value)
        {
            try
            {
                return Convert.ToDecimal(value);
            }
            catch (Exception)
            {
                return 0;
            }
        }

        private static Control CreateNumericBox(xmlrpc.GuiField fld, Control container)
        {
            NumericUpDown num = new NumericUpDown();
            num.Name = fld.name;
            num.Tag = fld;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            num.Width = sz.Width + 20;
            num.Height = sz.Height;
            num.Minimum = 0;
            double length = fld.gui.length < 8 ? fld.gui.length : 8;
            num.Maximum = (decimal)Math.Pow(10, length)-1;
            if (fld.value != "")
                num.Value = ToDecimal(fld.value);
            else
            {
                num.Value = ToDecimal(fld.gui.defvalue);
            }
            return num;
        }

        private static Control CreateChoiceBox(xmlrpc.GuiField fld, Control container)
        {
            ComboBox box = new ComboBox();
            box.Name = fld.name;
            box.Tag = fld;
            box.DropDownStyle = ComboBoxStyle.DropDownList;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            box.Width = sz.Width;
            box.Height = sz.Height;
            foreach (xmlrpc.Choice ch in fld.gui.values)
            {
                box.Items.Add(ch);
                if (ch.id == fld.gui.defvalue)
                    box.SelectedItem = ch;
            }

            if (fld.gui.fills.callbackName != null)
            {
                // We create a delegate to support the callback for this combo box
                box.SelectedIndexChanged += delegate(object sender, EventArgs args)
                {
                    xmlrpc.GuiFieldValue[] data = new xmlrpc.GuiFieldValue[fld.gui.fills.parameters.Length];
                    int pos = 0;
                    foreach (string parameter in fld.gui.fills.parameters)
                    {
                        Control[] ctrlParameter = container.Controls.Find(parameter, true);
                        if (ctrlParameter.Length > 0)
                        {
                            xmlrpc.GuiField field = (xmlrpc.GuiField)ctrlParameter[0].Tag;
                            data[pos++] = ctrlTypeInfo[field.gui.type].dataExtractor(ctrlParameter[0], field, false);
                        }
                    }
                    xmlrpc.GuiFieldValue[] newData = xmlrpc.UdsAdminService.InvokeChooseCallback(fld.gui.fills.callbackName, data);
                    foreach (xmlrpc.GuiFieldValue val in newData)
                    {
                        Control[] ctrlResult = container.Controls.Find(val.name, true);
                        if (ctrlResult.Length > 0)
                        {
                            xmlrpc.GuiField field = (xmlrpc.GuiField)ctrlResult[0].Tag;
                            ctrlTypeInfo[field.gui.type].dataWriter(ctrlResult[0], val);
                        }
                    }
                };
            }
            // With the event active, we change the selected item (if there is a callback, it should launc now)
            return box;
        }

        // Multichoice creator
        private static Control CreateMultiChoiceBox(xmlrpc.GuiField fld, Control container)
        {
            ListBox box = new ListBox();
            box.Name = fld.name;
            box.Tag = fld;
            box.SelectionMode = SelectionMode.MultiExtended;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            box.Width = sz.Width;
            box.Height = sz.Height;
            foreach (xmlrpc.Choice ch in fld.gui.values)
            {
                box.Items.Add(ch);
                if (fld.gui.defvalue == ch.id)
                    box.SelectedItem = ch;
            }

            return box;
        }

        private static Control CreateEditList(xmlrpc.GuiField fld, Control container)
        {
            controls.ListEditor lst = new controls.ListEditor();
            lst.Name = fld.name;
            lst.Tag = fld;
            lst.Text = fld.gui.label;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            lst.Width = sz.Width;
            List<string> vals = new List<string>();
            foreach (xmlrpc.Choice ch in fld.gui.values)
                vals.Add(ch.id);
            lst.Items = vals;

            return lst;
        }

        private static Control CreateCheckBox(xmlrpc.GuiField fld, Control container)
        {
            CheckBox check = new CheckBox();
            check.Name = fld.name;
            check.Tag = fld;
            Size sz = ctrlTypeInfo[fld.gui.type].sizeCalculator(fld);
            check.Width = sz.Width;
            check.Height = sz.Height;
            string value = (fld.value != "") ? fld.value : fld.gui.defvalue;

            if (value != xmlrpc.Constants.TRUE)
                check.Checked = false;
            else
                check.Checked = true;
            return check;
        }

        // Controls size calculators
        private static Size DefaultSizeCalculator(xmlrpc.GuiField fld)
        {
            Size sz = ctrlTypeInfo[fld.gui.type].size();
            sz.Width *= fld.gui.length;
            if (sz.Width > UdsAdmin.Properties.Settings.Default.MaxControlWidth)
                sz.Width = UdsAdmin.Properties.Settings.Default.MaxControlWidth;

            return sz;
        }

        // Text box size calculator
        private static Size TextSizeCalculator(xmlrpc.GuiField fld)
        {
            if (fld.gui.multiline < 2)
                return DefaultSizeCalculator(fld);

            Size sz = ctrlTypeInfo[fld.gui.type].size();
            sz.Width *= fld.gui.length;
            if (sz.Width > UdsAdmin.Properties.Settings.Default.MaxControlWidth)
                sz.Width = UdsAdmin.Properties.Settings.Default.MaxControlWidth;
            sz.Height *= fld.gui.multiline;
            return sz;
        }



        // Button size calculators
        private static Size BtnSizeCalculator(xmlrpc.GuiField fld)
        {
            Size sz = ctrlTypeInfo[fld.gui.type].size();
            sz.Height += 8;
            sz.Width *= fld.gui.length;
            if (sz.Width > UdsAdmin.Properties.Settings.Default.MaxControlWidth)
                sz.Width = UdsAdmin.Properties.Settings.Default.MaxControlWidth;

            return sz;
        }

        // Listbox size calculator
        private static Size MultiChoiceSizeCalculator(xmlrpc.GuiField fld)
        {
            Size sz = ctrlTypeInfo[fld.gui.type].size();
            sz.Width *= fld.gui.length;
            if (sz.Width > UdsAdmin.Properties.Settings.Default.MaxControlWidth)
                sz.Width = UdsAdmin.Properties.Settings.Default.MaxControlWidth;
            int rows = 2;
            if (fld.gui.rows != -1)
                rows = fld.gui.rows;
            sz.Height *= rows;
            return sz;
        }

        private static Size CheckBoxSizeCalculator(xmlrpc.GuiField fld)
        {
            Size sz = ctrlTypeInfo[fld.gui.type].size() + new Size(4, 4);
            if (sz.Width > UdsAdmin.Properties.Settings.Default.MaxControlWidth)
                sz.Width = UdsAdmin.Properties.Settings.Default.MaxControlWidth;

            return sz;
        }

        // Control extractors helpers
        private static xmlrpc.GuiFieldValue TextDataExtractor(Control ctrl, xmlrpc.GuiField fld, bool validate)
        {
            TextBox txt = (TextBox)ctrl;
            string val = txt.Text.Trim();
            if (validate && fld.gui.required && val.Length == 0)
                throw new ValidationError(fld);
            return new xmlrpc.GuiFieldValue(fld.name, val);
        }

        private static xmlrpc.GuiFieldValue NumericDataExtractor(Control ctrl, xmlrpc.GuiField fld, bool validate)
        {
            NumericUpDown num = (NumericUpDown)ctrl;
            string val = ((int)(num.Value)).ToString();
            if( validate && fld.gui.required && val == "0" )
                throw new ValidationError(fld);
            return new xmlrpc.GuiFieldValue(fld.name, val);
        }

        private static xmlrpc.GuiFieldValue ChoiceDataExtractor(Control ctrl, xmlrpc.GuiField fld, bool validate)
        {
            ComboBox box = (ComboBox)ctrl;
            string val = "";
            if( box.SelectedItem != null )
                val = ((xmlrpc.Choice)box.SelectedItem).id;
            if( validate && fld.gui.required && val.Length == 0 )
                    throw new ValidationError(fld);
            return new xmlrpc.GuiFieldValue(fld.name, val);
        }

        private static xmlrpc.GuiFieldValue MultiChoiceExtractor(Control ctrl, xmlrpc.GuiField fld, bool validate)
        {
            ListBox box = (ListBox)ctrl;
            xmlrpc.Choice[] selected = new xmlrpc.Choice[box.SelectedItems.Count];
            for (int i = 0; i < box.SelectedItems.Count; i++)
                selected[i] = (xmlrpc.Choice)box.SelectedItems[i];
            if (validate && fld.gui.required && selected.Length == 0)
                throw new ValidationError(fld);
            return new xmlrpc.GuiFieldValue(fld.name, selected);
        }

        private static xmlrpc.GuiFieldValue EditListExtractor(Control ctrl, xmlrpc.GuiField fld, bool validate)
        {
            controls.ListEditor lst = (controls.ListEditor)ctrl;
            List<string> vals = lst.Items;
            xmlrpc.Choice[] selected = new xmlrpc.Choice[vals.Count];
            for (int i = 0; i < vals.Count; i++)
                selected[i] = new xmlrpc.Choice(vals[i], ""); // Returned values goes inside ids (the significant part of choices, text are used to display data to user)
            if ( validate && fld.gui.required && selected.Length == 0)
                throw new ValidationError(fld);
            return new xmlrpc.GuiFieldValue(fld.name, selected);
        }

        private static xmlrpc.GuiFieldValue CheckBoxExtractor(Control ctrl, xmlrpc.GuiField fld, bool validate)
        {
            CheckBox chk = (CheckBox)ctrl;
            return new xmlrpc.GuiFieldValue(fld.name, chk.Checked ? xmlrpc.Constants.TRUE : xmlrpc.Constants.FALSE);
        }

        // Control writers helpers
        private static void TextDataWriter(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            TextBox tc = (TextBox)ctrl;
            string val = value.value;
            if (tc.Multiline)
            {
                StringBuilder bldr = new StringBuilder();
                foreach (string v in val.Split('\n'))
                    bldr.AppendLine(v);
                val = bldr.ToString();
            }

            ctrl.Text = val;
        }

        // Control writers helpers
        private static void NumericDataWriter(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            NumericUpDown num = (NumericUpDown)ctrl;
            num.Value = ToDecimal(value.value);
        }

        private static void ChoiceDataWriter(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            ComboBox box = (ComboBox)ctrl;
            box.Items.Clear();
            foreach (xmlrpc.Choice ch in value.values)
            {
                box.Items.Add(ch);
            }
            if (box.Items.Count > 0)
                box.SelectedIndex = 0;
            else
                box.SelectedIndex = -1;
        }

        private static void MultichoiceDataWriter(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            ListBox box = (ListBox)ctrl;
            box.Items.Clear();
            foreach (xmlrpc.Choice ch in value.values)
            {
                box.Items.Add(ch);
            }
        }

        private static void EditListDataWriter(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            controls.ListEditor lst = (controls.ListEditor)ctrl;
            List<string> vals = new List<string>();
            foreach (xmlrpc.Choice ch in value.values)
                vals.Add(ch.text);
            lst.Items = vals;
        }

        private static void CheckBoxDataWriter(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            CheckBox chk = (CheckBox)ctrl;
            if (value.value != xmlrpc.Constants.TRUE)
                chk.Checked = false;
            else
                chk.Checked = true;
        }

        // Controls "Selectors" (that is, select the items without overwriting it
        private static void TextSelector(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            TextDataWriter(ctrl, value);
        }

        private static void NumericSelector(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            NumericUpDown num = (NumericUpDown)ctrl;
            num.Value = ToDecimal(value.value);
        }

        private static void ChoiceSelector(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            ComboBox box = (ComboBox)ctrl;
            foreach( xmlrpc.Choice ch in box.Items )
            {
                if (ch.id == value.value)
                    box.SelectedItem = ch;
            }
        }

        private static void MultiChoiceSelector(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            ListBox box = (ListBox)ctrl;
            box.BeginUpdate();
            box.ClearSelected();
            foreach (xmlrpc.Choice val in value.values)
                box.SelectedItems.Add(val);
            box.EndUpdate();
        }

        private static void EditListSelector(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            // All items are "Selected" in editlist, i mean, we fill the list with this items
            controls.ListEditor lst = (controls.ListEditor)ctrl;
            List<string> vals = new List<string>();
            foreach (xmlrpc.Choice ch in value.values)
                vals.Add(ch.id);
            lst.Items = vals;

        }

        private static void CheckBoxSelector(Control ctrl, xmlrpc.GuiFieldValue value)
        {
            CheckBox chk = (CheckBox)ctrl;
            if (value.value != xmlrpc.Constants.TRUE)
                chk.Checked = false;
            else
                chk.Checked = true;
        }

    }
}
