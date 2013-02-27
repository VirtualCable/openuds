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
using System.Text;
using CookComputing.XmlRpc;

namespace UdsAdmin.xmlrpc
{

    public class BaseType
    {
        public string name;
        public string type;
        public string description;
        public string icon;

        public override string ToString()
        {
            return name;
        }

    }

    public class BaseItemData
    {
        public string id;
        public string name;
        public string comments;
        public string type;
        public string typeName;

        public override string ToString()
        {
            return name + "," + comments;
        }

        public override bool Equals(object obj)
        {
            bool eq = base.Equals(obj);
            if (eq == true)
                return eq;
            if (!(obj is BaseItemData))
                return false;
            return ((BaseItemData)obj).id == id;
        }

        public override int GetHashCode() { return 0; }
    }

    public class SimpleInfo
    {
        public string id;
        public string name;

        public SimpleInfo()
        {
            id = name = "";
        }


        public SimpleInfo(string id, string name)
        {
            this.id = id;
            this.name = name;
        }

        public override string ToString()
        {
            return name;
        }
    }

    public struct LoginData
    {
        public string credentials;
        public string versionRequired;
        public string url;  // Download url for new version if needed
        [XmlRpcMissingMapping(MappingAction.Ignore)]  // Right now, linux url is not used for anything... :-)
        public string urlLinux; // Download url for linux version
        public bool isAdmin;
    }

    public class GuiItem
    {
        public string defvalue;
        public int length;
        public bool required;
        public string label;
        public bool rdonly;
        public int order;
        public string tooltip;
        public string type;
        // Choice values (available only for choices)
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public Choice[] values;

        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public ChoiceCallback fills;

        // For multichoices
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public int rows;

        // For multilines
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public int multiline = 0;
    }

    public class GuiField
    {
        public string name;
        public string value; // For "modify" operations
        public GuiItem gui;
    }

    public class PrefGroup
    {
        public string moduleLabel;
        public GuiField[] prefs;
    }

    public struct GuiFieldValue
    {
        public string name;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public string value;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public Choice[] values;

        public GuiFieldValue(string name, string value)
        {
            this.name = name;
            this.value = value;
            this.values = null;
        }

        public GuiFieldValue(string name, Choice[] values)
        {
            this.name = name;
            this.value = null;
            this.values = values;
        }

        static public string getData(GuiFieldValue[] fields, string field)
        {
            foreach( GuiFieldValue g in fields )
                if( g.name == field )
                    return g.value;
            return "";
        }
    }

    public class ServiceProviderType : BaseType
    {
    }

    public class ServiceProvider : BaseItemData
    {
    }

    public class ServiceType : BaseType
    {
    }

    public class ServiceInfo
    {
        public bool needsPublication;
        public int maxDeployed;
        public bool usesCache;
        public bool usesCacheL2;
        public string cacheTooltip;
        public string cacheTooltipL2;
        public bool needsManager;
        public bool mustAssignManually;
        public string typeName; // Type of the service
    }

    public class Service : BaseItemData
    {
        public string idParent;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public ServiceInfo info;
    }

    public class AuthenticatorType : BaseType
    {
        public bool isExternalSource;
        public bool canSearchUsers;
        public bool canSearchGroups;
        public bool needsPassword;
        public string userNameLabel;
        public string groupNameLabel;
        public string passwordLabel;
        public bool canCreateUsers;
    }

    public class Authenticator : BaseItemData
    {
        public string priority;
        public string smallName;
    }

    public class Group
    {
        public string idParent;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public string nameParent;
        public string id;
        public string name;
        public string comments;
        public bool active;

        public override string ToString()
        {
            return name + ", " + comments;
        }
    }

    public class User
    {
        public string idParent;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public string nameParent;
        public string id;
        public string name;
        public string password;
        public string oldPassword; // To check if password has changed, cause it's encripted at database and can't be reversed
        public string realName;
        public string comments;
        public string state;
        public DateTime lastAccess;
        public bool staffMember;
        public bool isAdmin;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public Group[] groups;  // For internal authenticators, active groups are those that the user belongs to, inactive those not

