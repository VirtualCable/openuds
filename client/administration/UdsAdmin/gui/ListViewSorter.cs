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
using System.Collections;

namespace UdsAdmin.gui
{
    class ListViewSorter : IComparer
    {
        private const string ASC = " (asc)";
        private const string DES = " (des)";
        private int _colToSort;
        private ImageList sortOrderImages;
        SortOrder _order;
        IComparer _strComparer;
        ListView _list;
        ICollection<int> _dateColumns;

        public ListViewSorter(ListView lst, ICollection<int> dateColumns = null )
        {
            _colToSort = 0;
            _order = SortOrder.None;
            _strComparer = new CaseInsensitiveComparer();
            _list = lst;

            _dateColumns = dateColumns;


            sortOrderImages = new ImageList();
            
            if( lst.SmallImageList != null )
            {
                foreach(string k in lst.SmallImageList.Images.Keys )
                {
                    sortOrderImages.Images.Add(k, lst.SmallImageList.Images[k]);
                }
            }

            sortOrderImages.ColorDepth = ColorDepth.Depth24Bit;
            sortOrderImages.Images.Add("up", Images.uparrow16);
            sortOrderImages.Images.Add("down", Images.downarrow16);
            sortOrderImages.Images.Add("empty", Images.empty16);

            lst.SmallImageList = sortOrderImages;
            foreach (ColumnHeader h in lst.Columns)
            {
                h.TextAlign = HorizontalAlignment.Left;
                h.ImageKey = "empty";
                int width = TextRenderer.MeasureText(h.Text, lst.Parent.Font).Width + 40;
                if (width > h.Width)
                    h.Width = width;
            }
        }


        public int Compare(object x, object y)
        {
            int compareResult;
            string listviewX, listviewY;

            // Cast the objects to be compared to ListViewItem objects  
            listviewX = ((ListViewItem)x).SubItems[_colToSort].Text;
            listviewY = ((ListViewItem)y).SubItems[_colToSort].Text;

            // Compare the two items  
            if( _dateColumns != null && _dateColumns.Contains(_colToSort ) )
                compareResult = DateTime.Compare(DateTime.Parse(listviewX), DateTime.Parse(listviewY));
            else
                compareResult = _strComparer.Compare(listviewX, listviewY);

            // Calculate correct return value based on object comparison  
            if (_order == SortOrder.Ascending)
            {
                // Ascending sort is selected, return normal result of compare operation  
                return compareResult;
            }
            else if (_order == SortOrder.Descending)
            {
                // Descending sort is selected, return negative result of compare operation  
                return (-compareResult);
            }
            else
            {
                // Return '0' to indicate they are equal  
                return 0;
            }
        }

        private void updateColumnHeaderText(int column, string order)
        {
            ColumnHeader h = _list.Columns[column];
            string txt = h.Text;
            // Try to remove " (asc)" or " (des)"
            /*if (txt.Contains(ASC))
                txt = txt.Substring(0, txt.Length - ASC.Length);
            else if (txt.Contains(DES))
                txt = txt.Substring(0, txt.Length - DES.Length);
            txt += order;
            h.Text = txt;*/
            if (order == ASC)
                h.ImageKey = "down";
            else if (order == DES)
                h.ImageKey = "up";
            else
                h.ImageKey = "empty";
        }

        private void updateColumHeaders()
        {
            for (int i = 0; i < _list.Columns.Count; i++)
                if (i == _colToSort)
                    updateColumnHeaderText(i, _order == SortOrder.Ascending ? ASC : DES);
                else
                    updateColumnHeaderText(i, "");
        }

        public void ColumnClick(object sender, ColumnClickEventArgs e)
        {
            // Determine if clicked column is already the column that is being sorted.  
            if (e.Column == _colToSort)
            {
                // Reverse the current sort direction for this column.  
                if (_order == SortOrder.Ascending)
                {
                    _order = SortOrder.Descending;
                }
                else
                {
                    _order = SortOrder.Ascending;
                }
            }
            else
            {
                // Set the column number that is to be sorted; default to ascending.  
                _colToSort = e.Column;
                _order = SortOrder.Ascending;
            }
            updateColumHeaders();
            _list.Sort();
        }
    }
}
