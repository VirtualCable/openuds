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

namespace UdsAdmin.xmlrpc
{
    public class ExceptionExplainer
    {
        public const int AUTH_CLASS = 0x1000;
        public const int DATA_CLASS = 0x2000;
        public const int ACTION_CLASS = 0x3000;

        public const int FAIL = 0x0100;

        public const int AUTH_FAILED = AUTH_CLASS | FAIL | 0x0001;
        public const int DUPLICATE_FAIL = DATA_CLASS | FAIL | 0x0001;
        public const int INSERT_FAIL = DATA_CLASS | FAIL | 0x0002;
        public const int DELETE_FAIL = DATA_CLASS | FAIL | 0x0003;
        public const int FIND_FAIL = DATA_CLASS | FAIL | 0x0004;
        public const int VALIDATION_FAIL = DATA_CLASS | FAIL | 0x0005;
        public const int PARAMETERS_FAIL = DATA_CLASS | FAIL | 0x0006;
        public const int MODIFY_FAIL = DATA_CLASS | FAIL | 0x0007;
        
        public const int PUBLISH_FAIL = ACTION_CLASS | FAIL | 0x0001;
        public const int CANCEL_FAIL = ACTION_CLASS | FAIL | 0x0001;


        private int _code;
        private string _text;
        private bool _fatal;

        public ExceptionExplainer(CookComputing.XmlRpc.XmlRpcFaultException e)
        {
            _code = e.FaultCode; _text = e.FaultString;
            _fatal = false;
        }

        public string explain()
        {
            string res = "";
            switch (_code)
            {
                case DUPLICATE_FAIL:
                    res = Strings.duplicatedItem + ": " + _text;
                    break;
                case DELETE_FAIL:
                    res = Strings.deletionFailed + ": " + _text;
                    break;
                case MODIFY_FAIL:
                    res = Strings.modificationFailed + ": " + _text;
                    break;
                case INSERT_FAIL:
                    res = _text;
                    break;
                case FIND_FAIL:
                    res = Strings.findFailed + ":" + _text;
                    break;
                case VALIDATION_FAIL:
                    res = Strings.validationFailed + ":" + _text;
                    break;
                case AUTH_FAILED:
                    _fatal = true;
                    res = Strings.authFailed + ":" + _text;
                    break;
                case PUBLISH_FAIL:
                    res = Strings.publicationFailed + ": " + _text;
                    break;
                case PARAMETERS_FAIL:
                default:
                    res = _text;
                    break;
            }
            if (_fatal)
                res += "\n" + Strings.appWillTerminate;
            return res;
        }

        public void showError()
        {
            System.Windows.Forms.MessageBox.Show(explain(), Strings.error, System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            if (_fatal)
                System.Windows.Forms.Application.Exit();
        }
    }
}
