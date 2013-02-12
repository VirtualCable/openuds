using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Windows.Forms.DataVisualization.Charting;

namespace UdsAdmin.controls.panel
{
    public class ChartPanel : UserControl
    {
        private System.ComponentModel.IContainer components = null;
        System.Windows.Forms.DataVisualization.Charting.Chart chart;

        public ChartPanel()
        {
            InitializeComponent();
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        private void InitializeComponent()
        {
            this.components = new System.ComponentModel.Container();

            System.Windows.Forms.DataVisualization.Charting.ChartArea chartArea1 = new ChartArea();
            System.Windows.Forms.DataVisualization.Charting.Legend legend1 = new System.Windows.Forms.DataVisualization.Charting.Legend();

            chart = new System.Windows.Forms.DataVisualization.Charting.Chart();
            ((System.ComponentModel.ISupportInitialize)(this.chart)).BeginInit();
            SuspendLayout();
            chartArea1.Name = "ChartArea1";
            chart.ChartAreas.Add(chartArea1);

            legend1.Name = "Legend1";
            legend1.LegendStyle = LegendStyle.Column;
            legend1.Title = Strings.legend;
            chart.Legends.Add(legend1);

            chart.Dock = DockStyle.Fill;
            chart.Name = "Chart";
            chart.TabIndex = 0;
            chart.Text = "chart1";
            chart.Palette = ChartColorPalette.Pastel;

            Controls.Add(chart); 
            Load += new System.EventHandler(this.ChartPanel_Load);
            ((System.ComponentModel.ISupportInitialize)(chart)).EndInit();
            ResumeLayout(false);

            // For testing how chart looks like
            /*System.Windows.Forms.DataVisualization.Charting.Series series1 = new System.Windows.Forms.DataVisualization.Charting.Series();
            series1.ChartArea = "ChartArea1";
            series1.Legend = "Legend1";
            series1.XValueType = ChartValueType.DateTime;
            series1.YValueType = ChartValueType.Double;
            series1.Name = "Series1";
            series1.ChartType = SeriesChartType.SplineArea;

            DateTime a = DateTime.Now;
            a = a.AddDays(-360);


            for (int i = 0; i < 360; i++)
            {
                series1.Points.AddXY(a, 100+100*Math.Sin(i*Math.PI/180));
                a = a.AddDays(1);
            }


            this.chart.Series.Add(series1);

            chart.Invalidate();*/

        }

        private void ChartPanel_Load(object sender, EventArgs e)
        {
        }

        public void clearSeries()
        {
            chart.Series.Clear();
        }

        public void addSerie(xmlrpc.StatCounter counter)
        {
            SuspendLayout();
            string n = (1+chart.Series.Count).ToString();

            /*Legend legend = new Legend();
            legend.Name = "Legend" + n;
            legend.LegendStyle = LegendStyle.Column;
            legend.Title = counter.title;
            this.chart.Legends.Add(legend);*/

            Series serie = new Series();
            serie.ChartArea = "ChartArea1";
            serie.Legend = "Legend1";
            serie.XValueType = ChartValueType.DateTime;
            serie.YValueType = ChartValueType.Double;
            serie.Name = counter.title;
            
            serie.ChartType = SeriesChartType.SplineArea;

            foreach( xmlrpc.StatCounterData i in counter.data )
            {
                serie.Points.AddXY(i.stamp, i.value);
            }

            this.chart.Series.Add(serie);
            this.chart.Invalidate();
            ResumeLayout();
        }

    }
}
