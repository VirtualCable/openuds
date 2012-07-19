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
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Net;
using System.Diagnostics;

namespace UdsAdmin.forms
{
    public partial class FileDownloader : Form
    {
        private string _url;
        private string _outFile;
        private const int BUFFER_SIZE = 8192;
        delegate void UpdateDialogCallback(int readed, int length, double speed);

        public FileDownloader(string url)
        {
            _url = url;
            _outFile = System.IO.Path.GetTempPath() + "UDSAdminSetup.exe";
            InitializeComponent();
            Text = Strings.titleDownloader;
        }

        private void FileDownloader_Load(object sender, EventArgs e)
        {
            install.Enabled = false;
            bgTask.RunWorkerAsync();
        }

        private void UpdateProgress(int readed, int length, double speed)
        {
            progress.Maximum = length;
            progress.Value = readed;
            info.Text = String.Format(Strings.downloadInfo, readed / 1024, length / 1024, speed / 1024);
            if (readed == length)
            {
                install.Enabled = true;
                cancel.Text = Strings.exit;
            }
        }

        private void bgTask_DoWork(object sender, DoWorkEventArgs e)
        {
            HttpWebRequest req;
            HttpWebResponse res;
            try
            {
                req = (HttpWebRequest)WebRequest.Create(_url);
                res = (HttpWebResponse)req.GetResponse();

                int length = (int)res.ContentLength;

                System.IO.FileStream of = new System.IO.FileStream(_outFile, System.IO.FileMode.Create);
                int nRead = 0;

                Stopwatch timer = new Stopwatch();

                byte[] buffer = new byte[BUFFER_SIZE];
                UpdateDialogCallback d = new UpdateDialogCallback(UpdateProgress);

                timer.Start();
                while (true)
                {
                    if (bgTask.CancellationPending)
                        break;

                    int bytesReaded = res.GetResponseStream().Read(buffer, 0, BUFFER_SIZE);

                    nRead += bytesReaded;

                    double speed = 1000.0 * ((double)nRead) / timer.ElapsedMilliseconds;

                    this.Invoke(d, new object[] { nRead, length, speed });

                    if (bytesReaded == 0)
                        break;

                    of.Write(buffer, 0, bytesReaded);

                }
                timer.Stop();

                res.GetResponseStream().Close();
                of.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message, Strings.error, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
        }

        private void install_Click(object sender, EventArgs e)
        {
            Process install = new Process();
            install.StartInfo.FileName = _outFile;
            install.Start();
            DialogResult = System.Windows.Forms.DialogResult.OK;
        }

        private void cancel_Click(object sender, EventArgs e)
        {
            bgTask.CancelAsync();
            DialogResult = System.Windows.Forms.DialogResult.Cancel;
        }

    }
}
