#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on Nov 16, 2011

@author: dkmaster
'''

import sys, time, logging
from uds.actor.daemon import Daemon
from uds.actor.rpc import Rpc
from uds.actor import net
from uds.actor.renamer import rename
 
logger = logging.getLogger('uds')

class MyDaemon(Daemon):
    def run(self):
        while True:
            # Wait for networks to become ready
            info = net.getExternalIpAndMacs()
            if len(info) > 0:
                break
            time.sleep(4)
        # Now, get info of what to do
        Rpc.initialize()
        
        # waits for a valid command (maybe broker down or not reachable, so we loop here till we know what to do (that is, broker is reachable))
        todo = None 
        while todo is None: 
            Rpc.resetId()
            todo = Rpc.getInfo()
            if todo is None:
                time.sleep(4)
        
        # We can get 'rename:newname', ''. Anything else is an error        
        data = todo.split(':')
        
        if data[0] == 'rename':
            logger.info('Renaming to {0}'.format(data[1]))
            rename(data[1])
            Rpc.setReady()
        elif todo == '':
            logger.info('Unmanaged machine')
            # Unmanaged machine, exit
            return
        else:
            # Error, log and exit
            logger.error('Unknown command received: {0}'.format(todo))
            return
        
        # Keep notifiyin ip changes
        info = net.getExternalIpAndMacs()
        # We have "info" with know interfaces
        while True:
            newInfo = net.getExternalIpAndMacs()
            for k in info.keys():
                if info[k]['ip'] != newInfo[k]['ip']:
                    if Rpc.notifyIpChange() is not None:
                        info = newInfo
                    else:
                        logger.info('Could not notify IP address. Will retry later.')
                    break
            time.sleep(5)
        return
        

if __name__ == '__main__': 
    if len(sys.argv) == 3:
        if 'login' == sys.argv[1]:
            logger.debug('Notifiyin login')
            Rpc.initialize()
            Rpc.login(sys.argv[2])
            sys.exit(0)
        elif 'logout' == sys.argv[1]:
            logger.debug('Notifiyin logout')
            Rpc.initialize()
            Rpc.logout(sys.argv[2])
            sys.exit(0)
            
    logger.debug('Executing actor')
    daemon = MyDaemon('/var/run/udsactor.pid') 
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart|login 'username'|logout 'username'" % sys.argv[0]
        sys.exit(2)    

