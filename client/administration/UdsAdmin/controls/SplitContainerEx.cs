using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Drawing;

namespace UdsAdmin.controls
{
    public class SplitContainerEx :  SplitContainer
    {
        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);

            HandlePaint(e);
        }

        private void HandlePaint(PaintEventArgs e)
        {
            //paint the three dots'
            Point[] points = new Point[3];
            var w = Width;
            var h = Height;
            var d = SplitterDistance;
            var sW = SplitterWidth;

            //calculate the position of the points'
            if (Orientation == Orientation.Horizontal)
            {
                points[0] = new Point((w / 2), d + (sW / 2));
                points[1] = new Point(points[0].X - 10, points[0].Y);
                points[2] = new Point(points[0].X + 10, points[0].Y);
            }
            else
            {
                points[0] = new Point(d + (sW / 2), (h / 2));
                points[1] = new Point(points[0].X, points[0].Y - 10);
                points[2] = new Point(points[0].X, points[0].Y + 10);
            }

            foreach (Point p in points)
            {
                p.Offset(-2, -2);
                e.Graphics.FillEllipse(SystemBrushes.ControlDark,
                    new Rectangle(p, new Size(3, 3)));

                p.Offset(1, 1);
                e.Graphics.FillEllipse(SystemBrushes.ControlLight,
                    new Rectangle(p, new Size(3, 3)));
            }
        }

    }
}