        public override string ToString()
        {
            return name + "(" + realName + ")" + ", " + comments;
        }
    }

    public class OSManagerType : BaseType
    {
    }

    public class OSManager : BaseItemData
    {
    }


    public class TransportType : BaseType
    {
    }

    public class Transport : BaseItemData
    {
        public string priority;
        public string[] networks;
    }

    public class Network
    {
        public string id;
        public string name;
        public string netStart;
        public string netEnd;

        public Network()
        {
            id = name = netStart = netEnd = "";
        }

        public override string ToString()
        {
            return name;
        }
    }

    public class DeployedService
    {
        public string id;
        public string name;
        public string comments;
        public string idService;
        public string idOsManager;
        public string state;
        public int initialServices;
        public int cacheL1;
        public int cacheL2;
        public int maxServices;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public string serviceName;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public string osManagerName;
        public SimpleInfo[] transports;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public SimpleInfo[] groups;
        [XmlRpcMissingMapping(MappingAction.Ignore)]
        public ServiceInfo info;
    }

    public class DeployedServicePublication
    {
        public string idParent;
        public string id;
        public string state;
        public DateTime publishDate;
        public string reason;
        public string revision;
    }

    public class UserService
    {
        public string idParent;
        public string id;
        public string uniqueId;
        public string friendlyName;
        public string state;
        public string osState;
        public DateTime stateDate;
        public DateTime creationDate;
        public string revision;
    }

    public class CachedUserService : UserService
    {
        public string cacheLevel;
    }

    public class AssignedUserService : UserService
    {
        public string user;
        public bool inUse;  
        public DateTime inUseDate;
        public string sourceHost;
        public string sourceIp;
    }

    public class AssignableUserService
    {
        public string id;
        public string name;

        public override string ToString()
        {
            return name;
        }
    }

    public class ResultTest
    {
        public bool ok;
        public string message;
    }

    public class Configuration
    {
        public string section;
        public string key;
        public string value;
        public bool crypt;
        public bool longText;

        public Configuration()
        {
            section = key = value = "";
            crypt = longText = false;
        }

        public Configuration(string section, string key, string value, bool crypt, bool longText)
        {
            this.section = section; this.key = key; this.value = value; this.crypt = crypt; this.longText = longText;
        }
    }

    public class LogEntry
    {
        public DateTime date;
        public int level;
        public string message;
        public string source;
    }

    // Stats structures
    public class StatCounterData
    {
        public DateTime stamp;
        public int value;
    }

    public class StatCounter
    {
        public string title;
        public StatCounterData[] data;
    }

    public struct ChoiceCallback
    {
        public string callbackName;
        public string[] parameters;
    }

    public struct Choice
    {
        public string id;
        public string text;

        public Choice(string id, string text)
        {
            this.id = id;
            this.text = text;
        }

        public override string ToString()
        {
            return text;
        }

        public override bool Equals(object obj)
        {
            bool eq = base.Equals(obj);
            if (eq == true)
                return eq;
            if (!(obj is Choice))
                return false;
            return ((Choice)obj).id == id;
        }

        public override int GetHashCode() { return 0; }
    }

    // Comparators
    public class ServiceProviderTypeSorterByName : IComparer<ServiceProviderType>
    {
        public int Compare(ServiceProviderType a, ServiceProviderType b)
        {
            return a.name.CompareTo(b.name);
        }
    }

    public class ServiceTypeSorterByName : IComparer<ServiceType>
    {
        public int Compare(ServiceType a, ServiceType b)
        {
            return a.name.CompareTo(b.name);
        }
    }


    public class AuthenticatorTypeSorterByName : IComparer<AuthenticatorType>
    {
        public int Compare(AuthenticatorType a, AuthenticatorType b)
        {
            return a.name.CompareTo(b.name);
        }
    }

    public class OSManagerTypeSorterByName : IComparer<OSManagerType>
    {
        public int Compare(OSManagerType a, OSManagerType b)
        {
            return a.name.CompareTo(b.name);
        }
    }

    public class TransportTypeSorterByName : IComparer<TransportType>
    {
        public int Compare(TransportType a, TransportType b)
        {
            return a.name.CompareTo(b.name);
        }
    }

}
