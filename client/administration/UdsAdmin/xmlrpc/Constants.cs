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
    public class Constants
    {
        public const string TEXT_TYPE = "text";
        public const string NUMERIC_TYPE = "numeric";
        public const string PASSWORD_TYPE = "password";
        public const string HIDDEN_TYPE = "hidden";
        public const string CHOICE_TYPE = "choice";
        public const string MULTI_CHOICE_TYPE = "multichoice";
        public const string EDITABLE_LIST = "editlist";
        public const string CHECKBOX_TYPE = "checkbox";

        public const string TRUE = "true";
        public const string FALSE = "false";

        public const string STATE_ACTIVE = "A";
        public const string STATE_INACTIVE = "I";
        public const string STATE_BLOCKED = "B";
        public const string STATE_LAUNCHING = "L";
        public const string STATE_PREPARING = "P"; 
        public const string STATE_USABLE = "U"; 
        public const string STATE_REMOVABLE = "R"; 
        public const string STATE_REMOVING = "M";
        public const string STATE_REMOVED = "S";
        public const string STATE_ERROR = "E"; 
        public const string STATE_CANCELED = "C";
        public const string STATE_CANCELING = "K";

        public const int COUNTER_LOAD_TYPE = 0;
        public const int COUNTER_STORAGE = 1;
        public const int COUNTER_ASSIGNED = 2;
        public const int COUNTER_INUSE = 3;

        public const string LEVEL_OTHER = "OTHER";
        public const int LEVEL_OTHER_I = 10000;
        public const string LEVEL_DEBUG = "DEBUG";
        public const int LEVEL_DEBUG_I = 20000;
        public const string LEVEL_INFO = "INFO";
        public const int LEVEL_INFO_I = 30000;
        public const string LEVEL_WARN = "WARN";
        public const int LEVEL_WARN_I = 40000;
        public const string LEVEL_ERROR = "ERROR";
        public const int LEVEL_ERROR_I = 50000;
        public const string LEVEL_FATAL = "FATAL";
        public const int LEVEL_FATAL_I = 60000;

        public static string stringFromLevel(int level)
        {
            if (level >= LEVEL_FATAL_I)
                return LEVEL_FATAL;
            if (level >= LEVEL_ERROR_I)
                return LEVEL_ERROR;
            if (level >= LEVEL_WARN_I)
                return LEVEL_WARN;
            if (level >= LEVEL_INFO_I)
                return LEVEL_INFO;
            if (level >= LEVEL_DEBUG_I)
                return LEVEL_DEBUG;
            return LEVEL_OTHER;
        }
    }
}
