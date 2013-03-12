using System;
using System.Collections.Generic;
using log4net;

namespace uds
{

    public class RPCAppender : log4net.Appender.AppenderSkeleton
    {
        /// <summary>
        /// Sends the logging event to UDS
        /// </summary>
        override protected void Append(log4net.Core.LoggingEvent lEvent)
        {
            string message = RenderLoggingEvent(lEvent);
            // Filters out messages that are FATAL or DEBUG
            if (lEvent.Level == log4net.Core.Level.Critical || lEvent.Level == log4net.Core.Level.Fatal || lEvent.Level == log4net.Core.Level.Debug)
                return;

            rpc.Log(message, lEvent.Level.Name);
        }

        /// <summary>
        /// This appender requires a <see cref="Layout"/> to be set.
        /// </summary>
        override protected bool RequiresLayout
        {
            get { return true; }
        }
    }
}
