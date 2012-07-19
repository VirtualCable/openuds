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
using System.Drawing;

namespace UdsAdmin.gui
{
    public class Colors
    {
        public static Color BlackColor = Color.Black;
        public static Color ActiveColor = Color.Black;
        public static Color InactiveColor = Color.Orange;
        public static Color RemovingColor = Color.DarkGray;
        public static Color RemovedColor = Color.Gray;
        public static Color BlockedColor = Color.Red;
        public static Color RunningColor = Color.Green;
        public static Color ErrorColor = Color.Red;
        public static Color InactiveBackColor = Color.Red;
        public static Color InactiveForeColor = Color.Yellow;
        public static Color ActiveBackColor = Color.Green;
        public static Color ActiveForeColor = Color.White;

        public static Color getColorForState(string state)
        {
            switch (state)
            {
                case xmlrpc.Constants.STATE_USABLE:
                case xmlrpc.Constants.STATE_ACTIVE:
                    return ActiveColor;
                case xmlrpc.Constants.STATE_ERROR:
                    return ErrorColor;
                case xmlrpc.Constants.STATE_PREPARING:
                    return RunningColor;
                case xmlrpc.Constants.STATE_INACTIVE:
                    return InactiveColor;
                case xmlrpc.Constants.STATE_REMOVABLE:
                case xmlrpc.Constants.STATE_REMOVING:
                case xmlrpc.Constants.STATE_CANCELING:
                    return RemovingColor;
                case xmlrpc.Constants.STATE_REMOVED:
                case xmlrpc.Constants.STATE_CANCELED:
                    return RemovedColor;
                default:
                    return BlackColor;
            }
        }
    }
}
