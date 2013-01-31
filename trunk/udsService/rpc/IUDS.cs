using System;
using System.Collections.Generic;
using System.Text;
using CookComputing.XmlRpc;

namespace uds
{
    public interface IUDS : IXmlRpcProxy
    {
        [XmlRpcMethod("test")]
        bool Test();

        [XmlRpcMethod("message")]
        string Message(string id, string message, string data);

    }
}
